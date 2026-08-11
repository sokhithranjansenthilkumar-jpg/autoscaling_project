import csv
import json
import os
from functools import lru_cache

import joblib
from django.db.models import Max
from django.db.utils import OperationalError, ProgrammingError
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET

from .models import MetricSnapshot, ScenarioPreset

APP_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(APP_DIR, "models", "model.pkl")
DATASET_PATH = os.path.join(os.path.dirname(APP_DIR), "dataset.csv")
MODEL_FEATURES = ["users", "cpu", "memory", "latency"]
MARKETPLACE_SOURCES = ["amazon", "flipkart", "meesho", "ajio", "myntra"]


def api_error(message, status=400, details=None):
    payload = {"ok": False, "error": message}
    if details:
        payload["details"] = details
    return JsonResponse(payload, status=status)


def json_body(request):
    try:
        return json.loads(request.body or b"{}")
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON body: {exc.msg}") from exc


def parse_number(payload, key, target_type, minimum=None, maximum=None):
    if key not in payload:
        raise ValueError(f"Missing '{key}' in request body")

    raw_value = payload.get(key)
    if raw_value in (None, ""):
        raise ValueError(f"'{key}' cannot be empty")

    try:
        value = target_type(raw_value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' must be a valid {target_type.__name__}") from exc

    if minimum is not None and value < minimum:
        raise ValueError(f"'{key}' must be >= {minimum}")
    if maximum is not None and value > maximum:
        raise ValueError(f"'{key}' must be <= {maximum}")
    return value


def parse_optional_positive_int(payload, key):
    if key not in payload or payload.get(key) in (None, ""):
        return None

    try:
        value = int(payload.get(key))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"'{key}' must be a valid int") from exc

    if value <= 0:
        raise ValueError(f"'{key}' must be > 0")
    return value


@lru_cache(maxsize=1)
def load_model():
    if not os.path.exists(MODEL_PATH):
        return load_fallback_model()

    try:
        return joblib.load(MODEL_PATH)
    except Exception:
        return load_fallback_model()


def load_fallback_model():
    if not os.path.exists(DATASET_PATH):
        return None

    try:
        with open(DATASET_PATH, newline="", encoding="utf-8") as file_handle:
            reader = csv.DictReader(file_handle)
            rows = [
                {
                    "users": int(row["users"]),
                    "cpu": float(row["cpu"]),
                    "memory": float(row["memory"]),
                    "latency": float(row["latency"]),
                    "instances": int(float(row["instances"])),
                }
                for row in reader
            ]
    except Exception:
        return None

    if not rows:
        return None

    return {"type": "fallback_dataset", "rows": rows}


def prediction_payload_from_values(users, cpu, memory, latency):
    return {
        "users": int(users),
        "cpu": float(cpu),
        "memory": float(memory),
        "latency": float(latency),
    }


def model_input_from_payload(model, payload):
    feature_names = list(getattr(model, "feature_names_in_", []))
    if feature_names:
        return [[payload[name] for name in feature_names]]

    feature_count = int(getattr(model, "n_features_in_", 1))
    feature_order = MODEL_FEATURES[:feature_count]
    if feature_count == 1:
        feature_order = ["cpu"]

    return [[payload[name] for name in feature_order]]


def predict_instances(model, payload):
    if isinstance(model, dict) and model.get("type") == "fallback_dataset":
        return predict_instances_from_dataset(model["rows"], payload)

    model_input = model_input_from_payload(model, payload)
    predicted = int(round(float(model.predict(model_input)[0])))
    return max(1, predicted)


def predict_instances_from_dataset(rows, payload):
    nearest_row = min(
        rows,
        key=lambda row: (
            abs(row["users"] - payload["users"]) * 0.08
            + abs(row["cpu"] - payload["cpu"]) * 1.0
            + abs(row["memory"] - payload["memory"]) * 0.45
            + abs(row["latency"] - payload["latency"]) * 0.02
        ),
    )
    return max(1, int(nearest_row["instances"]))


