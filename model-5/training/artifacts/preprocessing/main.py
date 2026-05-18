import argparse
import os
from pathlib import Path


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

    os.makedirs(args.output_data, exist_ok=True)

    # Stub: write a dummy CSV without pandas dependency
    output_file = Path(args.output_data) / "train.csv"
    output_file.write_text("feature,target\n1,0\n2,1\n3,0\n")

    print("Preprocessing completed successfully.")


if __name__ == "__main__":
    main()
