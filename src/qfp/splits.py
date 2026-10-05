"""Chronological and leakage split partitions with round-level bootstrapping.

Strictly enforces round-level chronological partitioning to avoid data leakage:
  - Training: early rounds (e.g. rounds 1..4)
  - Validation: intermediate rounds (e.g. rounds 5..6, used for threshold & hyperparameter tuning)
  - Testing: final rounds (e.g. rounds 7..8, touched only once)
  
Also implements forward-chaining time-series cross-validation within training rounds,
and round-level bootstrap resampling for 95% confidence intervals.
"""

from typing import Dict, Generator, List, Optional, Tuple
import numpy as np
import pandas as pd


class SplitLeakageError(ValueError):
    """Raised when round overlap or temporal leakage is detected across split partitions."""
    pass


def chronological_split(
    df: pd.DataFrame,
    train_rounds: List[int],
    val_rounds: List[int],
    test_rounds: List[int],
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Partitions a DataFrame into chronological Train, Validation, and Test sets by round_id.
    
    Args:
        df: DataFrame containing a 'round_id' column.
        train_rounds: List of round integers for training.
        val_rounds: List of round integers for validation and threshold calibration.
        test_rounds: List of round integers for final evaluation.
        
    Returns:
        Tuple of (df_train, df_val, df_test).
        
    Raises:
        SplitLeakageError: If any round_id appears in more than one partition.
    """
    s_train = set(train_rounds)
    s_val = set(val_rounds)
    s_test = set(test_rounds)
    
    # Assert zero overlap
    overlap_tv = s_train.intersection(s_val)
    overlap_tt = s_train.intersection(s_test)
    overlap_vt = s_val.intersection(s_test)
    
    if overlap_tv or overlap_tt or overlap_vt:
        raise SplitLeakageError(
            f"Temporal data leakage detected! Round overlap across splits: "
            f"train/val overlap={overlap_tv}, train/test overlap={overlap_tt}, val/test overlap={overlap_vt}"
        )
        
    df_train = df[df["round_id"].isin(s_train)].copy()
    df_val = df[df["round_id"].isin(s_val)].copy()
    df_test = df[df["round_id"].isin(s_test)].copy()
    
    df_train["split_partition"] = "train"
    df_val["split_partition"] = "val"
    df_test["split_partition"] = "test"
    
    return df_train, df_val, df_test


def forward_chaining_rounds_cv(
    train_rounds: List[int],
    min_train: int = 2,
) -> List[Tuple[List[int], List[int]]]:
    """Generates forward-chaining rolling folds strictly within the training set.
    
    For example, if train_rounds = [1, 2, 3, 4] with min_train=2:
      Fold 1: train=[1, 2], val=[3]
      Fold 2: train=[1, 2, 3], val=[4]
      
    Args:
        train_rounds: Sorted list of training round IDs.
        min_train: Minimum number of rounds to start training window.
        
    Returns:
        List of (fold_train_rounds, fold_val_rounds).
    """
    sorted_rounds = sorted(train_rounds)
    folds = []
    for i in range(min_train, len(sorted_rounds)):
        f_train = sorted_rounds[:i]
        f_val = [sorted_rounds[i]]
        folds.append((f_train, f_val))
    return folds


def random_leakage_split(
    df: pd.DataFrame,
    train_ratio: float = 0.5,
    val_ratio: float = 0.25,
    test_ratio: float = 0.25,
    seed: int = 42,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Generates a chunk-level random split across rounds to explicitly quantify leakage.
    
    Used strictly as a labeled negative comparison in Fig 12 and Table T3.
    """
    rng = np.random.default_rng(seed)
    shuffled_indices = rng.permutation(len(df))
    
    n_train = int(len(df) * train_ratio)
    n_val = int(len(df) * val_ratio)
    
    idx_train = shuffled_indices[:n_train]
    idx_val = shuffled_indices[n_train : n_train + n_val]
    idx_test = shuffled_indices[n_train + n_val :]
    
    df_train = df.iloc[idx_train].copy()
    df_val = df.iloc[idx_val].copy()
    df_test = df.iloc[idx_test].copy()
    
    df_train["split_partition"] = "random_train_leakage"
    df_val["split_partition"] = "random_val_leakage"
    df_test["split_partition"] = "random_test_leakage"
    
    return df_train, df_val, df_test


def bootstrap_rounds_resample(
    df: pd.DataFrame,
    rounds: List[int],
    rng: np.random.Generator,
) -> pd.DataFrame:
    """Resamples complete rounds with replacement to compute valid 95% bootstrap CIs.
    
    Resampling is performed at the round level (not sample level) because chunks
    within a round share calibration state and environmental noise.
    
    Args:
        df: DataFrame containing samples.
        rounds: Base list of round IDs.
        rng: Initialized NumPy random generator.
        
    Returns:
        Bootstrapped DataFrame consisting of concatenated chunk samples from resampled rounds.
    """
    n_rounds = len(rounds)
    if n_rounds == 0:
        return df.iloc[0:0].copy()
        
    sampled_rounds = rng.choice(rounds, size=n_rounds, replace=True)
    
    boot_dfs = []
    for r in sampled_rounds:
        r_df = df[df["round_id"] == r]
        boot_dfs.append(r_df)
        
    return pd.concat(boot_dfs, ignore_index=True)
