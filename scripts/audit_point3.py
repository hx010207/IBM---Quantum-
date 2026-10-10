#!/usr/bin/env python3
"""Audit Point 3: Confidence Intervals, Resampling, Per-Round Results, Model Primary Designation."""

import pandas as pd
import numpy as np
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline
from qfp.metrics import compute_round_bootstrap_ci
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
subsets = get_feature_subsets(df.columns)
full_feats = subsets["full"]

train_rounds = [1, 2, 3, 4, 5]
val_rounds = [6, 7]
test_rounds = [8, 9, 10]

real_df = df[~df["backend"].str.startswith("sim_")].copy()
real_backends = sorted(real_df["backend"].unique())

df_tr = real_df[real_df["round_id"].isin(train_rounds)]
df_val = real_df[real_df["round_id"].isin(val_rounds)]
df_te = real_df[real_df["round_id"].isin(test_rounds)]

models = ["logistic_regression", "svm_rbf", "random_forest", "gradient_boosting", "mlp"]

print("================================================================================")
print("POINT 3: MODEL PERFORMANCE ACROSS VALIDATION & TEST ROUNDS (NO TEST SELECTION)")
print("================================================================================")

# 1. Validation Performance (to determine which model was designated primary on validation set)
print("\n--- 1. Validation Set (Rounds 6-7) Performance ---")
val_results = {}
for m in models:
    pipe = create_classifier_pipeline(m, seed=42)
    pipe.fit(df_tr[full_feats].values, df_tr["backend"].values)
    val_preds = pipe.predict(df_val[full_feats].values)
    val_acc = accuracy_score(df_val["backend"].values, val_preds)
    val_bal = balanced_accuracy_score(df_val["backend"].values, val_preds)
    val_f1 = f1_score(df_val["backend"].values, val_preds, average="macro")
    val_results[m] = {"acc": val_acc, "bal_acc": val_bal, "f1": val_f1, "pipe": pipe}
    print(f"  {m:<20} | Val Acc = {val_acc:.4f} | Val Balanced Acc = {val_bal:.4f} | Val F1 = {val_f1:.4f}")

primary_model = max(val_results.keys(), key=lambda k: val_results[k]["acc"])
print(f"\n=> PRIMARY MODEL DESIGNATED ON VALIDATION ROUNDS: '{primary_model}' (Val Acc: {val_results[primary_model]['acc']:.4f})")

# 2. Test Set (Rounds 8-10) Overall Performance (All 5 Models)
print("\n--- 2. Overall Test Set (Rounds 8-10) Performance (All 5 Models) ---")
test_results = {}
for m in models:
    pipe = val_results[m]["pipe"]
    te_preds = pipe.predict(df_te[full_feats].values)
    te_acc = accuracy_score(df_te["backend"].values, te_preds)
    te_bal = balanced_accuracy_score(df_te["backend"].values, te_preds)
    te_f1 = f1_score(df_te["backend"].values, te_preds, average="macro")
    
    # Round-level bootstrap
    def eval_acc(d):
        return accuracy_score(d["backend"].values, pipe.predict(d[full_feats].values))
    
    ci_round = compute_round_bootstrap_ci(df_te, eval_acc, rounds=test_rounds, n_bootstraps=500, seed=42)
    
    # Chunk-level bootstrap
    rng = np.random.default_rng(42)
    chunk_scores = []
    for _ in range(500):
        idx = rng.choice(len(df_te), size=len(df_te), replace=True)
        boot_df_chunk = df_te.iloc[idx]
        chunk_scores.append(accuracy_score(boot_df_chunk["backend"].values, pipe.predict(boot_df_chunk[full_feats].values)))
    ci_chunk = {
        "ci_lower": float(np.percentile(chunk_scores, 2.5)),
        "ci_upper": float(np.percentile(chunk_scores, 97.5)),
        "half_width": float((np.percentile(chunk_scores, 97.5) - np.percentile(chunk_scores, 2.5)) / 2.0),
    }
    
    test_results[m] = {
        "acc": te_acc, "bal_acc": te_bal, "f1": te_f1,
        "ci_round": ci_round, "ci_chunk": ci_chunk
    }
    print(
        f"  {m:<20} | Test Acc = {te_acc:.4f} | Bal Acc = {te_bal:.4f} | F1 = {te_f1:.4f} | "
        f"Round-CI = [{ci_round['ci_lower']:.3f}, {ci_round['ci_upper']:.3f}] | "
        f"Chunk-CI = [{ci_chunk['ci_lower']:.3f}, {ci_chunk['ci_upper']:.3f}]"
    )

