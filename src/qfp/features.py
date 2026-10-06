"""Feature extraction pipeline for quantum backend fingerprinting.

Extracts black-box measurement statistical features concatenated across
the 10 benchmark circuits:
  1. Full outcome probability vectors (8 dims/circuit)
  2. Per-qubit marginals (3 dims/circuit)
  3. Parity statistics (1 dim/circuit)
  4. Pairwise ZZ correlators (3 dims/circuit)
  5. Distance to noiseless ideal distribution: TVD, Hellinger, KL (3 dims/circuit)
  6. Shannon entropy (1 dim/circuit)
  7. Readout confusion estimates from |000> and |111> calibration circuits (6 dims)

Also provides baseline feature sets:
  - Histogram-only features (80 dims)
  - Calibration-property features (T1, T2, readout error, gate errors)
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd

from qfp.circuits import CIRCUIT_NAMES, build_benchmark_circuits, compute_ideal_probabilities
from qfp.provenance import enforce_dataframe_provenance, validate_record_provenance

BITSTRINGS_ORDER = [f"{i:03b}" for i in range(8)]  # ['000', '001', '010', '011', '100', '101', '110', '111']


def compute_chunk_probabilities(chunk_counts: Dict[str, int]) -> np.ndarray:
    """Computes normalized 8-element probability array from count dictionary."""
    total_shots = sum(chunk_counts.values())
    if total_shots <= 0:
        return np.ones(8) / 8.0
    return np.array([chunk_counts.get(b, 0) / total_shots for b in BITSTRINGS_ORDER], dtype=np.float64)


def extract_single_circuit_features(
    p: np.ndarray,
    q_ideal: np.ndarray,
) -> Dict[str, float]:
    """Computes all statistical descriptors for a single circuit's measurement distribution.
    
    Args:
        p: Empirical probability vector of length 8.
        q_ideal: Ideal noiseless probability vector of length 8.
        
    Returns:
        Dictionary of extracted statistical features.
    """
    feats = {}
    
    # 1. Outcome probabilities
    for i, b in enumerate(BITSTRINGS_ORDER):
        feats[f"prob_{b}"] = float(p[i])
        
    # 2. Per-qubit marginals P(q_k = 1)
    # Bitstring index 0 is q2, 1 is q1, 2 is q0
    for q in range(3):
        bit_idx = 2 - q
        p_one = sum(p[i] for i, b in enumerate(BITSTRINGS_ORDER) if b[bit_idx] == "1")
        feats[f"marginal_q{q}"] = float(p_one)
        
    # 3. Parity statistics P(odd hamming weight)
    p_odd = sum(p[i] for i, b in enumerate(BITSTRINGS_ORDER) if b.count("1") % 2 == 1)
    feats["parity_odd"] = float(p_odd)
    
    # 4. Pairwise ZZ correlators <Z_i Z_j>
    # Z eigenvalue: 0 -> +1, 1 -> -1. So (-1)**(bit_i + bit_j)
    for q1, q2 in [(0, 1), (1, 2), (0, 2)]:
        idx1, idx2 = 2 - q1, 2 - q2
        zz = sum(p[i] * ((-1) ** (int(b[idx1]) + int(b[idx2]))) for i, b in enumerate(BITSTRINGS_ORDER))
        feats[f"zz_{q1}_{q2}"] = float(zz)
        
    # 5. Distances to ideal distribution
    # Total Variation Distance (TVD)
    tvd = 0.5 * np.sum(np.abs(p - q_ideal))
    feats["dist_tvd"] = float(tvd)
    
    # Hellinger Distance
    hellinger = (1.0 / np.sqrt(2.0)) * np.sqrt(np.sum((np.sqrt(np.clip(p, 0, 1)) - np.sqrt(np.clip(q_ideal, 0, 1))) ** 2))
    feats["dist_hellinger"] = float(hellinger)
    
    # KL Divergence with epsilon smoothing
    eps = 1e-7
    p_smooth = p + eps
    p_smooth /= np.sum(p_smooth)
    q_smooth = q_ideal + eps
    q_smooth /= np.sum(q_smooth)
    kl = np.sum(p_smooth * np.log(p_smooth / q_smooth))
    feats["dist_kl"] = float(kl)
    
    # 6. Shannon Entropy (in bits)
    non_zero_p = p[p > 1e-9]
    entropy = -np.sum(non_zero_p * np.log2(non_zero_p)) if len(non_zero_p) > 0 else 0.0
    feats["entropy"] = float(entropy)
    
    return feats


def extract_sample_feature_vector(
    circuits_data: Dict[str, Any],
    chunk_idx: int,
    ideal_probs: Dict[str, np.ndarray],
    props_snapshot: Optional[Dict[str, Any]] = None,
) -> Dict[str, float]:
    """Builds a complete unified feature dictionary for one sample chunk across all circuits."""
    full_vector: Dict[str, float] = {}
    
    # Concatenate features across all 10 circuits
    for cid in CIRCUIT_NAMES:
        if cid not in circuits_data:
            raise KeyError(f"Missing required circuit '{cid}' in circuits_data.")
            
        chunks = circuits_data[cid]["chunks"]
        if chunk_idx >= len(chunks):
            raise IndexError(f"Chunk index {chunk_idx} exceeds available chunks ({len(chunks)}) for {cid}.")
            
        c_counts = chunks[chunk_idx]
        p = compute_chunk_probabilities(c_counts)
        q_ideal = ideal_probs[cid]
        
        c_feats = extract_single_circuit_features(p, q_ideal)
        for fname, val in c_feats.items():
            full_vector[f"{cid}__{fname}"] = val

    # 7. Global Readout Confusion Estimates from calibration circuits (c01_prep_000 and c02_prep_111)
    for q in range(3):
        # False positive: P(q=1 | 000)
        full_vector[f"calib__p1_given_0_q{q}"] = full_vector[f"c01_prep_000__marginal_q{q}"]
        # False negative: P(q=0 | 111) = 1 - P(q=1 | 111)
        full_vector[f"calib__p0_given_1_q{q}"] = 1.0 - full_vector[f"c02_prep_111__marginal_q{q}"]

    return full_vector


def extract_calibration_property_features(props_snapshot: Optional[Dict[str, Any]]) -> Dict[str, float]:
    """Extracts scalar calibration baseline features (T1, T2, readout error, 2Q gate errors)."""
    calib_feats: Dict[str, float] = {}
    if not props_snapshot:
        return calib_feats
        
    qubit_props = props_snapshot.get("qubit_properties", {})
    for q in [0, 1, 2]:
        qp = qubit_props.get(str(q), {})
        calib_feats[f"calib_prop_t1_q{q}"] = float(qp.get("t1_seconds") or 1e-4)
        calib_feats[f"calib_prop_t2_q{q}"] = float(qp.get("t2_seconds") or 1e-4)
        calib_feats[f"calib_prop_readout_err_q{q}"] = float(qp.get("readout_error") or 0.01)
        
    two_q_errors = props_snapshot.get("two_qubit_gate_errors", {})
    calib_feats["calib_prop_gate_err_0_1"] = float(two_q_errors.get("0_1", {}).get("error", 0.01))
    calib_feats["calib_prop_gate_err_1_2"] = float(two_q_errors.get("1_2", {}).get("error", 0.01))
    
    return calib_feats


def build_dataset_from_raw_records(
    raw_files: List[Path],
    is_dryrun: bool = False,
) -> pd.DataFrame:
    """Parses raw JSON round files into a clean, provenance-enforced Pandas DataFrame.
    
    Args:
        raw_files: List of file paths to raw round JSONs.
        is_dryrun: Whether running in dry-run mode.
        
    Returns:
        pd.DataFrame containing metadata columns (round_id, backend, provenance, chunk_idx)
        and all numeric feature columns.
    """
    logical_circuits = build_benchmark_circuits(seed=42)
    ideal_probs = compute_ideal_probabilities(logical_circuits)
    
    rows = []
    for fpath in sorted(raw_files):
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
            
        validate_record_provenance(data, is_dryrun=is_dryrun)
        
        round_id = data["round_id"]
        backend = data["backend"]
        provenance = data["provenance"]
        num_chunks = data.get("num_chunks", 8)
        props_snapshot = data.get("properties_snapshot")
        circuits_data = data["circuits"]
        adversary_level = data.get("adversary_level", "real")
        target_backend = data.get("target_backend", backend)
        
        calib_prop_features = extract_calibration_property_features(props_snapshot)
        
        for c_idx in range(num_chunks):
            feat_vec = extract_sample_feature_vector(
                circuits_data,
                chunk_idx=c_idx,
                ideal_probs=ideal_probs,
                props_snapshot=props_snapshot,
            )
            
            row = {
                "round_id": round_id,
                "backend": backend,
                "target_backend": target_backend,
                "adversary_level": adversary_level,
                "provenance": provenance,
                "transpile_path": data.get("transpile_path", "alap"),
                "chunk_idx": c_idx,
                "sample_id": f"{backend}_r{round_id:03d}_c{c_idx:02d}",
            }
            row.update(feat_vec)
            row.update(calib_prop_features)
            rows.append(row)

    df = pd.DataFrame(rows)
    enforce_dataframe_provenance(df, is_dryrun=is_dryrun)
    return df


def get_feature_subsets(all_columns: List[str]) -> Dict[str, List[str]]:
    """Partitions feature column names into canonical subsets for ablation experiments.
    
    Subsets:
      - 'full': all statistical output features + calibration readout confusion
      - 'histogram_only': outcome probability vectors only (8 dims x 10 circuits = 80 dims)
      - 'calibration_properties': T1, T2, readout error, 2Q gate error baseline
      - 'marginal_and_correlators': per-qubit marginals, parities, and ZZ correlators
      - 'information_distances': TVD, Hellinger, KL, and entropy
    """
    subsets = {
        "full": [],
        "histogram_only": [],
        "calibration_properties": [],
        "marginal_and_correlators": [],
        "information_distances": [],
    }
    
    for col in all_columns:
        if col.startswith("calib_prop_"):
            subsets["calibration_properties"].append(col)
        elif "__prob_" in col:
            subsets["histogram_only"].append(col)
            subsets["full"].append(col)
        elif any(k in col for k in ["marginal_", "parity_", "zz_"]):
            subsets["marginal_and_correlators"].append(col)
            subsets["full"].append(col)
        elif any(k in col for k in ["dist_", "entropy"]):
            subsets["information_distances"].append(col)
            subsets["full"].append(col)
        elif col.startswith("calib__"):
            subsets["full"].append(col)

    return subsets
