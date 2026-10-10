#!/usr/bin/env python3
"""Audit Item 4: E4 with full features per backend and per adversary."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
import json

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.detect import build_integrity_detector
from qfp.metrics import compute_roc_and_eer

def main():
    df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
    subsets = get_feature_subsets(df.columns)
    full_feats = subsets["full"]
    
    train_rounds = [1, 2, 3, 4, 5]
    val_rounds = [6, 7]
    test_rounds = [8, 9, 10]
    
    real_df = df[~df["backend"].str.startswith("sim_")].copy()
    sim_df = df[df["backend"].str.startswith("sim_")].copy()
    real_backends = sorted(real_df["backend"].unique())
    
    results = {}
    
    print("=== E4 Full Features (196-dim) Detailed Metrics ===")
    for target_b in real_backends:
        gen_tr = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(train_rounds))]
        gen_val = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(val_rounds))]
        gen_te = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(test_rounds))]
        
        # Fit detector on train rounds
        det = build_integrity_detector("mahalanobis", seed=42)
        det.fit(gen_tr[full_feats].values)
        
        # Validation threshold calibrated at FPR = 0.05 on val rounds 6-7
        val_thresh = det.calibrate_threshold(gen_val[full_feats].values, target_fpr=0.05)
        
        # Evaluate genuine test scores
        gen_te_scores = det.compute_anomaly_scores(gen_te[full_feats].values)
        # FRR = proportion of genuine test samples with score > val_thresh
        frr = float(np.mean(gen_te_scores > val_thresh))
        
        print(f"\nTarget Backend: {target_b} (Val Thresh @ 5% FPR: {val_thresh:.4f}, Test FRR: {frr:.4f})")
        print(f"  Genuine Test Scores: mean={np.mean(gen_te_scores):.2f}, min={np.min(gen_te_scores):.2f}, max={np.max(gen_te_scores):.2f}")
        
        other_hw_te = real_df[(real_df["backend"] != target_b) & (real_df["round_id"].isin(test_rounds))]
        s0_te = sim_df[(sim_df["backend"] == "sim_S0_ideal") | (sim_df["backend"].str.contains(f"sim_S0.*{target_b}"))]
        if s0_te.empty:
            s0_te = sim_df[sim_df["backend"].str.contains("sim_S0")]
        s0_te = s0_te[s0_te["round_id"].isin(test_rounds)]
        
        s1_te = sim_df[(sim_df["backend"] == f"sim_S1_{target_b}") & (sim_df["round_id"].isin(test_rounds))]
        s2_te = sim_df[(sim_df["backend"] == f"sim_S2_{target_b}") & (sim_df["round_id"].isin(test_rounds))]
        
        adversaries = {
            "Other HW": other_hw_te,
            "S0 (Ideal)": s0_te,
            "S1 (Calib)": s1_te,
            "S2 (Adaptive)": s2_te,
        }
        
        results[target_b] = {
            "val_threshold": float(val_thresh),
            "genuine_frr": frr,
            "adversaries": {}
        }
        
        for adv_name, adv_df in adversaries.items():
            if adv_df.empty:
                print(f"  vs {adv_name:14s}: NO SAMPLES FOUND")
                continue
            adv_scores = det.compute_anomaly_scores(adv_df[full_feats].values)
            # FAR = proportion of impostor samples with score <= val_thresh
            far = float(np.mean(adv_scores <= val_thresh))
            
            y_eval = np.concatenate([np.zeros(len(gen_te)), np.ones(len(adv_df))])
            scores_eval = np.concatenate([gen_te_scores, adv_scores])
            roc = compute_roc_and_eer(y_eval, scores_eval)
            
            results[target_b]["adversaries"][adv_name] = {
                "roc_auc": float(roc["roc_auc"]),
                "eer": float(roc["eer"]),
                "far": far,
                "frr": frr,
                "adv_mean_score": float(np.mean(adv_scores)),
            }
            print(f"  vs {adv_name:14s}: AUC = {roc['roc_auc']:.4f} | EER = {roc['eer']:.4f} | FAR = {far:.4f} | FRR = {frr:.4f} | AdvScoreMean = {np.mean(adv_scores):.2f}")

    # Check original E4 results.json
    print("\n=== Reconciling with results/metrics/e4_spoofing.json ===")
    e4_path = PROJECT_ROOT / "results" / "metrics" / "e4_spoofing.json"
    if e4_path.exists():
        with open(e4_path) as f:
            e4_data = json.load(f)
        print("Raw e4_spoofing.json contents:")
        print(json.dumps(e4_data, indent=2))

if __name__ == "__main__":
    main()
