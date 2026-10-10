#!/usr/bin/env python3
"""Audit Point 2: Genuine-sample metrics and reconciliation of E5 vs E1."""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.detect import build_integrity_detector
from qfp.metrics import compute_roc_and_eer, compute_far_frr_at_threshold

df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
subsets = get_feature_subsets(df.columns)
full_feats = subsets["full"]

train_rounds = [1, 2, 3, 4, 5]
val_rounds = [6, 7]
test_rounds = [8, 9, 10]

real_df = df[~df["backend"].str.startswith("sim_")].copy()
sim_df = df[df["backend"].str.startswith("sim_")].copy()
real_backends = sorted(real_df["backend"].unique())

print("================================================================================")
print("POINT 2: GENUINE-SAMPLE METRICS PER BACKEND (THRESHOLD FIXED ON VAL ROUNDS 6-7)")
print("================================================================================")

for b in real_backends:
    gen_tr = real_df[(real_df["backend"] == b) & (real_df["round_id"].isin(train_rounds))]
    gen_val = real_df[(real_df["backend"] == b) & (real_df["round_id"].isin(val_rounds))]
    gen_val_r6 = real_df[(real_df["backend"] == b) & (real_df["round_id"] == 6)]
    gen_val_r7 = real_df[(real_df["backend"] == b) & (real_df["round_id"] == 7)]
    gen_te = real_df[(real_df["backend"] == b) & (real_df["round_id"].isin(test_rounds))]
    
    # Train detector ONLY on genuine training rounds
    det = build_integrity_detector("mahalanobis", seed=42)
    det.fit(gen_tr[full_feats].values)
    
    # Fixed threshold calibrated on validation rounds 6-7 at target FPR = 0.05
    thresh = det.calibrate_threshold(gen_val[full_feats].values, target_fpr=0.05)
    
    # Validation scores and FRR
    val_scores = det.compute_anomaly_scores(gen_val[full_feats].values)
    val_r6_scores = det.compute_anomaly_scores(gen_val_r6[full_feats].values)
    val_r7_scores = det.compute_anomaly_scores(gen_val_r7[full_feats].values)
    val_frr = float(np.mean(val_scores > thresh))
    val_r6_frr = float(np.mean(val_r6_scores > thresh))
    val_r7_frr = float(np.mean(val_r7_scores > thresh))
    
    # Test scores and FRR (False Reject Rate on genuine test samples)
    te_scores = det.compute_anomaly_scores(gen_te[full_feats].values)
    te_frr = float(np.mean(te_scores > thresh))
    
    # Per-test-round FRR
    te_r8_scores = det.compute_anomaly_scores(real_df[(real_df["backend"] == b) & (real_df["round_id"] == 8)][full_feats].values)
    te_r9_scores = det.compute_anomaly_scores(real_df[(real_df["backend"] == b) & (real_df["round_id"] == 9)][full_feats].values)
    te_r10_scores = det.compute_anomaly_scores(real_df[(real_df["backend"] == b) & (real_df["round_id"] == 10)][full_feats].values)
    
    frr_r8 = float(np.mean(te_r8_scores > thresh))
    frr_r9 = float(np.mean(te_r9_scores > thresh))
    frr_r10 = float(np.mean(te_r10_scores > thresh))
    
    # Impostors evaluated on test rounds 8-10:
    # 1. Other real hardware backends
    other_hw = real_df[(real_df["backend"] != b) & (real_df["round_id"].isin(test_rounds))]
    # 2. S0, S1, S2 simulators
    s0_imp = sim_df[(sim_df["backend"].str.contains("sim_S0")) & (sim_df["round_id"].isin(test_rounds))]
    s1_imp = sim_df[(sim_df["backend"].str.contains(f"sim_S1_{b}")) & (sim_df["round_id"].isin(test_rounds))]
    s2_imp = sim_df[(sim_df["backend"].str.contains(f"sim_S2_{b}")) & (sim_df["round_id"].isin(test_rounds))]
    all_imp = pd.concat([other_hw, s0_imp, s1_imp, s2_imp])
    
    print(f"\n>>> BACKEND: {b} (Calibrated Threshold on R6-7 = {thresh:.4f})")
    print(f"  Genuine Samples: Train(R1-5)={len(gen_tr)}, Val(R6-7)={len(gen_val)} [R6={len(gen_val_r6)}, R7={len(gen_val_r7)}], Test(R8-10)={len(gen_te)}")
    print(f"  Genuine Validation FRR: Overall={val_frr:.4f} | R6(pre-67.6h gap)={val_r6_frr:.4f} | R7(post-67.6h gap)={val_r7_frr:.4f}")
    print(f"  Genuine Test FRR (False Rejection Rate): Overall(R8-10)={te_frr:.4f} | R8={frr_r8:.4f} | R9={frr_r9:.4f} | R10={frr_r10:.4f}")
    print(f"  Mean Anomaly Score: Train={np.mean(det.compute_anomaly_scores(gen_tr[full_feats].values)):.2f}, R6={np.mean(val_r6_scores):.2f}, R7={np.mean(val_r7_scores):.2f}, R8-10={np.mean(te_scores):.2f}")
    
    # Evaluate against each impostor class and combined impostor pool on test rounds 8-10
    imp_sets = [
        ("Other_Hardware", other_hw),
        ("S0_Ideal", s0_imp),
        ("S1_Calibration", s1_imp),
        ("S2_Adaptive", s2_imp),
        ("Combined_All_Impostors", all_imp),
    ]
    
    print(f"  -- Discrimination Metrics on Test Rounds 8-10 --")
    print(f"  {'Impostor Class':<24} | {'ROC-AUC':<8} | {'EER':<8} | {'TPR@1%FPR':<10} | {'TPR@5%FPR':<10} | {'FAR@ValThresh':<14} | {'FRR@ValThresh':<14}")
    print("  " + "-" * 98)
    for imp_name, imp_data in imp_sets:
        y_true = np.concatenate([np.zeros(len(gen_te)), np.ones(len(imp_data))])
        X_eval = np.concatenate([gen_te[full_feats].values, imp_data[full_feats].values])
        scores = det.compute_anomaly_scores(X_eval)
        
        roc_res = compute_roc_and_eer(y_true, scores)
        far_frr = compute_far_frr_at_threshold(y_true, scores, thresh)
        
        print(
            f"  {imp_name:<24} | {roc_res['roc_auc']:<8.4f} | {roc_res['eer']:<8.4f} | "
            f"{roc_res['tpr_at_1pct_fpr']:<10.4f} | {roc_res['tpr_at_5pct_fpr']:<10.4f} | "
            f"{far_frr['far']:<14.4f} | {far_frr['frr']:<14.4f}"
        )

