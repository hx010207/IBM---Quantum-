#!/usr/bin/env python3
"""Audit Item 5: Leakage gap (random vs chronological split) for all five models."""

import sys
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline

def main():
    df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
    subsets = get_feature_subsets(df.columns)
    full_feats = subsets["full"]
    
    # Only real hardware backends
    real_df = df[~df["backend"].str.startswith("sim_")].copy()
    
    train_rounds = [1, 2, 3, 4, 5]
    test_rounds = [8, 9, 10]
    
    # 1. Chronological split
    df_chrono_tr = real_df[real_df["round_id"].isin(train_rounds)].copy()
    df_chrono_te = real_df[real_df["round_id"].isin(test_rounds)].copy()
    
    X_tr_chrono = df_chrono_tr[full_feats].values
    y_tr_chrono = df_chrono_tr["backend"].values
    X_te_chrono = df_chrono_te[full_feats].values
    y_te_chrono = df_chrono_te["backend"].values
    
    # 2. Random chunk-level split (using identical sample sizes)
    # Total samples across rounds 1-5 and 8-10:
    combined_df = real_df[real_df["round_id"].isin(train_rounds + test_rounds)].copy()
    
    # Stratified 50/50 split matching train size (120 train, 72 test)
    # Or train_test_split with test_size = len(df_chrono_te) / len(combined_df) = 72 / 192 = 0.375
    test_frac = len(df_chrono_te) / len(combined_df)
    
    models = ["logistic_regression", "random_forest", "svm_rbf", "gradient_boosting", "mlp"]
    
    print("=== Model Leakage Gap Analysis (Chronological vs Random Split) ===")
    print(f"Sample counts: Chronological Train = {len(df_chrono_tr)}, Test = {len(df_chrono_te)}")
    print(f"Total Combined Pool: {len(combined_df)} samples\n")
    
    results = []
    
    # We run 20 random split trials to report stable mean random accuracy
    n_seeds = 20
    
    for m in models:
        # Chronological
        pipe_chrono = create_classifier_pipeline(m, seed=42)
        pipe_chrono.fit(X_tr_chrono, y_tr_chrono)
        preds_chrono = pipe_chrono.predict(X_te_chrono)
        acc_chrono = accuracy_score(y_te_chrono, preds_chrono)
        bal_chrono = balanced_accuracy_score(y_te_chrono, preds_chrono)
        f1_chrono = f1_score(y_te_chrono, preds_chrono, average="macro")
        
        # Random splits
        rand_accs = []
        rand_bals = []
        rand_f1s = []
        for seed in range(n_seeds):
            tr_idx, te_idx = train_test_split(
                np.arange(len(combined_df)),
                test_size=test_frac,
                stratify=combined_df["backend"].values,
                random_state=42 + seed
            )
            df_rand_tr = combined_df.iloc[tr_idx]
            df_rand_te = combined_df.iloc[te_idx]
            
            pipe_rand = create_classifier_pipeline(m, seed=42)
            pipe_rand.fit(df_rand_tr[full_feats].values, df_rand_tr["backend"].values)
            preds_rand = pipe_rand.predict(df_rand_te[full_feats].values)
            
            rand_accs.append(accuracy_score(df_rand_te["backend"].values, preds_rand))
            rand_bals.append(balanced_accuracy_score(df_rand_te["backend"].values, preds_rand))
            rand_f1s.append(f1_score(df_rand_te["backend"].values, preds_rand, average="macro"))
            
        mean_rand_acc = float(np.mean(rand_accs))
        leakage_gap = mean_rand_acc - acc_chrono
        
        results.append({
            "model": m,
            "chrono_acc": acc_chrono,
            "chrono_bal_acc": bal_chrono,
            "chrono_f1": f1_chrono,
            "rand_acc": mean_rand_acc,
            "rand_acc_std": float(np.std(rand_accs)),
            "leakage_gap": leakage_gap,
        })
        
        print(f"Model: {m:20s}")
        print(f"  Chronological Acc : {acc_chrono:.4f} (Bal: {bal_chrono:.4f}, F1: {f1_chrono:.4f})")
        print(f"  Random Split Acc  : {mean_rand_acc:.4f} +/- {np.std(rand_accs):.4f}")
        print(f"  Leakage Gap (Delta): {leakage_gap:+.4f} ({leakage_gap*100:+.2f} percentage points)\n")

if __name__ == "__main__":
    main()
