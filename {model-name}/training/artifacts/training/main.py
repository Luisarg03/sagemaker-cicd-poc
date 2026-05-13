import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model")
    )
    parser.add_argument(
        "--train",
        type=str,
        default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"),
    )
    args = parser.parse_args()

    print(f"Training model with data from {args.train}")

    train_file = Path(args.train) / "train.csv"
    if train_file.exists():
        rows = len(train_file.read_text().strip().splitlines()) - 1  # exclude header
        print(f"Read {rows} rows of training data")
    else:
        print(f"Warning: {train_file} not found. Proceeding with dummy training.")

    os.makedirs(args.model_dir, exist_ok=True)
    model_artifact = Path(args.model_dir) / "model.json"
    with open(model_artifact, "w") as f:
        json.dump({"model_name": "poc-model", "version": "1.0", "status": "trained"}, f)

    print(f"Model artifact saved to {model_artifact}")


if __name__ == "__main__":
    main()