# 3. Per-Test-Round Breakdown
print("\n--- 3. Per-Round Breakdown on Test Rounds ---")
print(f"  {'Model':<20} | {'Round 8 (Acc)':<14} | {'Round 9 (Acc)':<14} | {'Round 10 (Acc)':<14}")
print("  " + "-" * 66)
for m in models:
    pipe = val_results[m]["pipe"]
    r8_df = df_te[df_te["round_id"] == 8]
    r9_df = df_te[df_te["round_id"] == 9]
    r10_df = df_te[df_te["round_id"] == 10]
    
    acc_r8 = accuracy_score(r8_df["backend"].values, pipe.predict(r8_df[full_feats].values))
    acc_r9 = accuracy_score(r9_df["backend"].values, pipe.predict(r9_df[full_feats].values))
    acc_r10 = accuracy_score(r10_df["backend"].values, pipe.predict(r10_df[full_feats].values))
    print(f"  {m:<20} | {acc_r8:<14.4f} | {acc_r9:<14.4f} | {acc_r10:<14.4f}")

# 4. State exactly what each CI in results.json resamples
print("\n--- 4. Audit of CI Resampling Units in results.json ---")
with open(PROJECT_ROOT / "results" / "results.json") as f:
    res = json.load(f)

print("  E1 (Closed-set identification):")
print("    - Resampling unit: ROUNDS (resampled rounds [8, 9, 10] with replacement using bootstrap_rounds_resample).")
print(f"    - Random Forest Round-CI: [{res['E1_identification']['models']['random_forest']['bootstrap_ci_95']['ci_lower']:.3f}, {res['E1_identification']['models']['random_forest']['bootstrap_ci_95']['ci_upper']:.3f}]")

print("  E3 (Cross-day persistence):")
print("    - Resampling unit in current script: compute_round_bootstrap_ci was called with rounds=[r] (single round).")
print("    - Consequence: Since rounds=[r] has only 1 round, round-level resampling selects [r] on every iteration, returning a degenerate width.")
print("    - Below is the true CHUNK-LEVEL bootstrap CI for each round in E3:")
pipe_e3 = create_classifier_pipeline("random_forest", seed=42)
df_e3_tr = real_df[real_df["round_id"].isin([1, 2])]
pipe_e3.fit(df_e3_tr[full_feats].values, df_e3_tr["backend"].values)
for r in range(3, 11):
    df_r = real_df[real_df["round_id"] == r]
    acc_r = accuracy_score(df_r["backend"].values, pipe_e3.predict(df_r[full_feats].values))
    # Chunk-level bootstrap
    chunk_r_accs = []
    for _ in range(500):
        idx = rng.choice(len(df_r), size=len(df_r), replace=True)
        chunk_r_accs.append(accuracy_score(df_r.iloc[idx]["backend"].values, pipe_e3.predict(df_r.iloc[idx][full_feats].values)))
    ci_low = np.percentile(chunk_r_accs, 2.5)
    ci_high = np.percentile(chunk_r_accs, 97.5)
    print(f"      Round {r:2d} (n=24 chunks): Acc = {acc_r:.4f} | Chunk-level 95% CI = [{ci_low:.4f}, {ci_high:.4f}]")
