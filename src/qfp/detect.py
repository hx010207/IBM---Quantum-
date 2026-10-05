"""Integrity anomaly detectors and trust verification engine.

Trained EXCLUSIVELY on genuine real hardware data for a target backend.
All scalers, covariance estimates, and thresholds are calibrated on
training and validation sets; test sets are evaluated out-of-sample.

Detectors:
  1. Mahalanobis Distance Detector
  2. Centroid-TVD Distance Detector
  3. One-Class SVM
  4. Isolation Forest
  5. Mahalanobis Nearest-Neighbour Authenticator (baseline)
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from scipy.spatial.distance import cdist
from sklearn.covariance import LedoitWolf
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM


DETECTOR_NAMES = [
    "mahalanobis",
    "centroid_tvd",
    "one_class_svm",
    "isolation_forest",
    "mahalanobis_nn",
]


class BaseIntegrityDetector:
    """Abstract base class for per-backend integrity detectors."""

    def __init__(self, name: str):
        self.name = name
        self.threshold: float = 0.0
        self.val_score_mean: float = 0.0
        self.val_score_std: float = 1.0
        self.fitted: bool = False

    def fit(self, X_train: np.ndarray) -> "BaseIntegrityDetector":
        raise NotImplementedError

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        """Computes raw anomaly scores (higher score = more anomalous / impostor)."""
        raise NotImplementedError

    def calibrate_threshold(
        self,
        X_val_genuine: np.ndarray,
        target_fpr: float = 0.05,
    ) -> float:
        """Calibrates detection threshold strictly on genuine validation data.
        
        Args:
            X_val_genuine: Validation samples from the genuine backend.
            target_fpr: Desired false positive (false rejection) rate on genuine validation.
            
        Returns:
            Calibrated decision threshold.
        """
        val_scores = self.compute_anomaly_scores(X_val_genuine)
        self.val_score_mean = float(np.mean(val_scores))
        self.val_score_std = float(np.std(val_scores)) if np.std(val_scores) > 1e-6 else 1.0
        
        # Set threshold at the (1 - target_fpr) percentile of genuine validation scores
        self.threshold = float(np.percentile(val_scores, 100.0 * (1.0 - target_fpr)))
        return self.threshold

    def predict(self, X: np.ndarray) -> np.ndarray:
        """Predicts binary label: 1 for genuine (accepted), 0 for impostor/anomaly (rejected)."""
        scores = self.compute_anomaly_scores(X)
        return (scores <= self.threshold).astype(int)

    def compute_trust_scores(self, X: np.ndarray) -> np.ndarray:
        """Maps anomaly scores to a continuous [0, 1] trust confidence score."""
        scores = self.compute_anomaly_scores(X)
        # Sigmoid centered at the calibrated threshold
        z = (scores - self.threshold) / self.val_score_std
        trust = 1.0 / (1.0 + np.exp(np.clip(z, -15.0, 15.0)))
        return trust


class MahalanobisDetector(BaseIntegrityDetector):
    """Integrity detector using Mahalanobis distance to training genuine centroid."""

    def __init__(self, shrinkage: float = 1e-4):
        super().__init__("mahalanobis")
        self.shrinkage = shrinkage
        self.scaler = StandardScaler()
        self.mean_: Optional[np.ndarray] = None
        self.inv_cov_: Optional[np.ndarray] = None

    def fit(self, X_train: np.ndarray) -> "MahalanobisDetector":
        X_scaled = self.scaler.fit_transform(X_train)
        self.mean_ = np.mean(X_scaled, axis=0)
        
        # Robust covariance with Ledoit-Wolf shrinkage
        lw = LedoitWolf(assume_centered=False)
        lw.fit(X_scaled)
        cov = lw.covariance_ + self.shrinkage * np.eye(X_scaled.shape[1])
        self.inv_cov_ = np.linalg.pinv(cov)
        
        self.fitted = True
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        diff = X_scaled - self.mean_
        # d_M^2 = diag(diff @ inv_cov @ diff.T)
        left = diff @ self.inv_cov_
        d_sq = np.sum(left * diff, axis=1)
        return np.sqrt(np.maximum(0.0, d_sq))


class MahalanobisNNDetector(BaseIntegrityDetector):
    """Nearest-Neighbour authenticator using Mahalanobis distance to training exemplars."""

    def __init__(self, shrinkage: float = 1e-4):
        super().__init__("mahalanobis_nn")
        self.shrinkage = shrinkage
        self.scaler = StandardScaler()
        self.X_train_scaled: Optional[np.ndarray] = None
        self.inv_cov_: Optional[np.ndarray] = None

    def fit(self, X_train: np.ndarray) -> "MahalanobisNNDetector":
        self.X_train_scaled = self.scaler.fit_transform(X_train)
        lw = LedoitWolf(assume_centered=False)
        lw.fit(self.X_train_scaled)
        cov = lw.covariance_ + self.shrinkage * np.eye(self.X_train_scaled.shape[1])
        self.inv_cov_ = np.linalg.pinv(cov)
        self.fitted = True
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        # Pairwise Mahalanobis distance to all training samples
        # d(u, v) = sqrt((u-v) inv_cov (u-v)^T)
        # Use transformed coordinates: Z = X @ sqrt(inv_cov)
        u, s, vt = np.linalg.svd(self.inv_cov_)
        sqrt_inv_cov = u @ np.diag(np.sqrt(np.maximum(0, s))) @ vt
        
        Z_test = X_scaled @ sqrt_inv_cov
        Z_train = self.X_train_scaled @ sqrt_inv_cov
        
        dists = cdist(Z_test, Z_train, metric="euclidean")
        min_dists = np.min(dists, axis=1)
        return min_dists


class CentroidTVDDetector(BaseIntegrityDetector):
    """Centroid Total Variation Distance detector over 10 circuit probability distributions."""

    def __init__(self, num_circuits: int = 10):
        super().__init__("centroid_tvd")
        self.num_circuits = num_circuits
        self.circuit_centroids: List[np.ndarray] = []

    def fit(self, X_train: np.ndarray) -> "CentroidTVDDetector":
        # Assumes first 80 columns are the 10 circuit 8-outcome probability vectors
        probs_train = X_train[:, : self.num_circuits * 8]
        self.circuit_centroids = []
        for c in range(self.num_circuits):
            c_p = probs_train[:, c * 8 : (c + 1) * 8]
            centroid = np.mean(c_p, axis=0)
            centroid = centroid / np.sum(centroid)
            self.circuit_centroids.append(centroid)
        self.fitted = True
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        probs = X[:, : self.num_circuits * 8]
        n_samples = len(X)
        tvd_scores = np.zeros(n_samples)
        
        for c in range(self.num_circuits):
            c_p = probs[:, c * 8 : (c + 1) * 8]
            diff = np.abs(c_p - self.circuit_centroids[c])
            tvd_scores += 0.5 * np.sum(diff, axis=1)
            
        return tvd_scores / self.num_circuits


class OneClassSVMDetector(BaseIntegrityDetector):
    """One-Class Support Vector Machine for non-linear genuine support estimation."""

    def __init__(self, nu: float = 0.05):
        super().__init__("one_class_svm")
        self.nu = nu
        self.scaler = StandardScaler()
        self.oc_svm = OneClassSVM(kernel="rbf", gamma="scale", nu=self.nu)

    def fit(self, X_train: np.ndarray) -> "OneClassSVMDetector":
        X_scaled = self.scaler.fit_transform(X_train)
        self.oc_svm.fit(X_scaled)
        self.fitted = True
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        # Decision function is positive for inliers, negative for outliers
        # Negate so higher value indicates higher anomaly
        return -self.oc_svm.decision_function(X_scaled)


class IsolationForestDetector(BaseIntegrityDetector):
    """Isolation Forest ensemble detector."""

    def __init__(self, contamination: float = 0.05, seed: int = 42):
        super().__init__("isolation_forest")
        self.contamination = contamination
        self.seed = seed
        self.scaler = StandardScaler()
        self.ifo = IsolationForest(
            contamination=self.contamination,
            random_state=self.seed,
            n_jobs=-1,
        )

    def fit(self, X_train: np.ndarray) -> "IsolationForestDetector":
        X_scaled = self.scaler.fit_transform(X_train)
        self.ifo.fit(X_scaled)
        self.fitted = True
        return self

    def compute_anomaly_scores(self, X: np.ndarray) -> np.ndarray:
        X_scaled = self.scaler.transform(X)
        return -self.ifo.decision_function(X_scaled)


def build_integrity_detector(name: str, seed: int = 42) -> BaseIntegrityDetector:
    """Factory function for integrity detectors."""
    if name == "mahalanobis":
        return MahalanobisDetector()
    elif name == "mahalanobis_nn":
        return MahalanobisNNDetector()
    elif name == "centroid_tvd":
        return CentroidTVDDetector()
    elif name == "one_class_svm":
        return OneClassSVMDetector()
    elif name == "isolation_forest":
        return IsolationForestDetector(seed=seed)
    else:
        raise ValueError(f"Unknown detector name '{name}'. Allowed: {DETECTOR_NAMES}")
