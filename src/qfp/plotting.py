"""Publication-grade plotting module for IEEE format figures.

Generates Figures 1 through 12 following strict IEEE visual guidelines:
  - Matplotlib only (deterministic, no external drawing tools)
  - Colorblind-safe palette (Okabe-Ito)
  - IEEE column widths (single column: 3.5 in, double column: 7.16 in)
  - High resolution: 300 DPI PNG + vector PDF
  - Legible typography (labels >= 9pt, ticks >= 8pt)
  - No titles inside figures (captions reserved for LaTeX)
  - Automatic export of raw data source CSV alongside each figure
  - Strict synthetic watermark applied to all figures generated in dry-run mode
"""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import matplotlib
matplotlib.use("Agg")  # Non-interactive backend
import matplotlib.pyplot as plt
import matplotlib.patches as patches
import numpy as np
import pandas as pd


# Colorblind-safe palette (Okabe-Ito)
COLOR_PALETTE = {
    "blue": "#0072B2",
    "vermilion": "#D55E00",
    "bluish_green": "#009E73",
    "orange": "#E69F00",
    "sky_blue": "#56B4E9",
    "reddish_purple": "#CC79A7",
    "yellow": "#F0E442",
    "black": "#000000",
    "gray": "#7F7F7F",
}

CLASS_COLORS = [
    COLOR_PALETTE["blue"],
    COLOR_PALETTE["vermilion"],
    COLOR_PALETTE["bluish_green"],
    COLOR_PALETTE["orange"],
    COLOR_PALETTE["reddish_purple"],
]


def set_ieee_style():
    """Applies clean IEEE style configuration to matplotlib rcParams."""
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9,
        "axes.labelsize": 9,
        "axes.titlesize": 9,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "figure.titlesize": 10,
        "lines.linewidth": 1.5,
        "axes.linewidth": 0.8,
        "grid.linewidth": 0.5,
        "grid.alpha": 0.4,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    })


def apply_synthetic_watermark(ax: plt.Axes):
    """Stamps 'SYNTHETIC - NOT FOR PUBLICATION' prominently across the axes."""
    ax.text(
        0.5, 0.5,
        "SYNTHETIC - NOT FOR PUBLICATION",
        transform=ax.transAxes,
        fontsize=13,
        color="red",
        alpha=0.35,
        ha="center",
        va="center",
        rotation=30,
        weight="bold",
        zorder=100,
    )


