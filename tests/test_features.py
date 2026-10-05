"""Unit tests for feature extraction and statistical descriptor validation."""

import numpy as np
import pytest
from qfp.features import (
    compute_chunk_probabilities,
    extract_sample_feature_vector,
    extract_single_circuit_features,
    get_feature_subsets,
)


def test_chunk_probability_normalization():
    counts = {"000": 50, "111": 50}
    p = compute_chunk_probabilities(counts)
    assert len(p) == 8
    assert np.isclose(np.sum(p), 1.0)
    assert np.isclose(p[0], 0.5)  # '000'
    assert np.isclose(p[7], 0.5)  # '111'


def test_single_circuit_feature_properties():
    p = np.zeros(8)
    p[0] = 0.5  # |000>
    p[7] = 0.5  # |111>
    q_ideal = np.zeros(8)
    q_ideal[0] = 0.5
    q_ideal[7] = 0.5
    
    feats = extract_single_circuit_features(p, q_ideal)
    
    # Check probabilities
    assert feats["prob_000"] == 0.5
    assert feats["prob_111"] == 0.5
    
    # GHZ state marginals: each qubit has 50% chance of 1
    assert np.isclose(feats["marginal_q0"], 0.5)
    assert np.isclose(feats["marginal_q1"], 0.5)
    assert np.isclose(feats["marginal_q2"], 0.5)
    
    # Distance to ideal should be 0.0
    assert np.isclose(feats["dist_tvd"], 0.0)
    assert np.isclose(feats["dist_hellinger"], 0.0)
    
    # Entropy: - 2 * (0.5 * log2(0.5)) = 1.0 bit
    assert np.isclose(feats["entropy"], 1.0)


def test_feature_subsets_partitioning():
    cols = [
        "c01_prep_000__prob_000",
        "c01_prep_000__marginal_q0",
        "c01_prep_000__dist_tvd",
        "calib__p1_given_0_q0",
        "calib_prop_t1_q0",
    ]
    subsets = get_feature_subsets(cols)
    assert "c01_prep_000__prob_000" in subsets["histogram_only"]
    assert "calib_prop_t1_q0" in subsets["calibration_properties"]
    assert len(subsets["full"]) == 4  # All output/calib features except hardware props
