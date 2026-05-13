import argparse
import json
import os
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model-dir", type=str, default="/opt/ml/processing/input/model"
    )
    parser.add_argument(
        "--output-dir", type=str, default="/opt/ml/processing/output/evaluation"
    )
    args = parser.parse_args()

    print(f"Validating model from {args.model_dir}")

    # Stub: read model artifact
    model_file = Path(args.model_dir) / "model.json"
    if model_file.exists():
        with open(model_file) as f:
            model_data = json.load(f)
            print(f"Validating model: {model_data.get('model_name')}")
    else:
        print(f"Warning: Model artifact not found at {model_file}")

    # Stub: Create evaluation metrics
    os.makedirs(args.output_dir, exist_ok=True)
    evaluation_report = Path(args.output_dir) / "evaluation.json"

    report = {
        "classification_metrics": {
            "accuracy": {"value": 0.95, "standard_deviation": 0.01},
            "precision": {"value": 0.94, "standard_deviation": 0.02},
            "recall": {"value": 0.96, "standard_deviation": 0.01},
        }
    }

    with open(evaluation_report, "w") as f:
        json.dump(report, f)

    print(f"Evaluation report saved to {evaluation_report}")


if __name__ == "__main__":
    main()