def scaling_summary(recommended, current):
    current_value = int(current or 0)
    delta = recommended - current_value

    scaling = "stable"
    if delta > 0:
        scaling = "scale_up"
    elif delta < 0:
        scaling = "scale_down"

    return {
        "current_instances": current_value,
        "recommended_instances": recommended,
        "delta": delta,
        "scaling": scaling,
    }


def snapshot_to_dict(snapshot):
    return {
        "id": snapshot.id,
        "timestamp": snapshot.created_at.isoformat(),
        "users": snapshot.active_users,
        "cpu": float(snapshot.cpu),
        "memory": float(snapshot.memory),
        "latency": float(snapshot.latency),
        "instances": snapshot.current_instances,
        "source": snapshot.source,
    }


def save_snapshot(users, cpu, memory, latency, instances=None, source="manual"):
    return MetricSnapshot.objects.create(
        active_users=users,
        cpu=cpu,
        memory=memory,
        latency=latency,
        current_instances=instances,
        source=(str(source).strip() or "manual")[:50],
    )


def get_latest_snapshot_for_source(source):
    return MetricSnapshot.objects.filter(source=source).order_by("-created_at", "-id").first()


def get_latest_snapshot():
    return MetricSnapshot.objects.order_by("-created_at").first()


def resolve_marketplace_current_instances(model, source, provided_instances):
    provided_value = int(provided_instances) if provided_instances else None

    if provided_value is not None:
        return provided_value

    latest_snapshot = get_latest_snapshot_for_source(source)

    if latest_snapshot is None:
        return provided_value

    latest_payload = prediction_payload_from_values(
        latest_snapshot.active_users,
        latest_snapshot.cpu,
        latest_snapshot.memory,
        latest_snapshot.latency,
    )
    latest_recommended = predict_instances(model, latest_payload)
    if latest_recommended > 0:
        return latest_recommended

    if latest_snapshot.current_instances:
        return int(latest_snapshot.current_instances)

    return provided_value


def parse_prediction_inputs(payload):
    users = parse_number(payload, "users", int, minimum=0)
    cpu = parse_number(payload, "cpu", float, minimum=0, maximum=100)
    memory = parse_number(payload, "memory", float, minimum=0, maximum=100)
    latency = parse_number(payload, "latency", float, minimum=1)
    return prediction_payload_from_values(users, cpu, memory, latency)


@require_GET
def api_overview(request):
    return JsonResponse(
        {
            "ok": True,
            "service": "autoscaling-api",
            "message": "Autoscaling backend is running.",
            "routes": {
                "health": "/health/",
                "predict": "/predict/",
                "predict_live": "/predict/live/",
                "predict_marketplace": "/predict/marketplace/",
                "ingest": "/ingest/",
                "realtime_latest": "/realtime/latest/",
                "realtime_history": "/realtime/history/",
                "marketplace_status": "/status/marketplaces/",
                "dataset": "/dataset/",
                "scenario_presets": "/scenario-presets/",
                "export_realtime_dataset": "/dataset/export-realtime/",
            },
            "model_features": MODEL_FEATURES,
            "server_time": timezone.now().isoformat(),
        }
    )


@csrf_exempt
def predict(request):
    if request.method != "POST":
        return api_error("Only POST method allowed", status=405)

    try:
        payload = parse_prediction_inputs(json_body(request))
    except ValueError as exc:
        return api_error(str(exc), status=400)

    model = load_model()
    if model is None:
        return api_error("Model file missing. Run: py -3 train_model.py", status=500)

    instances = predict_instances(model, payload)
    return JsonResponse(
        {
            "ok": True,
            "action": f"Scale to {instances} instance(s)",
            "instances": instances,
            "inputs": payload,
        }
    )


@csrf_exempt
def ingest_metric(request):
    if request.method != "POST":
        return api_error("Only POST method allowed", status=405)

    try:
        body = json_body(request)
        payload = parse_prediction_inputs(body)
        instances = parse_optional_positive_int(body, "instances")
        source = body.get("source", "manual")
        snapshot = save_snapshot(
            payload["users"],
            payload["cpu"],
            payload["memory"],
            payload["latency"],
            instances=instances,
            source=source,
        )
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        return api_error("Failed to ingest metric", status=400, details=str(exc))

    return JsonResponse({"ok": True, "snapshot": snapshot_to_dict(snapshot)}, status=201)


