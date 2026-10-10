#!/usr/bin/env python3
"""Audit Item 7: Exploratory re-enrollment analysis (fit on rounds 1-7, test on 8-10)."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.detect import build_integrity_detector
from qfp.metrics import compute_roc_and_eer

def main():
    df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
    subsets = get_feature_subsets(df.columns)
    full_feats = subsets["full"]
    
    real_df = df[~df["backend"].str.startswith("sim_")].copy()
    sim_df = df[df["backend"].str.startswith("sim_")].copy()
    real_backends = sorted(real_df["backend"].unique())
    
    test_rounds = [8, 9, 10]
    
    print("================================================================================")
    print("=== EXPLORATORY ANALYSIS: RE-ENROLLMENT ON ROUNDS 1-7 (TEST ON 8-10) ===")
    print("=== (Labeled exploratory: does NOT replace primary train 1-5 results)    ===")
    print("================================================================================")
    
    for target_b in real_backends:
        print(f"\n==================== Target Backend: {target_b} ====================")
        
        # 1. Primary Protocol: Fit on R1-5 (n=40), Val on R6-7 (n=16)
        gen_tr_prim = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin([1, 2, 3, 4, 5]))]
        gen_val_prim = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin([6, 7]))]
        gen_te = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(test_rounds))]
        
        det_prim = build_integrity_detector("mahalanobis", seed=42)
        det_prim.fit(gen_tr_prim[full_feats].values)
        thresh_prim = det_prim.calibrate_threshold(gen_val_prim[full_feats].values, target_fpr=0.05)
        
        scores_te_prim = det_prim.compute_anomaly_scores(gen_te[full_feats].values)
        frr_prim = float(np.mean(scores_te_prim > thresh_prim))
        
        # 2. Re-enrolled Protocol: Fit on R1-7 (n=56), Threshold calibrated at 95th percentile of enrolled (or R6-7)
        gen_tr_reenroll = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(range(1, 8)))]
        det_reenroll = build_integrity_detector("mahalanobis", seed=42)
        det_reenroll.fit(gen_tr_reenroll[full_feats].values)
        
        # Internal calibration threshold (95th percentile of enrolled data, target FPR=0.05)
        thresh_reenroll = det_reenroll.calibrate_threshold(gen_tr_reenroll[full_feats].values, target_fpr=0.05)
        scores_te_reenroll = det_reenroll.compute_anomaly_scores(gen_te[full_feats].values)
        frr_reenroll = float(np.mean(scores_te_reenroll > thresh_reenroll))
        
        print(f"Genuine False Reject Rate (FRR @ 5% FPR threshold):")
        print(f"  Primary Protocol (Enrolled R1-5, Val R6-7) : FRR = {frr_prim:.4f} (Thresh: {thresh_prim:.2f}, Mean Score: {np.mean(scores_te_prim):.2f})")
        print(f"  Re-enrolled Protocol (Enrolled R1-7)        : FRR = {frr_reenroll:.4f} (Thresh: {thresh_reenroll:.2f}, Mean Score: {np.mean(scores_te_reenroll):.2f})")
        print(f"  FRR Reduction via Re-enrollment             : {frr_prim - frr_reenroll:+.4f} ({(frr_prim - frr_reenroll)*100:+.1f} percentage points)")
        
        # Adversaries
        other_hw_te = real_df[(real_df["backend"] != target_b) & (real_df["round_id"].isin(test_rounds))]
        s0_te = sim_df[(sim_df["backend"].str.contains("sim_S0")) & (sim_df["round_id"].isin(test_rounds))]
        s1_te = sim_df[(sim_df["backend"].str.contains(f"sim_S1_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
        s2_te = sim_df[(sim_df["backend"].str.contains(f"sim_S2_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
        
        adversaries = {
            "Other HW": other_hw_te,
            "S0 (Ideal)": s0_te,
            "S1 (Calib)": s1_te,
            "S2 (Adaptive)": s2_te,
        }
        
        print(f"\nAdversary Discrimination Metrics Comparison:")
        print(f"{'Adversary':14s} | {'Primary AUC':11s} | {'Re-enroll AUC':13s} | {'Primary FAR':11s} | {'Re-enroll FAR':13s}")
        print("-" * 72)
        
        for adv_name, adv_df in adversaries.items():
            # Primary
            adv_scores_prim = det_prim.compute_anomaly_scores(adv_df[full_feats].values)
            y_prim = np.concatenate([np.zeros(len(gen_te)), np.ones(len(adv_df))])
            roc_prim = compute_roc_and_eer(y_prim, np.concatenate([scores_te_prim, adv_scores_prim]))
            far_prim = float(np.mean(adv_scores_prim <= thresh_prim))
            
            # Re-enrolled
            adv_scores_reenroll = det_reenroll.compute_anomaly_scores(adv_df[full_feats].values)
            y_reenroll = np.concatenate([np.zeros(len(gen_te)), np.ones(len(adv_df))])
            roc_reenroll = compute_roc_and_eer(y_reenroll, np.concatenate([scores_te_reenroll, adv_scores_reenroll]))
            far_reenroll = float(np.mean(adv_scores_reenroll <= thresh_reenroll))
            
            print(f"{adv_name:14s} | {roc_prim['roc_auc']:11.4f} | {roc_reenroll['roc_auc']:13.4f} | {far_prim:11.4f} | {far_reenroll:13.4f}")

if __name__ == "__main__":
    main()
