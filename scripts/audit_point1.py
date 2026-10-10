#!/usr/bin/env python3
"""Audit Point 1: Artifact audit of perfect results (E2, E4, E5)."""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline
from qfp.detect import build_integrity_detector
from qfp.metrics import compute_roc_and_eer
from sklearn.metrics import accuracy_score, roc_auc_score

df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
subsets = get_feature_subsets(df.columns)
full_feats = subsets["full"]
hist_feats = subsets["histogram_only"]

train_rounds = [1, 2, 3, 4, 5]
val_rounds = [6, 7]
test_rounds = [8, 9, 10]

real_df = df[~df["backend"].str.startswith("sim_")].copy()
sim_df = df[df["backend"].str.startswith("sim_")].copy()
real_backends = sorted(real_df["backend"].unique())

print("=== 1(a) Feature Provenance Confirmation ===")
metadata_leak = [c for c in full_feats if any(k in c.lower() for k in ["round", "timestamp", "transpile", "path", "backend", "elapsed", "provenance", "cal_"])]
print("Features depending on metadata/provenance:", metadata_leak)

print("\n=== 1(b) Re-run E2 (Real vs Sim) ===")
df["is_real"] = (~df["backend"].str.startswith("sim_")).astype(int)
df_tr = df[df["round_id"].isin(train_rounds)]
df_te = df[df["round_id"].isin(test_rounds)]

for feats_name, feats in [("full (196-dim)", full_feats), ("histogram_only (80-dim)", hist_feats)]:
    print(f"-- Feature set: {feats_name} --")
    for m in ["logistic_regression", "random_forest", "svm_rbf"]:
        pipe = create_classifier_pipeline(m, seed=42)
        pipe.fit(df_tr[feats].values, df_tr["is_real"].values)
        preds = pipe.predict(df_te[feats].values)
        if hasattr(pipe, "predict_proba"):
            probs = pipe.predict_proba(df_te[feats].values)[:, 1]
        elif hasattr(pipe, "decision_function"):
            probs = pipe.decision_function(df_te[feats].values)
        else:
            probs = preds
        acc = accuracy_score(df_te["is_real"].values, preds)
        auc = roc_auc_score(df_te["is_real"].values, probs)
        print(f"  {m}: Test Acc = {acc:.4f}, ROC-AUC = {auc:.4f}")

print("\n=== 1(b) Re-run E4 (Spoofing Detection) with histogram_only ===")
for target_b in real_backends:
    print(f"\nTarget backend: {target_b}")
    gen_tr = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(train_rounds))]
    gen_val = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(val_rounds))]
    gen_te = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(test_rounds))]
    
    other_hw_te = real_df[(real_df["backend"] != target_b) & (real_df["round_id"].isin(test_rounds))]
    s0_te = sim_df[(sim_df["backend"].str.contains("sim_S0")) & (sim_df["round_id"].isin(test_rounds))]
    s1_te = sim_df[(sim_df["backend"].str.contains(f"sim_S1_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
    s2_te = sim_df[(sim_df["backend"].str.contains(f"sim_S2_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
    
    for f_name, f_cols in [("full", full_feats), ("histogram_only", hist_feats)]:
        det = build_integrity_detector("mahalanobis", seed=42)
        det.fit(gen_tr[f_cols].values)
        thresh = det.calibrate_threshold(gen_val[f_cols].values, target_fpr=0.05)
        
        print(f"  [{f_name} ({len(f_cols)}-dim)] Mahalanobis Detector (Val Thresh: {thresh:.3f}):")
        for adv_name, adv_df in [("Other_HW", other_hw_te), ("S0_Ideal", s0_te), ("S1_Calib", s1_te), ("S2_Adaptive", s2_te)]:
            y_true = np.concatenate([np.zeros(len(gen_te)), np.ones(len(adv_df))])
            X_eval = np.concatenate([gen_te[f_cols].values, adv_df[f_cols].values])
            scores = det.compute_anomaly_scores(X_eval)
            roc = compute_roc_and_eer(y_true, scores)
            print(f"    vs {adv_name:12s}: ROC-AUC = {roc['roc_auc']:.4f}, EER = {roc['eer']:.4f}")

print("\n=== 1(c) Shot Count and Chunking Consistency ===")
# Verify raw records
for b in real_backends:
    with open(PROJECT_ROOT / "data" / "raw" / b / "round_001.json") as f:
        hw_r = json.load(f)
    with open(PROJECT_ROOT / "data" / "raw" / f"sim_S1_{b}" / "round_001.json") as f:
        sim_r = json.load(f)
    print(f"Backend {b}:")
    print(f"  Hardware: shots_per_circuit={hw_r.get('shots_per_circuit')}, num_chunks={hw_r.get('num_chunks')}")
    print(f"  Sim S1  : shots_per_circuit={sim_r.get('shots_per_circuit')}, num_chunks={sim_r.get('num_chunks')}")
    hw_chunks = [len(hw_r['circuits'][c]['chunks']) for c in hw_r['circuits']]
    sim_chunks = [len(sim_r['circuits'][c]['chunks']) for c in sim_r['circuits']]
    print(f"  Chunk counts per circuit match: {hw_chunks == sim_chunks == [8]*10}")
    # Sample chunk shot count
    hw_c0_shots = sum(hw_r['circuits']['c01_prep_000']['chunks'][0].values())
    sim_c0_shots = sum(sim_r['circuits']['c01_prep_000']['chunks'][0].values())
    print(f"  Sample chunk shot count: HW={hw_c0_shots}, SIM={sim_c0_shots}")

print("\n=== 1(d) Label-Shuffle Controls ===")
rng = np.random.default_rng(42)
# E2 shuffle
y_tr_shuff = rng.permutation(df_tr["is_real"].values)
pipe_shuff = create_classifier_pipeline("random_forest", seed=42)
pipe_shuff.fit(df_tr[hist_feats].values, y_tr_shuff)
probs_shuff = pipe_shuff.predict_proba(df_te[hist_feats].values)[:, 1]
auc_e2_shuff = roc_auc_score(df_te["is_real"].values, probs_shuff)
print(f"E2 Random Forest Label-Shuffle ROC-AUC (histogram_only): {auc_e2_shuff:.4f}")

# E4 shuffle
for target_b in real_backends:
    gen_tr = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(train_rounds))]
    gen_te = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(test_rounds))]
    s1_te = sim_df[(sim_df["backend"].str.contains(f"sim_S1_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
    y_e4 = np.concatenate([np.zeros(len(gen_te)), np.ones(len(s1_te))])
    X_e4 = np.concatenate([gen_te[hist_feats].values, s1_te[hist_feats].values])
    det = build_integrity_detector("mahalanobis", seed=42)
    det.fit(gen_tr[hist_feats].values)
    scores_e4 = det.compute_anomaly_scores(X_e4)
    y_e4_shuff = rng.permutation(y_e4)
    roc_shuff = compute_roc_and_eer(y_e4_shuff, scores_e4)
    print(f"E4 {target_b} vs S1 Label-Shuffle ROC-AUC (histogram_only): {roc_shuff['roc_auc']:.4f}")
