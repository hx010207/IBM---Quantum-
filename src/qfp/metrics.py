"""Statistical metrics, security verification benchmarks, and bootstrap confidence intervals.

Implements rigorous biometrics/security evaluation metrics:
  - ROC-AUC
  - Equal Error Rate (EER)
  - True Positive Rate at 1% and 5% FPR (TPR@1%FPR, TPR@5%FPR)
  - False Acceptance Rate (FAR) and False Rejection Rate (FRR) at pre-fixed threshold
  - Adversary Attack-Acceptance Rate (AAR) for S0, S1, S2
  - Multi-class Accuracy, Balanced Accuracy, Macro-F1
  - Total Variation Distance (TVD) round-to-round drift
  - 95% Confidence Intervals via round-level bootstrap
"""

from typing import Any, Callable, Dict, List, Optional, Tuple, Union
import numpy as np
import pandas as pd
from scipy.interpolate import interp1d
from scipy.optimize import brentq
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score, roc_auc_score, roc_curve


def compute_roc_and_eer(
    y_true: np.ndarray,
    anomaly_scores: np.ndarray,
) -> Dict[str, float]:
    """Computes ROC-AUC, EER, and operating points (TPR at 1% and 5% FPR).
    
    Convention:
      - y_true: 0 for genuine, 1 for impostor (spoof / attack)
      - anomaly_scores: higher value indicates more likely impostor
      
    Returns:
        Dict with keys: 'roc_auc', 'eer', 'eer_threshold', 'tpr_at_1pct_fpr', 'tpr_at_5pct_fpr'.
    """
    # Guard against single class
    unique_labels = np.unique(y_true)
    if len(unique_labels) < 2:
        return {
            "roc_auc": 0.5,
            "eer": 0.5,
            "eer_threshold": 0.0,
            "tpr_at_1pct_fpr": 0.0,
            "tpr_at_5pct_fpr": 0.0,
        }
        
    fpr, tpr, thresholds = roc_curve(y_true, anomaly_scores, pos_label=1)
    roc_auc = float(roc_auc_score(y_true, anomaly_scores))
    
    # Calculate Equal Error Rate (EER): FPR == 1 - TPR (or FAR == FRR)
    # fnr = 1 - tpr
    fnr = 1.0 - tpr
    idx_eer = np.nanargmin(np.abs(fpr - fnr))
    eer = float((fpr[idx_eer] + fnr[idx_eer]) / 2.0)
    eer_threshold = float(thresholds[idx_eer]) if idx_eer < len(thresholds) else 0.0
    
    # Interpolate TPR at fixed FPR levels
    try:
        # Sort fpr to ensure strictly monotonic for interpolation
        sorted_indices = np.argsort(fpr)
        sorted_fpr = fpr[sorted_indices]
        sorted_tpr = tpr[sorted_indices]
        
        # Deduplicate sorted_fpr
        unique_fpr_idx = np.unique(sorted_fpr, return_index=True)[1]
        dedup_fpr = sorted_fpr[unique_fpr_idx]
        dedup_tpr = sorted_tpr[unique_fpr_idx]
        
        interp_func = interp1d(dedup_fpr, dedup_tpr, kind="linear", bounds_error=False, fill_value=(0.0, 1.0))
        tpr_1pct = float(interp_func(0.01))
        tpr_5pct = float(interp_func(0.05))
    except Exception:
        tpr_1pct = float(tpr[fpr <= 0.01][-1]) if np.any(fpr <= 0.01) else 0.0
        tpr_5pct = float(tpr[fpr <= 0.05][-1]) if np.any(fpr <= 0.05) else 0.0

    return {
        "roc_auc": roc_auc,
        "eer": eer,
        "eer_threshold": eer_threshold,
        "tpr_at_1pct_fpr": tpr_1pct,
        "tpr_at_5pct_fpr": tpr_5pct,
    }


