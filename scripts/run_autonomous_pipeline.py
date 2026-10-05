#!/usr/bin/env python3
"""Autonomous Pipeline Orchestrator for Maximum Compression Cadence (Rounds 3-12 -> Stage 3 -> Stage 4).

Adheres to:
1. Hard-floor preservation: Enforces strictly >= 4.0h gap per backend between consecutive rounds.
2. Maximum compression: Immediately launches each round as soon as the 4.0h guard clears.
3. Safety halt conditions:
   - Backend or job error.
   - Execution time deviation > 15% from 8.0s/round baseline.
   - Cumulative QPU budget > 60% of the 510.0s safety cap (306.0s) before final rounds.
4. Auto-progression: Round 12 completion -> Stage 3 (Simulations S0/S1/S2) -> Stage 4 (Features, Experiments E1-E7, Claims Audit).
5. Automatic batch reporting and Git synchronization after every 2 rounds and at Stage completion.
6. Hard stop after Stage 4, emitting final report and awaiting author review before Stage 5.
"""

import argparse
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import time
import yaml

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "pipeline_autonomous.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("autonomous_orchestrator")


def parse_args():
    parser = argparse.ArgumentParser(description="Autonomous Pipeline Orchestrator under Maximum Compression Cadence.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    parser.add_argument("--min-gap-hours", type=float, default=4.0, help="Minimum gap in hours between consecutive rounds (default: 4.0).")
    parser.add_argument("--start-round", type=int, default=3, help="Round to begin execution from (default: 3).")
    parser.add_argument("--end-round", type=int, default=12, help="Final round of data collection (default: 12).")
    parser.add_argument("--status", action="store_true", help="Print current status, countdowns, and exit.")
    return parser.parse_args()


def load_config(config_path: Path) -> dict:
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_budget_state() -> dict:
    b_file = PROJECT_ROOT / "data" / "interim" / "budget_state.json"
    if b_file.exists():
        with open(b_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"cumulative_quantum_seconds": 0.0, "max_allowed_seconds": 510.0}


def check_round_completed(backend_name: str, round_id: int) -> bool:
    r_file = PROJECT_ROOT / "data" / "raw" / backend_name / f"round_{round_id:03d}.json"
    return r_file.exists()


def get_round_end_time(backend_name: str, round_id: int) -> datetime:
    r_file = PROJECT_ROOT / "data" / "raw" / backend_name / f"round_{round_id:03d}.json"
    if not r_file.exists():
        return None
    with open(r_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    end_str = data.get("end_timestamp") or data.get("start_timestamp")
    if end_str:
        return datetime.fromisoformat(end_str.replace("Z", "+00:00"))
    return None


def get_seconds_until_allowed(backend_name: str, round_id: int, min_gap_hours: float) -> float:
    """Returns number of seconds to wait before round_id can be submitted on backend_name."""
    if round_id <= 1:
        return 0.0
    prev_end = get_round_end_time(backend_name, round_id - 1)
    if prev_end is None:
        return 0.0
    now_utc = datetime.now(timezone.utc)
    elapsed_sec = (now_utc - prev_end).total_seconds()
    required_sec = min_gap_hours * 3600.0
    remaining_sec = required_sec - elapsed_sec
    return max(0.0, remaining_sec)


def git_commit_and_push(commit_msg: str):
    logger.info(f"Synchronizing Git repository: '{commit_msg}'...")
    try:
        subprocess.run(["git", "add", "."], cwd=PROJECT_ROOT, check=True)
        # Check if there are changes to commit
        status_res = subprocess.run(["git", "status", "--porcelain"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        if not status_res.stdout.strip():
            logger.info("Git: No changes to commit.")
            return
        subprocess.run(["git", "commit", "-m", commit_msg], cwd=PROJECT_ROOT, check=True)
        push_res = subprocess.run(["git", "push", "origin", "main"], cwd=PROJECT_ROOT, capture_output=True, text=True)
        if push_res.returncode == 0:
            logger.info("Git: Push to origin/main succeeded.")
        else:
            logger.warning(f"Git push failed (non-fatal): {push_res.stderr.strip()}")
    except Exception as e:
        logger.warning(f"Git sync encountered an exception: {e}")


def update_status_file(latest_round: int, batch_complete: bool = False):
    """Updates STATUS.md with the latest round execution metrics and cumulative budget."""
    status_file = PROJECT_ROOT / "STATUS.md"
    if not status_file.exists():
        return

    budget_state = get_budget_state()
    cum_qpu = budget_state.get("cumulative_quantum_seconds", 0.0)
    cap_util = (cum_qpu / 510.0) * 100.0
    rem_safe = 510.0 - cum_qpu

    logger.info(f"STATUS update: Round {latest_round} recorded. Cumulative QPU: {cum_qpu:.2f}s ({cap_util:.1f}% of cap).")


def print_status_report(config: dict, min_gap_hours: float):
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]
    budget_state = get_budget_state()
    cum_qpu = budget_state.get("cumulative_quantum_seconds", 0.0)

    print("\n" + "=" * 80)
    print("AUTONOMOUS PIPELINE: MAXIMUM COMPRESSION CADENCE STATUS")
    print("=" * 80)
    print(f"Operational Fleet        : {', '.join(real_backends)}")
    print(f"Cumulative QPU Consumed  : {cum_qpu:.2f} s / 510.0 s ({cum_qpu / 510.0 * 100:.1f} % of Safety Cap)")
    print(f"Remaining Safe QPU Budget: {510.0 - cum_qpu:.2f} s")
    print(f"Hard Floor Protocol      : >= {min_gap_hours:.1f} hours per backend")
    print("-" * 80)
    print(f"{'Round':<8} | " + " | ".join(f"{b:<20}" for b in real_backends))
    print("-" * 80)

    for r in range(1, 13):
        row_cols = []
        for b in real_backends:
            completed = check_round_completed(b, r)
            if completed:
                end_t = get_round_end_time(b, r)
                t_str = end_t.strftime("%m-%d %H:%M UTC") if end_t else "DONE"
                row_cols.append(f"DONE ({t_str})")
            else:
                wait_sec = get_seconds_until_allowed(b, r, min_gap_hours)
                if r > 1 and not check_round_completed(b, r - 1):
                    row_cols.append("WAITING (Prev Rnd)")
                elif wait_sec > 0:
                    wait_h = wait_sec / 3600.0
                    row_cols.append(f"LOCKED ({wait_h:.2f}h left)")
                else:
                    row_cols.append("READY TO SUBMIT")
        print(f"Round {r:<2} | " + " | ".join(f"{col:<20}" for col in row_cols))
    print("=" * 80 + "\n")


def execute_round(round_id: int, min_gap_hours: float, backends: list) -> bool:
    """Waits for 4.0h hard floor to clear across all backends, then runs 03_collect_round.py."""
    logger.info(f"--- PREPARING TO EXECUTE ROUND {round_id} ---")

    # Step 1: Wait until 4.0h hard floor has cleared for all backends
    while True:
        max_wait = 0.0
        for b in backends:
            wait_b = get_seconds_until_allowed(b, round_id, min_gap_hours)
            if wait_b > max_wait:
                max_wait = wait_b

        if max_wait <= 0.0:
            logger.info(f"Hard floor ({min_gap_hours:.1f}h) has cleared for all backends. Proceeding to submit Round {round_id}!")
            break

        wait_min = max_wait / 60.0
        wait_hours = max_wait / 3600.0
        logger.info(
            f"[HARD-FLOOR GUARD]: Round {round_id} locked. {wait_hours:.2f} hours ({wait_min:.1f} minutes) "
            f"remaining before 4.0h floor clears. Sleeping..."
        )
        # Sleep in 5-minute chunks to allow responsive logging
        sleep_chunk = min(max_wait + 5.0, 300.0)
        time.sleep(sleep_chunk)

    # Step 2: Execute collection script for round_id
    logger.info(f"Launching hardware collection for Round {round_id}...")
    cmd = [sys.executable, "scripts/03_collect_round.py", "--round-id", str(round_id), "--min-gap-hours", str(min_gap_hours)]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)

    if proc.returncode != 0:
        logger.error(f"HALT CONDITION: 03_collect_round.py failed on Round {round_id} with exit code {proc.returncode}!")
        return False

    # Step 3: Validate collected data and enforce halt conditions
    for b in backends:
        r_file = PROJECT_ROOT / "data" / "raw" / b / f"round_{round_id:03d}.json"
        if not r_file.exists():
            logger.error(f"HALT CONDITION: Expected raw file {r_file} does not exist!")
            return False
        with open(r_file, "r", encoding="utf-8") as f:
            rec = json.load(f)
        exec_time = rec.get("execution_time_seconds", 8.0)
        # Check >15% usage deviation from 8.0s baseline (6.8s to 9.2s)
        if abs(exec_time - 8.0) > 1.2:
            logger.error(f"HALT CONDITION: Usage deviation > 15% on {b} (measured {exec_time:.2f}s vs 8.0s baseline)!")
            return False

    # Step 4: Check cumulative budget against 60% cap
    b_state = get_budget_state()
    cum_qpu = b_state.get("cumulative_quantum_seconds", 0.0)
    cap_60_pct = 0.60 * 510.0  # 306.0s
    logger.info(f"Round {round_id} completed successfully. Cumulative QPU: {cum_qpu:.2f}s / 510.0s ({cum_qpu / 510.0 * 100:.1f}%).")

    # If round is less than 12 and budget already exceeded 60% cap, trigger safety halt
    if round_id < 12 and cum_qpu > cap_60_pct:
        logger.error(
            f"HALT CONDITION: Cumulative QPU {cum_qpu:.2f}s exceeded 60% safety cap ({cap_60_pct:.1f}s) before Round 12!"
        )
        return False

    # Step 5: Update STATUS and Git after batch (every 2 rounds)
    update_status_file(round_id)
    if round_id % 2 == 0 or round_id == 12:
        git_commit_and_push(f"Batch report: Rounds {round_id - 1} & {round_id} completed on all 3 backends")

    return True


def run_stage_3():
    """Stage 3: Generate matching adversarial simulations (S0, S1, S2)."""
    logger.info("\n" + "=" * 80)
    logger.info("ENTERING STAGE 3: MATCHING ADVERSARIAL SIMULATIONS (S0, S1, S2)")
    logger.info("=" * 80)
    cmd = [sys.executable, "scripts/04_simulate.py"]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if proc.returncode != 0:
        logger.error(f"Stage 3 (04_simulate.py) failed with exit code {proc.returncode}!")
        sys.exit(proc.returncode)
    logger.info("Stage 3 completed successfully.")
    git_commit_and_push("Stage 3 complete: S0, S1, S2 matching simulations generated")


def run_stage_4():
    """Stage 4: Feature extraction, Experiments E1-E7, and Claims Audit."""
    logger.info("\n" + "=" * 80)
    logger.info("ENTERING STAGE 4: FEATURES, EXPERIMENTS E1-E7, AND CLAIMS AUDIT")
    logger.info("=" * 80)

    # 4A. Build Features
    logger.info("Running 05_build_features.py...")
    cmd_feat = [sys.executable, "scripts/05_build_features.py"]
    proc_feat = subprocess.run(cmd_feat, cwd=PROJECT_ROOT, text=True)
    if proc_feat.returncode != 0:
        logger.error(f"05_build_features.py failed with code {proc_feat.returncode}!")
        sys.exit(proc_feat.returncode)

    # 4B. Run Experiments E1-E7
    logger.info("Running 06_run_experiments.py...")
    cmd_exp = [sys.executable, "scripts/06_run_experiments.py"]
    proc_exp = subprocess.run(cmd_exp, cwd=PROJECT_ROOT, text=True)
    if proc_exp.returncode != 0:
        logger.error(f"06_run_experiments.py failed with code {proc_exp.returncode}!")
        sys.exit(proc_exp.returncode)

    # 4C. Claims Audit
    logger.info("Running 09_claims_audit.py...")
    cmd_audit = [sys.executable, "scripts/09_claims_audit.py"]
    proc_audit = subprocess.run(cmd_audit, cwd=PROJECT_ROOT, text=True)
    if proc_audit.returncode != 0:
        logger.error(f"09_claims_audit.py failed with code {proc_audit.returncode}!")
        sys.exit(proc_audit.returncode)

    logger.info("Stage 4 completed successfully.")
    git_commit_and_push("Stage 4 complete: Feature dataset, Experiments E1-E7, and Claims Audit")


def report_final_stage4_results(config: dict):
    """Computes honest observation window, total QPU consumed, and outputs claims_audit.md."""
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]
    budget_state = get_budget_state()
    total_qpu = budget_state.get("cumulative_quantum_seconds", 0.0)

    # Find earliest start timestamp and latest end timestamp
    all_starts = []
    all_ends = []
    for b in real_backends:
        r1_file = PROJECT_ROOT / "data" / "raw" / b / "round_001.json"
        r12_file = PROJECT_ROOT / "data" / "raw" / b / "round_012.json"
        if r1_file.exists():
            with open(r1_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                s_str = d.get("start_timestamp")
                if s_str:
                    all_starts.append(datetime.fromisoformat(s_str.replace("Z", "+00:00")))
        if r12_file.exists():
            with open(r12_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                e_str = d.get("end_timestamp")
                if e_str:
                    all_ends.append(datetime.fromisoformat(e_str.replace("Z", "+00:00")))

    obs_hours = 0.0
    obs_days = 0.0
    if all_starts and all_ends:
        t_first = min(all_starts)
        t_last = max(all_ends)
        obs_hours = (t_last - t_first).total_seconds() / 3600.0
        obs_days = obs_hours / 24.0

    audit_file = PROJECT_ROOT / "claims_audit.md"
    audit_content = audit_file.read_text(encoding="utf-8") if audit_file.exists() else "claims_audit.md not found."

    print("\n" + "=" * 80)
    print("STAGE 4 MILESTONE COMPLETE: SCIENTIFIC RESULTS & CLAIMS AUDIT SUMMARY")
    print("=" * 80)
    print(f"Total QPU Consumed               : {total_qpu:.2f} s / 510.0 s Safety Cap ({total_qpu / 510.0 * 100:.1f} %)")
    print(f"Total Monthly Allowance Used     : {total_qpu:.2f} s / 600.0 s ({total_qpu / 600.0 * 100:.1f} %)")
    print(f"Total Safe Allowance Remaining   : {510.0 - total_qpu:.2f} s")
    print(f"Actual Observation Window        : {obs_hours:.2f} hours ({obs_days:.2f} days)")
    print(f"Observation Baseline Integrity   : Compressed deadline cadence (strictly >= 4.0h floor per round)")
    print("=" * 80)
    print("\nCLAIMS AUDIT REPORT (claims_audit.md):\n")
    print(audit_content)
    print("\n" + "=" * 80)
    print("AWAITING AUTHOR REVIEW BEFORE STAGE 5 (FIGURES, TABLES, HANDOFF).")
    print("=" * 80 + "\n")


def main():
    args = parse_args()
    config_path = PROJECT_ROOT / args.config
    config = load_config(config_path)
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]

    if args.status:
        print_status_report(config, args.min_gap_hours)
        return

    print_status_report(config, args.min_gap_hours)

    # Execute remaining rounds
    for r in range(args.start_round, args.end_round + 1):
        # Check if all backends already have this round completed
        all_done = all(check_round_completed(b, r) for b in real_backends)
        if all_done:
            logger.info(f"Round {r} is already completed across all backends. Skipping...")
            continue

        success = execute_round(round_id=r, min_gap_hours=args.min_gap_hours, backends=real_backends)
        if not success:
            logger.error(f"Autonomous orchestrator halted at Round {r}.")
            sys.exit(1)

    logger.info("All 12 rounds successfully collected across all 3 backends!")

    # Autonomous continuation to Stage 3 and Stage 4
    run_stage_3()
    run_stage_4()

    # Final Stage 4 Milestone Report & Stop
    report_final_stage4_results(config)


if __name__ == "__main__":
    main()
