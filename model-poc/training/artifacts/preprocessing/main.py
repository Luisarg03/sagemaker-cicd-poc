import argparse
import os
from pathlib import Path

import pandas as pd


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--input-data", type=str, default="/opt/ml/processing/input/data"
    )
    parser.add_argument(
        "--output-data", type=str, default="/opt/ml/processing/output/train"
    )
    args = parser.parse_args()

    print(f"Preprocessing data from {args.input_data} to {args.output_data}")

    # Ensure output directory exists
    os.makedirs(args.output_data, exist_ok=True)

    # Stub: Create a dummy processed file
    output_file = Path(args.output_data) / "train.csv"
    pd.DataFrame({"feature": [1, 2, 3], "target": [0, 1, 0]}).to_csv(
        output_file, index=False
    )

    print("Preprocessing completed successfully.")


if __name__ == "__main__":
    main()