def compute_far_frr_at_threshold(
    y_true: np.ndarray,
    anomaly_scores: np.ndarray,
    threshold: float,
) -> Dict[str, float]:
    """Computes FAR and FRR for a pre-fixed decision threshold.
    
    Threshold rule: score > threshold => classified as impostor (rejected).
    score <= threshold => classified as genuine (accepted).
    
    Args:
        y_true: 0 for genuine, 1 for impostor.
        anomaly_scores: Anomaly score array.
        threshold: Pre-fixed threshold from validation calibration.
    """
    genuine_mask = (y_true == 0)
    impostor_mask = (y_true == 1)
    
    n_genuine = np.sum(genuine_mask)
    n_impostor = np.sum(impostor_mask)
    
    # Genuine rejected: score > threshold
    frr = float(np.sum(anomaly_scores[genuine_mask] > threshold) / n_genuine) if n_genuine > 0 else 0.0
    
    # Impostor accepted: score <= threshold
    far = float(np.sum(anomaly_scores[impostor_mask] <= threshold) / n_impostor) if n_impostor > 0 else 0.0
    
    return {
        "threshold": float(threshold),
        "far": far,
        "frr": frr,
        "n_genuine": int(n_genuine),
        "n_impostor": int(n_impostor),
    }


def compute_adversary_acceptance_rate(
    sim_scores: np.ndarray,
    threshold: float,
) -> float:
    """Computes the Attack-Acceptance Rate (AAR) of a simulated adversary.
    
    Fraction of spoofed samples that fall below the genuine threshold and get accepted.
    """
    if len(sim_scores) == 0:
        return 0.0
    return float(np.mean(sim_scores <= threshold))


def compute_inter_round_tvd_drift(
    df: pd.DataFrame,
    backend_name: str,
    feature_columns: List[str],
) -> pd.DataFrame:
    """Computes the pairwise Total Variation Distance (TVD) between rounds for a backend.
    
    Measures temporal drift across observed rounds.
    """
    b_df = df[df["backend"] == backend_name]
    rounds = sorted(b_df["round_id"].unique())
    n_rounds = len(rounds)
    
    # Isolate probability columns (first 80)
    prob_cols = [c for c in feature_columns if "__prob_" in c][:80]
    
    matrix = np.zeros((n_rounds, n_rounds))
    
    for i, r1 in enumerate(rounds):
        p1 = b_df[b_df["round_id"] == r1][prob_cols].values
        mean_p1 = np.mean(p1, axis=0)
        
        for j, r2 in enumerate(rounds):
            p2 = b_df[b_df["round_id"] == r2][prob_cols].values
            mean_p2 = np.mean(p2, axis=0)
            
            # Average TVD across the 10 circuits
            tvd_total = 0.0
            for c in range(10):
                c_p1 = mean_p1[c * 8 : (c + 1) * 8]
                c_p2 = mean_p2[c * 8 : (c + 1) * 8]
                tvd_total += 0.5 * np.sum(np.abs(c_p1 - c_p2))
            matrix[i, j] = tvd_total / 10.0
            
    return pd.DataFrame(matrix, index=rounds, columns=rounds)


def compute_round_bootstrap_ci(
    df_test: pd.DataFrame,
    eval_fn: Callable[[pd.DataFrame], float],
    rounds: Optional[List[int]] = None,
    n_bootstraps: int = 1000,
    seed: int = 42,
) -> Dict[str, float]:
    """Computes 95% confidence intervals by bootstrapping over rounds.
    
    Args:
        df_test: Test DataFrame.
        eval_fn: Callable that accepts a bootstrapped test DataFrame and returns a scalar metric.
        rounds: List of test round IDs.
        n_bootstraps: Number of bootstrap iterations.
        seed: Random seed.
        
    Returns:
        Dict with 'mean', 'ci_lower', 'ci_upper', 'ci_half_width'.
    """
    from qfp.splits import bootstrap_rounds_resample
    
    if rounds is None:
        rounds = sorted(df_test["round_id"].unique())
        
    rng = np.random.default_rng(seed)
    scores = []
    
    for _ in range(n_bootstraps):
        df_boot = bootstrap_rounds_resample(df_test, rounds, rng)
        try:
            val = eval_fn(df_boot)
            if not np.isnan(val):
                scores.append(val)
        except Exception:
            continue
            
    if not scores:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "ci_half_width": 0.0}
        
    scores = np.array(scores)
    mean_val = float(np.mean(scores))
    ci_lower = float(np.percentile(scores, 2.5))
    ci_upper = float(np.percentile(scores, 97.5))
    half_width = float((ci_upper - ci_lower) / 2.0)
    
    return {
        "mean": mean_val,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper,
        "ci_half_width": half_width,
        "round_independence_note": (
            "Confidence intervals resampled over rounds. Test rounds spaced ~2-3 hours apart "
            "under compressed cadence are not fully independent."
        ),
    }
