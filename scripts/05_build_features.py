#!/usr/bin/env python3
"""Script 05: Build feature matrix from immutable raw measurement records.

Parses all raw round records in data/raw (or dryrun/data/raw), computes the
196-dimensional black-box statistical feature representation (probabilities,
marginals, parities, ZZ correlators, TVD/Hellinger/KL, entropy, readout errors)
and baseline calibration properties, and stores the processed dataset in
data/features/.
"""

import argparse
import logging
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qfp.features import build_dataset_from_raw_records, get_feature_subsets
from qfp.provenance import enforce_dataframe_provenance

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("build_features")


def parse_args():
    parser = argparse.ArgumentParser(description="Extract features from raw experimental records.")
    parser.add_argument("--dry-run", action="store_true", help="Process dryrun raw data directory.")
    return parser.parse_args()


def main():
    args = parse_args()
    raw_root = Path("dryrun/data/raw") if args.dry_run else Path("data/raw")
    features_root = Path("dryrun/data/features") if args.dry_run else Path("data/features")
    features_root.mkdir(parents=True, exist_ok=True)

    raw_files = list(raw_root.rglob("round_*.json"))
    if not raw_files:
        logger.error(f"No raw round files found in {raw_root}!")
        sys.exit(1)

    logger.info(f"Discovered {len(raw_files)} raw round records in {raw_root}. Building features...")
    df = build_dataset_from_raw_records(raw_files, is_dryrun=args.dry_run)
    enforce_dataframe_provenance(df, is_dryrun=args.dry_run)

    subsets = get_feature_subsets(df.columns)
    
    # Save CSV and Parquet
    csv_path = features_root / "dataset_features.csv"
    parquet_path = features_root / "dataset_features.parquet"
    
    df.to_csv(csv_path, index=False)
    try:
        df.to_parquet(parquet_path, index=False)
    except Exception as e:
        logger.warning(f"Could not write Parquet (pyarrow/fastparquet): {e}. CSV saved successfully.")

    logger.info(f"Successfully constructed feature matrix: {df.shape[0]} samples x {df.shape[1]} columns.")
    logger.info(f"Backends represented: {sorted(df['backend'].unique())}")
    logger.info(f"Rounds represented: {sorted(df['round_id'].unique())}")
    logger.info(f"Feature Subsets: { {k: len(v) for k, v in subsets.items()} }")
    logger.info(f"Feature dataset saved to {csv_path}")


if __name__ == "__main__":
    main()