print("\n================================================================================")
print("RECONCILIATION: E5 OPEN-SET REJECTION (100%) vs E1 CLOSED-SET ACCURACY (44-74%)")
print("================================================================================")
# E5 setup: trained on ibm_fez, tested on ibm_marrakesh (unseen)
det_fez = build_integrity_detector("mahalanobis", seed=42)
fez_tr = real_df[(real_df["backend"] == "ibm_fez") & (real_df["round_id"].isin(train_rounds))]
fez_val = real_df[(real_df["backend"] == "ibm_fez") & (real_df["round_id"].isin(val_rounds))]
fez_te = real_df[(real_df["backend"] == "ibm_fez") & (real_df["round_id"].isin(test_rounds))]

det_fez.fit(fez_tr[full_feats].values)
thresh_fez = det_fez.calibrate_threshold(fez_val[full_feats].values, target_fpr=0.05)

# Test on unseen ibm_marrakesh
mar_te = real_df[(real_df["backend"] == "ibm_marrakesh") & (real_df["round_id"].isin(test_rounds))]
scores_mar_unseen = det_fez.compute_anomaly_scores(mar_te[full_feats].values)
mar_rejection_rate = float(np.mean(scores_mar_unseen > thresh_fez))

# Genuine seen-backend test samples (ibm_fez on its own detector)
scores_fez_seen = det_fez.compute_anomaly_scores(fez_te[full_feats].values)
fez_frr_test = float(np.mean(scores_fez_seen > thresh_fez))

# Also check ibm_kingston on fez detector
scores_king_unseen = det_fez.compute_anomaly_scores(real_df[(real_df["backend"] == "ibm_kingston") & (real_df["round_id"].isin(test_rounds))][full_feats].values)
king_rejection_rate = float(np.mean(scores_king_unseen > thresh_fez))

print(f"Detector Trained on: ibm_fez (Calibrated Val Threshold = {thresh_fez:.4f})")
print(f"  Unseen Backend ibm_marrakesh Rejection Rate: {mar_rejection_rate*100:.1f}% ({mar_rejection_rate:.4f}) [Mean Score = {np.mean(scores_mar_unseen):.2f}]")
print(f"  Unseen Backend ibm_kingston  Rejection Rate: {king_rejection_rate*100:.1f}% ({king_rejection_rate:.4f}) [Mean Score = {np.mean(scores_king_unseen):.2f}]")
print(f"  Genuine Seen Backend (ibm_fez) False-Reject Rate on Test: {fez_frr_test*100:.1f}% ({fez_frr_test:.4f}) [Mean Score = {np.mean(scores_fez_seen):.2f}]")
print(f"  Genuine Seen Backend Acceptance Rate (1 - FRR): {(1 - fez_frr_test)*100:.1f}%")