def save_figure_and_source(
    fig: plt.Figure,
    df_source: pd.DataFrame,
    fig_name: str,
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Saves PNG (300 dpi), vector PDF, and the corresponding source CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    png_path = output_dir / f"{fig_name}.png"
    pdf_path = output_dir / f"{fig_name}.pdf"
    csv_path = output_dir / f"{fig_name}_source.csv"
    
    fig.tight_layout()
    fig.savefig(png_path, dpi=300)
    fig.savefig(pdf_path)
    plt.close(fig)
    
    df_source.to_csv(csv_path, index=False)


# =========================================================================
# FIGURE GENERATORS (Fig 1 to Fig 12)
# =========================================================================

def plot_fig1_threat_model(output_dir: Path, is_dryrun: bool = False):
    """Fig 1: Experiment pipeline and threat model diagram (matplotlib patches)."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(7.16, 2.8))
    
    # Draw boxes
    boxes = [
        ("IBM Hardware\n(R1, R2, R3)", 0.05, 0.55, 0.22, 0.35, "#D0E1F9", "#0072B2"),
        ("Adversary Simulators\nS0 (Ideal)\nS1 (Calibration)\nS2 (Adaptive)", 0.05, 0.1, 0.22, 0.35, "#FCE5CD", "#D55E00"),
        ("Fixed Circuit Suite\n10 Benchmark Circuits\n(Bell, GHZ, Clifford, Mirror)", 0.35, 0.32, 0.25, 0.45, "#E8F5E9", "#009E73"),
        ("Statistical Feature\nExtraction\n(196 dims)\nMarginals, ZZ, TVD, Entropy", 0.65, 0.52, 0.28, 0.38, "#FFF2CC", "#E69F00"),
        ("Verifier / Integrity\nDetector\n(Mahalanobis, OC-SVM)\nTrust Score in [0, 1]", 0.65, 0.1, 0.28, 0.38, "#F3E5F5", "#CC79A7"),
    ]
    
    for title, x, y, w, h, bg, border in boxes:
        rect = patches.FancyBboxPatch(
            (x, y), w, h, boxstyle="round,pad=0.03",
            fc=bg, ec=border, lw=1.5, zorder=2
        )
        ax.add_patch(rect)
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=8.5, weight="semibold", zorder=3)
        
    # Arrows
    arrow_props = dict(facecolor="#333333", edgecolor="#333333", width=1.0, headwidth=5, shrink=0.05)
    ax.annotate("", xy=(0.35, 0.65), xytext=(0.27, 0.72), arrowprops=arrow_props)
    ax.annotate("", xy=(0.35, 0.42), xytext=(0.27, 0.28), arrowprops=arrow_props)
    ax.annotate("", xy=(0.65, 0.7), xytext=(0.60, 0.55), arrowprops=arrow_props)
    ax.annotate("", xy=(0.79, 0.48), xytext=(0.79, 0.52), arrowprops=arrow_props)

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_df = pd.DataFrame([{"stage": b[0].replace("\n", " "), "type": "architecture_box"} for b in boxes])
    save_figure_and_source(fig, source_df, "fig1_pipeline_threat_model", output_dir, is_dryrun)


def plot_fig2_circuits(output_dir: Path, is_dryrun: bool = False):
    """Fig 2: Benchmark circuit schematics (Bell, GHZ3, Clifford, Mirror)."""
    from qfp.circuits import build_benchmark_circuits
    set_ieee_style()
    circuits = build_benchmark_circuits(seed=42)
    
    fig, axes = plt.subplots(2, 2, figsize=(7.16, 4.0))
    selected = [
        ("c03_bell_01", axes[0, 0], "Circuit 3: Bell (0, 1)"),
        ("c05_ghz_012", axes[0, 1], "Circuit 5: GHZ (0->1->2)"),
        ("c07_clifford_depth8", axes[1, 0], "Circuit 7: Random Clifford (d~8)"),
        ("c09_mirror_depth12", axes[1, 1], "Circuit 9: Mirror Circuit (d~12)"),
    ]
    
    for cid, ax, label in selected:
        qc = circuits[cid]
        try:
            qc.draw(output="mpl", ax=ax, fold=-1)
            ax.set_title(label, fontsize=8.5, pad=3)
        except Exception:
            # Fallback text representation if mpl drawer fails
            ax.text(0.5, 0.5, f"{label}\nOps: {dict(qc.count_ops())}", ha="center", va="center")
            ax.axis("off")
            
        if is_dryrun:
            apply_synthetic_watermark(ax)
            
    source_df = pd.DataFrame([{"circuit_id": cid, "label": label, "ops": str(dict(circuits[cid].count_ops()))} for cid, _, label in selected])
    save_figure_and_source(fig, source_df, "fig2_circuit_suite", output_dir, is_dryrun)


def plot_fig3_output_distributions(
    df: pd.DataFrame,
    circuit_id: str,
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 3: Grouped bar chart comparing output probability distributions across backends and simulators."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(7.16, 3.0))
    
    bitstrings = [f"{i:03b}" for i in range(8)]
    prob_cols = [f"{circuit_id}__prob_{b}" for b in bitstrings]
    
    classes = sorted(df["backend"].unique())
    x = np.arange(len(bitstrings))
    total_width = 0.8
    width = total_width / len(classes)
    
    source_rows = []
    for idx, cls_name in enumerate(classes):
        cls_df = df[df["backend"] == cls_name]
        mean_probs = cls_df[prob_cols].mean().values
        std_probs = cls_df[prob_cols].std().fillna(0).values
        
        offset = (idx - len(classes) / 2.0 + 0.5) * width
        color = CLASS_COLORS[idx % len(CLASS_COLORS)]
        
        ax.bar(
            x + offset, mean_probs, width=width,
            yerr=std_probs, capsize=2, label=cls_name,
            color=color, alpha=0.85, edgecolor="black", linewidth=0.5
        )
        
        for b, mp, sp in zip(bitstrings, mean_probs, std_probs):
            source_rows.append({"backend": cls_name, "bitstring": b, "mean_prob": mp, "std_prob": sp})

    ax.set_xlabel("Measurement Bitstring")
    ax.set_ylabel("Empirical Probability")
    ax.set_xticks(x)
    ax.set_xticklabels([f"|{b}⟩" for b in bitstrings])
    ax.legend(frameon=True, loc="upper right")
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    save_figure_and_source(fig, pd.DataFrame(source_rows), "fig3_output_distributions", output_dir, is_dryrun)


def plot_fig4_pca_embedding(
    df: pd.DataFrame,
    feature_cols: List[str],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 4: 2-D PCA embedding of statistical features colored by backend class."""
    from sklearn.decomposition import PCA
    from sklearn.preprocessing import StandardScaler
    
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    
    X = df[feature_cols].values
    X_scaled = StandardScaler().fit_transform(X)
    pca = PCA(n_components=2, random_state=42)
    Z = pca.fit_transform(X_scaled)
    
    df_plot = df[["backend", "provenance"]].copy()
    df_plot["PC1"] = Z[:, 0]
    df_plot["PC2"] = Z[:, 1]
    
    backends = sorted(df["backend"].unique())
    for idx, b in enumerate(backends):
        b_mask = (df_plot["backend"] == b)
        color = CLASS_COLORS[idx % len(CLASS_COLORS)]
        marker = "o" if "sim" not in b else "^"
        ax.scatter(
            df_plot.loc[b_mask, "PC1"],
            df_plot.loc[b_mask, "PC2"],
            label=b,
            color=color,
            marker=marker,
            alpha=0.75,
            edgecolors="none",
            s=22,
        )

    var1, var2 = pca.explained_variance_ratio_[:2] * 100
    ax.set_xlabel(f"PC1 ({var1:.1f}% var)")
    ax.set_ylabel(f"PC2 ({var2:.1f}% var)")
    ax.legend(frameon=True, loc="best", fontsize=7)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    save_figure_and_source(fig, df_plot, "fig4_pca_embedding", output_dir, is_dryrun)


def plot_fig5_confusion_matrix(
    y_true: List[str],
    y_pred: List[str],
    classes: List[str],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 5: Normalized confusion matrix for closed-set backend identification."""
    from sklearn.metrics import confusion_matrix
    
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    
    cm = confusion_matrix(y_true, y_pred, labels=classes)
    cm_norm = cm.astype(float) / np.maximum(1, cm.sum(axis=1)[:, np.newaxis])
    
    im = ax.imshow(cm_norm, interpolation="nearest", cmap="Blues", vmin=0, vmax=1)
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Normalized Frequency", fontsize=8)
    
    ax.set_xticks(np.arange(len(classes)))
    ax.set_yticks(np.arange(len(classes)))
    ax.set_xticklabels(classes, rotation=35, ha="right", fontsize=7.5)
    ax.set_yticklabels(classes, fontsize=7.5)
    
    # Overlay text annotations with count and percentage
    for i in range(len(classes)):
        for j in range(len(classes)):
            val = cm_norm[i, j]
            cnt = cm[i, j]
            color = "white" if val > 0.5 else "black"
            ax.text(j, i, f"{val:.2f}\n({cnt})", ha="center", va="center", color=color, fontsize=7)
            
    ax.set_xlabel("Predicted Backend")
    ax.set_ylabel("True Backend")
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_rows = []
    for i, c_true in enumerate(classes):
        for j, c_pred in enumerate(classes):
            source_rows.append({"true_backend": c_true, "pred_backend": c_pred, "count": cm[i, j], "normalized": cm_norm[i, j]})
            
    save_figure_and_source(fig, pd.DataFrame(source_rows), "fig5_confusion_matrix", output_dir, is_dryrun)


def plot_fig6_cross_day_persistence(
    time_gaps: List[float],
    accuracies: List[float],
    ci_lowers: List[float],
    ci_uppers: List[float],
    output_dir: Path,
    is_dryrun: bool = False,
    round_gaps: Optional[List[int]] = None,
):
    """Fig 6: Accuracy vs elapsed wall-clock hours with 95% bootstrap confidence bands."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    
    x = np.array(time_gaps)
    y = np.array(accuracies)
    y_low = np.array(ci_lowers)
    y_up = np.array(ci_uppers)
    
    ax.plot(x, y, "o-", color=COLOR_PALETTE["blue"], label="Chronological Test Accuracy")
    ax.fill_between(x, y_low, y_up, color=COLOR_PALETTE["blue"], alpha=0.2, label="95% Bootstrap CI")
    
    ax.set_xlabel("Elapsed Wall-Clock Separation (Hours)")
    ax.set_ylabel("Identification Accuracy")
    ax.set_ylim(0.0, 1.05)
    ax.legend(frameon=True, loc="lower left", fontsize=7.5)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_dict = {"elapsed_hours": x, "accuracy": y, "ci_lower": y_low, "ci_upper": y_up}
    if round_gaps is not None:
        source_dict["round_gap"] = round_gaps
    source_df = pd.DataFrame(source_dict)
    save_figure_and_source(fig, source_df, "fig6_cross_day_persistence", output_dir, is_dryrun)


def plot_fig7_drift_heatmap(
    tvd_df: pd.DataFrame,
    backend_name: str,
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 7: Pairwise Total Variation Distance (TVD) round-to-round drift heatmap."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    
    data = tvd_df.values
    im = ax.imshow(data, cmap="YlOrRd", vmin=0, vmax=max(0.1, np.max(data)))
    cbar = fig.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    cbar.set_label("Mean Circuit TVD", fontsize=8)
    
    rounds = list(tvd_df.columns)
    ax.set_xticks(np.arange(len(rounds)))
    ax.set_yticks(np.arange(len(rounds)))
    ax.set_xticklabels([f"R{r}" for r in rounds], fontsize=8)
    ax.set_yticklabels([f"R{r}" for r in rounds], fontsize=8)
    
    ax.set_xlabel("Round ID")
    ax.set_ylabel("Round ID")
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    save_figure_and_source(fig, tvd_df.reset_index(), f"fig7_drift_heatmap_{backend_name}", output_dir, is_dryrun)


def plot_fig8_roc_curves(
    roc_dict: Dict[str, Tuple[np.ndarray, np.ndarray, float]],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 8: ROC curves for spoofing detection across adversary levels (Other HW, S0, S1, S2)."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.0))
    
    colors = [COLOR_PALETTE["vermilion"], COLOR_PALETTE["blue"], COLOR_PALETTE["orange"], COLOR_PALETTE["bluish_green"]]
    
    source_rows = []
    for idx, (name, (fpr, tpr, auc_val)) in enumerate(roc_dict.items()):
        c = colors[idx % len(colors)]
        ax.plot(fpr, tpr, label=f"{name} (AUC={auc_val:.3f})", color=c, lw=1.5)
        for f, t in zip(fpr, tpr):
            source_rows.append({"adversary": name, "fpr": f, "tpr": t, "auc": auc_val})
            
    ax.plot([0, 1], [0, 1], "k--", lw=1.0, alpha=0.5, label="Random Guess")
    ax.set_xlabel("False Positive Rate (FPR)")
    ax.set_ylabel("True Positive Rate (TPR)")
    ax.set_xlim(-0.02, 1.02)
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=True, loc="lower right", fontsize=7)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    save_figure_and_source(fig, pd.DataFrame(source_rows), "fig8_roc_curves", output_dir, is_dryrun)


def plot_fig9_far_frr_curve(
    thresholds: np.ndarray,
    fars: np.ndarray,
    frrs: np.ndarray,
    eer: float,
    eer_thresh: float,
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 9: False Acceptance Rate (FAR) and False Rejection Rate (FRR) vs threshold."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    
    ax.plot(thresholds, fars, color=COLOR_PALETTE["vermilion"], label="FAR (Impostor Accepted)")
    ax.plot(thresholds, frrs, color=COLOR_PALETTE["blue"], label="FRR (Genuine Rejected)")
    ax.axvline(eer_thresh, color="black", linestyle=":", label=f"EER={eer:.3f}")
    
    ax.set_xlabel("Detector Decision Threshold")
    ax.set_ylabel("Error Rate")
    ax.set_ylim(-0.02, 1.02)
    ax.legend(frameon=True, loc="best", fontsize=7.5)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_df = pd.DataFrame({"threshold": thresholds, "far": fars, "frr": frrs, "eer": eer, "eer_threshold": eer_thresh})
    save_figure_and_source(fig, source_df, "fig9_far_frr_threshold", output_dir, is_dryrun)


def plot_fig10_shots_ablation(
    shot_values: List[int],
    metrics_dict: Dict[str, List[float]],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 10: Performance metrics as a function of shots per sample chunk."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    
    colors = [COLOR_PALETTE["blue"], COLOR_PALETTE["vermilion"], COLOR_PALETTE["bluish_green"]]
    source_rows = []
    
    for idx, (m_name, vals) in enumerate(metrics_dict.items()):
        c = colors[idx % len(colors)]
        ax.plot(shot_values, vals, "o-", label=m_name, color=c)
        for s, v in zip(shot_values, vals):
            source_rows.append({"shots_per_chunk": s, "metric_name": m_name, "value": v})
            
    ax.set_xscale("log", base=2)
    ax.set_xlabel("Shots per Sample Chunk")
    ax.set_ylabel("Metric Value")
    ax.set_ylim(-0.02, 1.05)
    ax.legend(frameon=True, loc="lower right", fontsize=7.5)
    ax.grid(True, linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    save_figure_and_source(fig, pd.DataFrame(source_rows), "fig10_shots_ablation", output_dir, is_dryrun)


def plot_fig11_feature_importance(
    top_features: List[Tuple[str, float]],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 11: Top feature importance ranking."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 3.2))
    
    names = [f[0] for f in top_features][::-1]
    scores = [f[1] for f in top_features][::-1]
    y_pos = np.arange(len(names))
    
    ax.barh(y_pos, scores, color=COLOR_PALETTE["blue"], alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.set_yticks(y_pos)
    ax.set_yticklabels(names, fontsize=7)
    ax.set_xlabel("Relative Importance Score")
    ax.grid(True, axis="x", linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_df = pd.DataFrame({"feature_name": names, "importance_score": scores})
    save_figure_and_source(fig, source_df, "fig11_feature_importance", output_dir, is_dryrun)


def plot_fig12_leakage_comparison(
    models: List[str],
    chrono_accs: List[float],
    leakage_accs: List[float],
    output_dir: Path,
    is_dryrun: bool = False,
):
    """Fig 12: Chronological vs random-split (leakage comparison) accuracy."""
    set_ieee_style()
    fig, ax = plt.subplots(figsize=(3.5, 2.8))
    
    x = np.arange(len(models))
    width = 0.35
    
    ax.bar(x - width / 2, chrono_accs, width, label="Chronological Split", color=COLOR_PALETTE["blue"], alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.bar(x + width / 2, leakage_accs, width, label="Random Split (Leakage)", color=COLOR_PALETTE["vermilion"], alpha=0.85, edgecolor="black", linewidth=0.5)
    
    ax.set_xticks(x)
    ax.set_xticklabels(models, rotation=25, ha="right", fontsize=7.5)
    ax.set_ylabel("Identification Accuracy")
    ax.set_ylim(0, 1.05)
    ax.legend(frameon=True, loc="lower right", fontsize=7)
    ax.grid(True, axis="y", linestyle="--", alpha=0.3)
    
    if is_dryrun:
        apply_synthetic_watermark(ax)
        
    source_df = pd.DataFrame({"model": models, "chronological_accuracy": chrono_accs, "random_leakage_accuracy": leakage_accs})
    save_figure_and_source(fig, source_df, "fig12_leakage_comparison", output_dir, is_dryrun)
