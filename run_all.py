#!/usr/bin/env python3
"""Cross-platform pipeline execution script (run_all.py).

Reproduces all pipeline stages seamlessly across Windows PowerShell, Linux, and macOS:
  1. Executes pytest suite
  2. Runs discovery / fake selection (01)
  3. Runs budget probe (02)
  4. Collects experimental rounds (03)
  5. Generates S0, S1, S2 simulations (04)
  6. Builds feature representation (05)
  7. Runs evaluations E1-E7 (06)
  8. Generates Figures 1-12 (07)
  9. Generates Tables T1-T5 (08)
 10. Produces Claims Audit (09)
"""

import argparse
import subprocess
import sys


def run_step(cmd_list, desc):
    print(f"\n>>> Running: {desc}...")
    res = subprocess.run(cmd_list)
    if res.returncode != 0:
        print(f"FAILED: {desc} exited with code {res.returncode}")
        sys.exit(res.returncode)
    print(f"DONE: {desc}")


def main():
    parser = argparse.ArgumentParser(description="Reproduce complete QFP pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Execute complete pipeline in dry-run mode.")
    parser.add_argument("--skip-collection", action="store_true", help="Skip data collection and start from features.")
    args = parser.parse_args()

    py = sys.executable

    # 1. Run unit tests
    run_step([py, "-m", "pytest", "tests/"], "Unit Tests")

    dry_flag = ["--dry-run"] if args.dry_run else []

    if not args.skip_collection:
        # 2. Select backends
        run_step([py, "scripts/01_select_backends.py"] + dry_flag, "Backend Selection")

        # 3. Budget probe
        run_step([py, "scripts/02_budget_probe.py"] + dry_flag, "Budget Probe")

        # 4. Collect rounds (target 8 rounds)
        for r in range(1, 9):
            run_step([py, "scripts/03_collect_round.py", "--round-id", str(r)] + dry_flag, f"Collect Round {r}")

        # 5. Generate simulations S0, S1, S2
        run_step([py, "scripts/04_simulate.py", "--rounds", "8"] + dry_flag, "Simulate Adversaries (S0, S1, S2)")

    # 6. Build features
    run_step([py, "scripts/05_build_features.py"] + dry_flag, "Feature Extraction")

    # 7. Run experiments
    run_step([py, "scripts/06_run_experiments.py"] + dry_flag, "Run Experiments E1-E7")

    # 8. Generate figures
    run_step([py, "scripts/07_make_figures.py"] + dry_flag, "Generate Figures 1-12")

    # 9. Generate tables
    run_step([py, "scripts/08_make_tables.py"] + dry_flag, "Generate Tables T1-T5")

    # 10. Claims audit
    run_step([py, "scripts/09_claims_audit.py"] + dry_flag, "Empirical Claims Audit")

    print("\n============================================================")
    print("PIPELINE EXECUTION COMPLETE AND FULLY REPRODUCED!")
    print("============================================================\n")


if __name__ == "__main__":
    main()
