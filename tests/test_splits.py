"""Unit tests for chronological splitting, leakage prevention, and bootstrap resampling."""

import pandas as pd
import pytest
from qfp.splits import (
    SplitLeakageError,
    bootstrap_rounds_resample,
    chronological_split,
    forward_chaining_rounds_cv,
)


def test_chronological_split_zero_overlap():
    rows = []
    for r in range(1, 9):
        for c in range(4):
            rows.append({"round_id": r, "chunk_idx": c, "backend": "b1"})
    df = pd.DataFrame(rows)
    
    train_rounds = [1, 2, 3, 4]
    val_rounds = [5, 6]
    test_rounds = [7, 8]
    
    df_train, df_val, df_test = chronological_split(df, train_rounds, val_rounds, test_rounds)
    
    s_train = set(df_train["round_id"].unique())
    s_val = set(df_val["round_id"].unique())
    s_test = set(df_test["round_id"].unique())
    
    assert s_train == {1, 2, 3, 4}
    assert s_val == {5, 6}
    assert s_test == {7, 8}
    assert len(s_train.intersection(s_val)) == 0
    assert len(s_train.intersection(s_test)) == 0
    assert len(s_val.intersection(s_test)) == 0


def test_detect_leakage_overlap_error():
    df = pd.DataFrame([{"round_id": 1}, {"round_id": 2}])
    with pytest.raises(SplitLeakageError, match="Temporal data leakage detected"):
        chronological_split(df, train_rounds=[1, 2], val_rounds=[2, 3], test_rounds=[4])


def test_forward_chaining_cv():
    folds = forward_chaining_rounds_cv([1, 2, 3, 4], min_train=2)
    assert len(folds) == 2
    assert folds[0] == ([1, 2], [3])
    assert folds[1] == ([1, 2, 3], [4])


def test_round_level_bootstrap():
    rows = []
    for r in [7, 8]:
        for c in range(8):
            rows.append({"round_id": r, "chunk_idx": c, "feat": r * 10 + c})
    df_test = pd.DataFrame(rows)
    
    import numpy as np
    rng = np.random.default_rng(42)
    boot = bootstrap_rounds_resample(df_test, [7, 8], rng)
    
    # Must preserve total number of rounds sampled (2 rounds * 8 chunks = 16 samples)
    assert len(boot) == 16
    assert set(boot["round_id"].unique()).issubset({7, 8})
