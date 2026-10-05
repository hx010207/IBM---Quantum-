#!/usr/bin/env python3
"""Script 08: Generate publication Tables T1 through T5 in CSV and LaTeX formats.

Generates:
  - Table T1: Backends and Physical Layouts
  - Table T2: Dataset Summary (rounds, samples, classes, provenance)
  - Table T3: E1 Closed-Set Identification Metrics (Models x Feature Sets, Mean +/- CI)
  - Table T4: E4 Spoofing Detection Metrics (per Backend & Adversary Level)
  - Table T5: Ablation Studies (Feature Subsets, Shots, and Budget Trade-offs)
"""

import argparse
import json
import logging
from pathlib import Path
import sys
import yaml
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("make_tables")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate Tables T1-T5 in CSV and LaTeX formats.")
    parser.add_argument("--dry-run", action="store_true", help="Generate tables for dry-run evaluation.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    return parser.parse_args()


def save_table(df: pd.DataFrame, table_name: str, tables_dir: Path):
    """Saves DataFrame as CSV and LaTeX tabular."""
    tables_dir.mkdir(parents=True, exist_ok=True)
    csv_path = tables_dir / f"{table_name}.csv"
    tex_path = tables_dir / f"{table_name}.tex"
    
    df.to_csv(csv_path, index=False)
    latex_code = df.to_latex(index=False, escape=False)
    with open(tex_path, "w", encoding="utf-8") as f:
        f.write(latex_code)
    logger.info(f"Saved {table_name} to CSV and LaTeX in {tables_dir}")


def main():
    args = parse_args()
    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    results_dir = Path("dryrun/results") if args.dry_run else Path("results")
    tables_dir = results_dir / "tables"
    tables_dir.mkdir(parents=True, exist_ok=True)

    res_path = results_dir / "results.json"
    if not res_path.exists():
        logger.error(f"Results file {res_path} not found! Run 06_run_experiments.py first.")
        sys.exit(1)

    with open(res_path, "r", encoding="utf-8") as f:
        master_results = json.load(f)

    meta = master_results["metadata"]
    backends_list = config["backends"].get("dryrun_backends" if args.dry_run else "real_backends", [])

    # -------------------------------------------------------------------------
    # Table T1: Backends and Layouts Used
    # -------------------------------------------------------------------------
    t1_rows = []
    for b in backends_list:
        t1_rows.append({
            "Backend Identifier": b["name"],
            "Qubits Used": str(b["layout"]),
            "Topology Topology": "Linear 3-Qubit Chain",
            "Transpiler Optimization Level": 1,
            "Scheduling": "ALAP (delay-aware)",
        })
    df_t1 = pd.DataFrame(t1_rows)
    save_table(df_t1, "table1_backends_layouts", tables_dir)

    # -------------------------------------------------------------------------
    # Table T2: Dataset Summary
    # -------------------------------------------------------------------------
    t2_rows = [
        {"Category": "Total Sample Chunks", "Value": str(meta["total_samples"])},
        {"Category": "Real / Hardware Samples", "Value": str(meta["real_samples"])},
        {"Category": "Simulator Impersonator Samples", "Value": str(meta["sim_samples"])},
        {"Category": "Data Provenance Mode", "Value": meta["mode"]},
        {"Category": "Training Rounds", "Value": str(meta["train_rounds"])},
        {"Category": "Validation Rounds", "Value": str(meta["val_rounds"])},
        {"Category": "Testing Rounds", "Value": str(meta["test_rounds"])},
        {"Category": "Shots per Circuit", "Value": "2048 (8 chunks x 256 shots)"},
        {"Category": "Circuits per Round", "Value": "10 circuits"},
        {"Category": "Feature Dimensionality", "Value": f"{meta['num_features_full']} dimensions"},
    ]
    df_t2 = pd.DataFrame(t2_rows)
    save_table(df_t2, "table2_dataset_summary", tables_dir)

    # -------------------------------------------------------------------------
    # Table T3: E1 Closed-Set Identification Metrics
    # -------------------------------------------------------------------------
    e1_models = master_results["E1_identification"]["models"]
    t3_rows = []
    for m_name, m_data in e1_models.items():
        ci = m_data["bootstrap_ci_95"]
        acc_str = f"{m_data['test_accuracy']:.3f} $\\pm$ {ci['ci_half_width']:.3f}"
        t3_rows.append({
            "Supervised Model": m_name.replace("_", " ").title(),
            "Chronological Accuracy": acc_str,
            "Balanced Accuracy": f"{m_data['test_balanced_accuracy']:.3f}",
            "Macro F1-Score": f"{m_data['test_f1_macro']:.3f}",
            "Bootstrap 95\\% CI": f"[{ci['ci_lower']:.3f}, {ci['ci_upper']:.3f}]",
        })
    df_t3 = pd.DataFrame(t3_rows)
    save_table(df_t3, "table3_e1_models_metrics", tables_dir)

    # -------------------------------------------------------------------------
    # Table T4: E4 Spoofing Detection Metrics
    # -------------------------------------------------------------------------
    t4_rows = []
    e4_data = master_results["E4_spoofing"]
    for b_name, b_info in e4_data.items():
        mah_info = b_info["detectors"]["mahalanobis"]["adversary_metrics"]
        for adv_name, adv_m in mah_info.items():
            t4_rows.append({
                "Target Backend": b_name,
                "Adversary Class": adv_name,
                "ROC-AUC": f"{adv_m['roc_auc']:.3f}",
                "EER": f"{adv_m['eer']:.3f}",
                "TPR @ 1\\% FPR": f"{adv_m['tpr_at_1pct_fpr']:.3f}",
                "TPR @ 5\\% FPR": f"{adv_m['tpr_at_5pct_fpr']:.3f}",
                "FAR (at Val Thresh)": f"{adv_m['far_at_val_thresh']:.3f}",
                "Attack Acceptance Rate": f"{adv_m['attack_acceptance_rate']:.3f}",
            })
    df_t4 = pd.DataFrame(t4_rows)
    save_table(df_t4, "table4_e4_spoofing_metrics", tables_dir)

    # -------------------------------------------------------------------------
    # Table T5: Ablations
    # -------------------------------------------------------------------------
    t5_rows = []
    f_subsets = master_results["E1_identification"]["feature_subsets_comparison"]
    for fset_name, f_info in f_subsets.items():
        t5_rows.append({
            "Ablation Dimension": "Feature Representation",
            "Configuration": fset_name.replace("_", " ").title(),
            "Dimensionality": f_info["num_features"],
            "Accuracy": f"{f_info['test_accuracy']:.3f}",
        })
        
    shots_ab = master_results["E6_ablations"]["shots_ablation"]
    for s, acc, auc in zip(shots_ab["shots"], shots_ab["accuracy"], shots_ab["roc_auc"]):
        t5_rows.append({
            "Ablation Dimension": "Sample Shot Count",
            "Configuration": f"{s} shots / chunk",
            "Dimensionality": 196,
            "Accuracy": f"{acc:.3f} (AUC={auc:.3f})",
        })
    df_t5 = pd.DataFrame(t5_rows)
    save_table(df_t5, "table5_ablations", tables_dir)


if __name__ == "__main__":
    main()
