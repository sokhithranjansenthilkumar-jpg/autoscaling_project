import os
import sys

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATASET_PATH = os.path.join(BASE_DIR, "dataset.csv")
MODELS_DIR = os.path.join(BASE_DIR, "autoscaling", "models")
MODEL_PATH = os.path.join(MODELS_DIR, "model.pkl")
FEATURE_COLUMNS = ["users", "cpu", "memory", "latency"]


def load_dataset():
    if not os.path.exists(DATASET_PATH):
        raise FileNotFoundError(f"dataset.csv not found at: {DATASET_PATH}")

    data = pd.read_csv(DATASET_PATH)
    required = set(FEATURE_COLUMNS + ["instances"])
    if not required.issubset(set(data.columns)):
        raise ValueError(
            "dataset.csv must contain columns: users, cpu, memory, latency, instances"
        )

    data = data.dropna(subset=FEATURE_COLUMNS + ["instances"])
    if data.empty:
        raise ValueError("dataset.csv has no usable rows after dropping missing values")

    return data


def train_and_save(data):
    features = data[FEATURE_COLUMNS]
    target = data["instances"]

    model = LinearRegression()
    model.fit(features, target)

    os.makedirs(MODELS_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)

    score = model.score(features, target)
    print("Training complete")
    print(f"Rows used: {len(data)}")
    print(f"R2 score: {score:.4f}")
    print(f"Saved model: {MODEL_PATH}")


def main():
    try:
        data = load_dataset()
        train_and_save(data)
    except Exception as exc:
        print(f"Training failed: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