@require_GET
def realtime_latest(request):
    snapshot = get_latest_snapshot()
    if snapshot is None:
        return api_error("No realtime metrics ingested yet", status=404)

    model = load_model()
    if model is None:
        return api_error("Model file missing. Run: py -3 train_model.py", status=500)

    payload = prediction_payload_from_values(
        snapshot.active_users, snapshot.cpu, snapshot.memory, snapshot.latency
    )
    instances = predict_instances(model, payload)
    return JsonResponse(
        {
            "ok": True,
            "snapshot": snapshot_to_dict(snapshot),
            "recommended_instances": instances,
            "action": f"Scale to {instances} instance(s)",
            "server_time": timezone.now().isoformat(),
        }
    )


@require_GET
def realtime_history(request):
    try:
        limit = int(request.GET.get("limit", 50))
    except ValueError:
        return api_error("limit must be an integer", status=400)

    limit = max(1, min(limit, 500))
    try:
        snapshots = MetricSnapshot.objects.order_by("-created_at")[:limit]
    except (OperationalError, ProgrammingError):
        return api_error(
            "Database not initialized. Run: py -3.12 manage.py migrate",
            status=503,
        )

    history = [snapshot_to_dict(snapshot) for snapshot in snapshots]
    return JsonResponse({"ok": True, "points": history, "count": len(history)})


@csrf_exempt
def predict_live(request):
    if request.method != "POST":
        return api_error("Only POST method allowed", status=405)

    snapshot = get_latest_snapshot()
    if snapshot is None:
        return api_error("No realtime metrics ingested yet", status=404)

    model = load_model()
    if model is None:
        return api_error("Model file missing. Run: py -3 train_model.py", status=500)

    payload = prediction_payload_from_values(
        snapshot.active_users, snapshot.cpu, snapshot.memory, snapshot.latency
    )
    instances = predict_instances(model, payload)
    return JsonResponse(
        {
            "ok": True,
            "action": f"Scale to {instances} instance(s)",
            "instances": instances,
            "snapshot": snapshot_to_dict(snapshot),
        }
    )


@csrf_exempt
def predict_marketplace(request):
    if request.method != "POST":
        return api_error("Only POST method allowed", status=405)

    try:
        body = json_body(request)
        source = str(body.get("source", "")).strip().lower()
        if source not in MARKETPLACE_SOURCES:
            raise ValueError(
                f"source must be one of: {', '.join(MARKETPLACE_SOURCES)}"
            )

        payload = parse_prediction_inputs(body)
        instances = parse_optional_positive_int(body, "instances")
    except ValueError as exc:
        return api_error(str(exc), status=400)
    except Exception as exc:
        return api_error("Failed to ingest marketplace metric", status=400, details=str(exc))

    model = load_model()
    if model is None:
        return api_error("Model file missing. Run: py -3 train_model.py", status=500)

    effective_instances = resolve_marketplace_current_instances(model, source, instances)
    try:
        snapshot = save_snapshot(
            payload["users"],
            payload["cpu"],
            payload["memory"],
            payload["latency"],
            instances=effective_instances,
            source=source,
        )
    except Exception as exc:
        return api_error("Failed to ingest marketplace metric", status=400, details=str(exc))

    recommended = predict_instances(model, payload)
    summary = scaling_summary(recommended, snapshot.current_instances)
    return JsonResponse(
        {
            "ok": True,
            "source": source,
            "action": f"Scale to {recommended} instance(s)",
            **summary,
            "snapshot": snapshot_to_dict(snapshot),
            "server_time": timezone.now().isoformat(),
        },
        status=201,
    )


