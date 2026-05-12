import os
import argparse
import pandas as pd
import json
from pathlib import Path

def main():
    parser = argparse.ArgumentParser()
    # SageMaker Training Job default paths
    parser.add_argument("--model-dir", type=str, default=os.environ.get("SM_MODEL_DIR", "/opt/ml/model"))
    parser.add_argument("--train", type=str, default=os.environ.get("SM_CHANNEL_TRAIN", "/opt/ml/input/data/train"))
    args = parser.parse_args()

    print(f"Training model with data from {args.train}")
    
    # Stub: read input to verify it exists
    train_file = Path(args.train) / "train.csv"
    if train_file.exists():
        df = pd.read_csv(train_file)
        print(f"Read {len(df)} rows of training data")
    else:
        print(f"Warning: {train_file} not found. Proceeding with dummy training.")

    # Stub: Create a dummy model artifact
    os.makedirs(args.model_dir, exist_ok=True)
    model_artifact = Path(args.model_dir) / "model.json"
    with open(model_artifact, "w") as f:
        json.dump({"model_name": "poc-model", "version": "1.0", "status": "trained"}, f)
    
    print(f"Model artifact saved to {model_artifact}")

if __name__ == "__main__":
    main()
