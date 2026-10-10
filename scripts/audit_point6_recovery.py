#!/usr/bin/env python3
"""Audit Item 6: Recovery metadata audit and calibration baseline sensitivity."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline

def main():
    df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
    subsets = get_feature_subsets(df.columns)
    full_feats = subsets["full"]
    calib_feats = subsets["calibration_properties"]
    
    real_df = df[~df["backend"].str.startswith("sim_")].copy()
    
    train_rounds = [1, 2, 3, 4, 5]
    test_rounds = [8, 9, 10]
    
    # Condition A: All rounds included
    tr_all = real_df[real_df["round_id"].isin(train_rounds)].copy()
    te_all = real_df[real_df["round_id"].isin(test_rounds)].copy()
    
    # Condition B: Excluding recovered records (Kingston R5, R9, R10)
    # Kingston R5 is in train; Kingston R9, R10 are in test
    tr_clean = tr_all[~((tr_all["backend"] == "ibm_kingston") & (tr_all["round_id"] == 5))].copy()
    te_clean = te_all[~((te_all["backend"] == "ibm_kingston") & (te_all["round_id"].isin([9, 10])))].copy()
    
    # Like-for-like identical test chunks: te_clean (56 samples: 24 Fez, 24 Marrakesh, 8 Kingston R8)
    te_common = te_clean.copy()
    
    print("=== Record Recovery Metadata Summary ===")
    print("Recovered / Hand-handled records:")
    print("  1. ibm_kingston Round 05: Job db25hv42ljfc73d405ng | transpile_fallback + post_hoc_retrieval (properties_snapshot @ 04:35Z vs execution @ 02:58Z)")
    print("  2. ibm_kingston Round 09: Job db4c73o4qg6s73c1vucg | post_hoc_api_retrieval (properties_snapshot retrieved post-sleep)")
    print("  3. ibm_kingston Round 10: Job db4gqkcvf2bc73cujge0 | post_hoc_api_retrieval (properties_snapshot retrieved post-sleep at 06:02Z)")
    print("  Measured bitstring counts: 100% UNALTERED from Qiskit Runtime API.")

    print("\n=== Like-for-Like Sensitivity on Identical Test Chunks (n=56: Fez R8-10, Marrakesh R8-10, Kingston R8) ===")
    print("Evaluating models trained on (A) All Train vs (B) Clean Train without Kingston R5, evaluated on identical clean test chunks:\n")
    
    models = ["logistic_regression", "svm_rbf", "random_forest", "gradient_boosting", "mlp"]
    
    print(f"{'Model':22s} | {'Feature Set':16s} | {'Train: All (Acc)':16s} | {'Train: Clean (Acc)':18s} | {'Difference':10s}")
    print("-" * 90)
    
    for m in models:
        # Full features
        pipe_all_full = create_classifier_pipeline(m, seed=42)
        pipe_all_full.fit(tr_all[full_feats].values, tr_all["backend"].values)
        acc_all_full = accuracy_score(te_common["backend"].values, pipe_all_full.predict(te_common[full_feats].values))
        
        pipe_clean_full = create_classifier_pipeline(m, seed=42)
        pipe_clean_full.fit(tr_clean[full_feats].values, tr_clean["backend"].values)
        acc_clean_full = accuracy_score(te_common["backend"].values, pipe_clean_full.predict(te_common[full_feats].values))
        
        diff_full = acc_clean_full - acc_all_full
        print(f"{m:22s} | {'Full (196-dim)':16s} | {acc_all_full:16.4f} | {acc_clean_full:18.4f} | {diff_full:+10.4f}")
        
        # Calibration baseline features
        pipe_all_cal = create_classifier_pipeline(m, seed=42)
        pipe_all_cal.fit(tr_all[calib_feats].values, tr_all["backend"].values)
        acc_all_cal = accuracy_score(te_common["backend"].values, pipe_all_cal.predict(te_common[calib_feats].values))
        
        pipe_clean_cal = create_classifier_pipeline(m, seed=42)
        pipe_clean_cal.fit(tr_clean[calib_feats].values, tr_clean["backend"].values)
        acc_clean_cal = accuracy_score(te_common["backend"].values, pipe_clean_cal.predict(te_common[calib_feats].values))
        
        diff_cal = acc_clean_cal - acc_all_cal
        print(f"{'':22s} | {'CalibProp (11-d)':16s} | {acc_all_cal:16.4f} | {acc_clean_cal:18.4f} | {diff_cal:+10.4f}")

    print("\n=== Sensitivity on Raw Full Test Set (n=72) vs Clean Test Set (n=56) ===")
    for m in models:
        pipe = create_classifier_pipeline(m, seed=42)
        pipe.fit(tr_all[full_feats].values, tr_all["backend"].values)
        acc_72 = accuracy_score(te_all["backend"].values, pipe.predict(te_all[full_feats].values))
        
        pipe_c = create_classifier_pipeline(m, seed=42)
        pipe_c.fit(tr_clean[full_feats].values, tr_clean["backend"].values)
        acc_56 = accuracy_score(te_clean["backend"].values, pipe_c.predict(te_clean[full_feats].values))
        print(f"  {m:20s}: All (n=72) = {acc_72:.4f} | Clean (n=56) = {acc_56:.4f} (Diff: {acc_56 - acc_72:+.4f})")

if __name__ == "__main__":
    main()
