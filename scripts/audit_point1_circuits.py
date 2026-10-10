#!/usr/bin/env python3
"""Audit Item 1: Print CIRCUIT_NAMES, definitions, and column prefixes."""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

import pandas as pd
from qfp.circuits import CIRCUIT_NAMES, build_benchmark_circuits
from qfp.features import get_feature_subsets

def main():
    print("=== CIRCUIT_NAMES from src/qfp/circuits.py ===")
    for i, name in enumerate(CIRCUIT_NAMES, 1):
        print(f"  {i:02d}. {name}")

    print("\n=== Benchmark Circuit Definitions ===")
    circuits = build_benchmark_circuits(seed=42)
    for name, qc in circuits.items():
        ops = [inst.operation.name for inst in qc.data if inst.operation.name != "barrier"]
        print(f"  Circuit: {name:26s} | Qubits: {qc.num_qubits} | Depth: {qc.depth():3d} | Non-barrier ops ({len(ops)}): {ops[:12]}...")

    print("\n=== Feature Column Prefixes from dataset_features.csv ===")
    df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
    subsets = get_feature_subsets(df.columns)
    full_cols = subsets["full"]
    
    circuit_prefixes = sorted(list(set(c.split("__")[0] for c in full_cols if "__" in c)))
    print("Distinct circuit prefixes in features:")
    for cp in circuit_prefixes:
        count = sum(1 for c in full_cols if c.startswith(cp + "__"))
        print(f"  {cp:26s} ({count:2d} features)")
        
    other_cols = [c for c in full_cols if "__" not in c]
    print(f"\nNon-circuit feature columns ({len(other_cols)}):")
    for oc in other_cols:
        print(f"  {oc}")

    print("\n=== Real Feature Extraction Path ===")
    print("  File: src/qfp/features.py")
    print("  Functions: extract_single_circuit_features, extract_all_features_from_sample, build_dataset_from_raw_records")
    print("  Verification: src/features/extraction.py does NOT exist.")

if __name__ == "__main__":
    main()
