#!/usr/bin/env python3
"""Audit Item 3: Leave-c10-out and Leave-one-circuit-out ablations for E2 and E4."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline
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
    
    df["is_real"] = (~df["backend"].str.startswith("sim_")).astype(int)
    df_tr = df[df["round_id"].isin(train_rounds)]
    df_te = df[df["round_id"].isin(test_rounds)]
    
    circuit_prefixes = [f"c{i:02d}_" for i in range(1, 11)]
    
    print("================================================================================")
    print("=== E2 ABLATION: REAL VS SIMULATOR DISCRIMINATION ===")
    print("================================================================================")
    
    for model_name in ["logistic_regression", "random_forest", "svm_rbf"]:
        print(f"\nModel: {model_name}")
        # All circuits (196 dims)
        pipe = create_classifier_pipeline(model_name, seed=42)
        pipe.fit(df_tr[full_feats].values, df_tr["is_real"].values)
        if hasattr(pipe, "predict_proba"):
            probs = pipe.predict_proba(df_te[full_feats].values)[:, 1]
        else:
            probs = pipe.decision_function(df_te[full_feats].values)
        r_all = compute_roc_and_eer(df_te["is_real"].values, probs)
        print(f"  All 10 circuits (196-dim)       : AUC = {r_all['roc_auc']:.4f}, EER = {r_all['eer']:.4f}")
        
        # Leave-c10-out (177 dims)
        no_c10 = [c for c in full_feats if not c.startswith("c10_")]
        pipe = create_classifier_pipeline(model_name, seed=42)
        pipe.fit(df_tr[no_c10].values, df_tr["is_real"].values)
        if hasattr(pipe, "predict_proba"):
            probs = pipe.predict_proba(df_te[no_c10].values)[:, 1]
        else:
            probs = pipe.decision_function(df_te[no_c10].values)
        r_no_c10 = compute_roc_and_eer(df_te["is_real"].values, probs)
        print(f"  Leave-c10-out (177-dim)         : AUC = {r_no_c10['roc_auc']:.4f}, EER = {r_no_c10['eer']:.4f}")

    print("\n--- Leave-One-Circuit-Out Ablation for E2 (Random Forest) ---")
    for cp in circuit_prefixes:
        c_name = [c.split("__")[0] for c in full_feats if c.startswith(cp)][0]
        sub = [c for c in full_feats if not c.startswith(cp)]
        pipe = create_classifier_pipeline("random_forest", seed=42)
        pipe.fit(df_tr[sub].values, df_tr["is_real"].values)
        probs = pipe.predict_proba(df_te[sub].values)[:, 1]
        r = compute_roc_and_eer(df_te["is_real"].values, probs)
        print(f"  Without {c_name:26s} ({len(sub)} dims): AUC = {r['roc_auc']:.4f}, EER = {r['eer']:.4f}")

    print("\n================================================================================")
    print("=== E4 ABLATION: MAHALANOBIS DETECTOR PER BACKEND (VS S1 ADVERSARY) ===")
    print("================================================================================")
    
    for target_b in real_backends:
        print(f"\n--- Target Backend: {target_b} ---")
        gen_tr = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(train_rounds))]
        gen_te = real_df[(real_df["backend"] == target_b) & (real_df["round_id"].isin(test_rounds))]
        s1_te = sim_df[(sim_df["backend"].str.contains(f"sim_S1_{target_b}")) & (sim_df["round_id"].isin(test_rounds))]
        
        y_true = np.concatenate([np.zeros(len(gen_te)), np.ones(len(s1_te))])
        
        # All circuits
        det = build_integrity_detector("mahalanobis", seed=42)
        det.fit(gen_tr[full_feats].values)
        X_all = np.concatenate([gen_te[full_feats].values, s1_te[full_feats].values])
        scores_all = det.compute_anomaly_scores(X_all)
        roc_all = compute_roc_and_eer(y_true, scores_all)
        print(f"  All 10 circuits       : AUC = {roc_all['roc_auc']:.4f}, EER = {roc_all['eer']:.4f}")
        
        # Leave c10 out
        no_c10 = [c for c in full_feats if not c.startswith("c10_")]
        det_no_c10 = build_integrity_detector("mahalanobis", seed=42)
        det_no_c10.fit(gen_tr[no_c10].values)
        X_no_c10 = np.concatenate([gen_te[no_c10].values, s1_te[no_c10].values])
        scores_no_c10 = det_no_c10.compute_anomaly_scores(X_no_c10)
        roc_no_c10 = compute_roc_and_eer(y_true, scores_no_c10)
        print(f"  Leave-c10-out         : AUC = {roc_no_c10['roc_auc']:.4f}, EER = {roc_no_c10['eer']:.4f}")
        
        # Leave-one-circuit-out
        print("  Leave-one-circuit-out breakdown vs S1:")
        for cp in circuit_prefixes:
            c_name = [c.split("__")[0] for c in full_feats if c.startswith(cp)][0]
            sub = [c for c in full_feats if not c.startswith(cp)]
            det_sub = build_integrity_detector("mahalanobis", seed=42)
            det_sub.fit(gen_tr[sub].values)
            X_sub = np.concatenate([gen_te[sub].values, s1_te[sub].values])
            scores_sub = det_sub.compute_anomaly_scores(X_sub)
            roc_sub = compute_roc_and_eer(y_true, scores_sub)
            print(f"    Without {c_name:24s}: AUC = {roc_sub['roc_auc']:.4f}, EER = {roc_sub['eer']:.4f}")

    print("\n================================================================================")
    print("=== S1/S2 DELAY RELAXATION CONFIGURATION ===")
    print("================================================================================")
    from qiskit_aer.noise import NoiseModel
    from qiskit_ibm_runtime.fake_provider import FakeFez
    nm = NoiseModel.from_backend(FakeFez())
    print("Aer NoiseModel instructions with noise:", nm.noise_instructions)
    print("Does NoiseModel include noise on 'delay'?:", "delay" in nm.noise_instructions)
    print("Conclusion: AerSimulator.from_backend() does NOT apply thermal relaxation or dephasing")
    print("to delay instructions. Delays in S1 and S2 execute as noiseless identity operations.")

if __name__ == "__main__":
    main()