@require_GET
def marketplace_status(request):
    model = load_model()
    if model is None:
        return api_error("Model file missing. Run: py -3 train_model.py", status=500)

    try:
        latest_by_source = (
            MetricSnapshot.objects.filter(source__in=MARKETPLACE_SOURCES)
            .values("source")
            .annotate(latest=Max("created_at"))
        )
    except (OperationalError, ProgrammingError):
        return api_error(
            "Database not initialized. Run: py -3 manage.py migrate",
            status=503,
        )

    status = {}
    for row in latest_by_source:
        snapshot = (
            MetricSnapshot.objects.filter(source=row["source"], created_at=row["latest"])
            .order_by("-id")
            .first()
        )
        if snapshot is None:
            continue

        payload = prediction_payload_from_values(
            snapshot.active_users, snapshot.cpu, snapshot.memory, snapshot.latency
        )
        recommended = predict_instances(model, payload)
        summary = scaling_summary(recommended, snapshot.current_instances)

        status[row["source"]] = {
            "snapshot": snapshot_to_dict(snapshot),
            **summary,
            "action": f"Scale to {recommended} instance(s)",
        }

    return JsonResponse({"ok": True, "status": status, "server_time": timezone.now().isoformat()})


@require_GET
def health(request):
    return JsonResponse({"ok": True, "time": timezone.now().isoformat()})


@require_GET
def scenario_presets(request):
    presets = ScenarioPreset.objects.order_by("group_name", "row_number")
    groups = {}

    for preset in presets:
        groups.setdefault(preset.group_name, []).append(
            {
                "row_number": preset.row_number,
                "active_users": preset.active_users,
                "cpu": float(preset.cpu),
                "memory": float(preset.memory),
                "latency": float(preset.latency),
            }
        )

    return JsonResponse(
        {
            "ok": True,
            "groups": groups,
            "count": sum(len(rows) for rows in groups.values()),
        }
    )


@require_GET
def dataset(request):
    if not os.path.exists(DATASET_PATH):
        return api_error("dataset.csv not found", status=404)

    try:
        with open(DATASET_PATH, newline="", encoding="utf-8") as file_handle:
            reader = csv.DictReader(file_handle)
            rows = list(reader)
    except Exception as exc:
        return api_error("Failed to parse dataset.csv", status=400, details=str(exc))

    if not rows:
        return JsonResponse(
            {
                "ok": True,
                "points": [],
                "count": 0,
                "cpuMin": None,
                "cpuMax": None,
                "instanceMin": None,
                "instanceMax": None,
                "features": MODEL_FEATURES,
            }
        )

    fieldnames = set(rows[0].keys())
    required_columns = set(MODEL_FEATURES + ["instances"])
    if not required_columns.issubset(fieldnames):
        return api_error(
            "dataset.csv must contain 'users', 'cpu', 'memory', 'latency', and 'instances'",
            status=400,
        )

    try:
        points = [
            {"cpu": float(row["cpu"]), "instances": float(row["instances"])}
            for row in rows
        ]
    except (TypeError, ValueError, KeyError) as exc:
        return api_error("dataset.csv contains invalid numeric values", status=400, details=str(exc))

    cpu_values = [point["cpu"] for point in points]
    instance_values = [point["instances"] for point in points]

    return JsonResponse(
        {
            "ok": True,
            "points": points,
            "count": len(points),
            "cpuMin": min(cpu_values),
            "cpuMax": max(cpu_values),
            "instanceMin": min(instance_values),
            "instanceMax": max(instance_values),
            "features": MODEL_FEATURES,
        }
    )


@require_GET
def export_realtime_dataset(request):
    try:
        snapshots = MetricSnapshot.objects.exclude(current_instances__isnull=True).order_by(
            "created_at"
        )
    except (OperationalError, ProgrammingError):
        return api_error(
            "Database not initialized. Run: py -3.12 manage.py migrate",
            status=503,
        )

    rows = [
        {
            "users": int(item.active_users),
            "cpu": float(item.cpu),
            "memory": float(item.memory),
            "latency": float(item.latency),
            "instances": int(item.current_instances),
        }
        for item in snapshots
    ]

    csv_path = os.path.join(os.path.dirname(APP_DIR), "realtime_dataset_export.csv")
    with open(
        csv_path,
        "w",
        newline="",
        encoding="utf-8",
    ) as file_handle:
        writer = csv.DictWriter(
            file_handle, fieldnames=["users", "cpu", "memory", "latency", "instances"]
        )
        writer.writeheader()
        writer.writerows(rows)

    return JsonResponse(
        {
            "ok": True,
            "exported_rows": len(rows),
            "path": csv_path,
            "note": "Use this file to retrain with real production data.",
        }
    )
