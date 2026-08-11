from django.urls import path
from . import views

urlpatterns = [
    path("", views.api_overview, name="api_overview"),
    path("health/", views.health, name="health"),
    path("predict/", views.predict, name="predict"),
    path("predict/live/", views.predict_live, name="predict_live"),
    path("predict/marketplace/", views.predict_marketplace, name="predict_marketplace"),
    path("ingest/", views.ingest_metric, name="ingest_metric"),
    path("realtime/latest/", views.realtime_latest, name="realtime_latest"),
    path("realtime/history/", views.realtime_history, name="realtime_history"),
    path("status/marketplaces/", views.marketplace_status, name="marketplace_status"),
    path("scenario-presets/", views.scenario_presets, name="scenario_presets"),
    path("dataset/", views.dataset, name="dataset"),
    path("dataset/export-realtime/", views.export_realtime_dataset, name="export_realtime_dataset"),
]
