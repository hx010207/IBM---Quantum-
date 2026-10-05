"""Supervised machine learning classifiers for backend identification and spoofing classification.

Implements standard scikit-learn models with strict feature scaling fitted
exclusively on training data:
  - Logistic Regression (L2 regularized)
  - Support Vector Classifier (RBF kernel)
  - Random Forest Classifier
  - Histogram-based Gradient Boosting Classifier
  - Multi-Layer Perceptron (small MLP)
"""

from typing import Any, Dict, List, Optional, Tuple, Union
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neural_network import MLPClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC


MODEL_NAMES = [
    "logistic_regression",
    "svm_rbf",
    "random_forest",
    "gradient_boosting",
    "mlp",
]


def create_classifier_pipeline(
    model_name: str,
    seed: int = 42,
    **hyperparams,
) -> Pipeline:
    """Builds a scikit-learn pipeline with StandardScaler and the specified estimator.
    
    Args:
        model_name: Identifier from MODEL_NAMES.
        seed: Random seed for reproducibility.
        **hyperparams: Additional estimator hyperparameters.
        
    Returns:
        Fitted scikit-learn Pipeline.
    """
    if model_name == "logistic_regression":
        clf = LogisticRegression(
            max_iter=1000,
            random_state=seed,
            C=hyperparams.get("C", 1.0),
            solver="lbfgs",
        )
    elif model_name == "svm_rbf":
        clf = SVC(
            kernel="rbf",
            probability=True,
            random_state=seed,
            C=hyperparams.get("C", 1.0),
            gamma=hyperparams.get("gamma", "scale"),
        )
    elif model_name == "random_forest":
        clf = RandomForestClassifier(
            n_estimators=hyperparams.get("n_estimators", 100),
            max_depth=hyperparams.get("max_depth", 8),
            random_state=seed,
            n_jobs=-1,
        )
    elif model_name == "gradient_boosting":
        clf = HistGradientBoostingClassifier(
            max_iter=hyperparams.get("max_iter", 100),
            max_depth=hyperparams.get("max_depth", 6),
            random_state=seed,
        )
    elif model_name == "mlp":
        clf = MLPClassifier(
            hidden_layer_sizes=hyperparams.get("hidden_layer_sizes", (64, 32)),
            max_iter=500,
            random_state=seed,
            early_stopping=False,
        )
    else:
        raise ValueError(f"Unknown model name '{model_name}'. Allowed: {MODEL_NAMES}")

    return Pipeline([
        ("scaler", StandardScaler()),
        ("classifier", clf),
    ])


def compute_feature_importances(
    pipeline: Pipeline,
    feature_names: List[str],
    X_val: Optional[np.ndarray] = None,
    y_val: Optional[np.ndarray] = None,
    n_repeats: int = 10,
    seed: int = 42,
) -> Dict[str, float]:
    """Extracts top feature importance scores using model weights, tree importances, or permutation.
    
    Returns:
        Dict mapping feature name to normalized importance score.
    """
    clf = pipeline.named_steps["classifier"]
    
    if hasattr(clf, "feature_importances_"):
        raw_imp = clf.feature_importances_
    elif hasattr(clf, "coef_"):
        # Mean absolute coefficient across classes
        raw_imp = np.mean(np.abs(clf.coef_), axis=0)
    elif X_val is not None and y_val is not None:
        from sklearn.inspection import permutation_importance
        perm = permutation_importance(pipeline, X_val, y_val, n_repeats=n_repeats, random_state=seed)
        raw_imp = perm.importances_mean
    else:
        raw_imp = np.ones(len(feature_names)) / len(feature_names)

    total = np.sum(raw_imp)
    norm_imp = (raw_imp / total) if total > 0 else raw_imp
    
    return {name: float(imp) for name, imp in zip(feature_names, norm_imp)}
