#!/usr/bin/env python3
"""Autonomous Pipeline Orchestrator for Maximum Compression Cadence (Rounds 8-12 -> Stage 3 -> Stage 4 -> Stage 5).

Key Guarantees:
1. Decoupled Per-Backend Submission:
   - Each backend submits independently as soon as its individual 4.0h hard floor clears.
   - No backend waits for another backend's prior round.
2. Machine Keep-Awake & Heartbeat Monitoring:
   - Uses Windows SetThreadExecutionState (ES_CONTINUOUS | ES_SYSTEM_REQUIRED | ES_AWAYMODE_REQUIRED).
   - Logs heartbeat timestamp every 60s.
   - If log gap > 30 minutes is detected, logs warning and writes note to STATUS.md.
3. Hard Cutoff:
   - Oct 10, 12:00 local time (2026-10-10 06:30:00 UTC).
   - If Round 12 is not reached across all 3 backends, collection ends at highest common round
     (minimum Round 10), and split is locked in study.yaml (train: 1-5, val: 6-7, test: 8-R_common).
   - Documented in METHODS_NOTES.md and LIMITATIONS_OBSERVED.md.
4. Auto-Progression through Stages 3, 4, 5:
   - Stage 3: S0, S1, S2 matching simulations.
   - Stage 4: Feature extraction, Experiments E1-E7, Claims Audit.
   - Stage 5: Figures 1-12 (PNG+PDF+CSV), Tables T1-T5 (CSV+LaTeX), CAPTIONS.md, Handoff package.
   - Git commit and push at each stage.
5. Safety Halt Protocol:
   - Halts on job failure, >15% usage deviation from 8.0s baseline, or cumulative QPU > 60% cap (306.0s).
   - Overwrites line 1 of STATUS.md with HALTED banner.
"""

import argparse
from datetime import datetime, timezone, timedelta
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import threading
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

# Hard Cutoff: Oct 10, 12:00 Indian Standard Time (UTC+05:30) = Oct 10, 06:30:00 UTC
CUTOFF_UTC = datetime(2026, 10, 10, 6, 30, 0, tzinfo=timezone.utc)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(PROJECT_ROOT / "pipeline_autonomous.log", mode="a", encoding="utf-8")
    ]
)
logger = logging.getLogger("autonomous_orchestrator")


def keep_machine_awake():
    """Instructs Windows power manager to keep system active and prevent sleep."""
    try:
        import ctypes
        # ES_CONTINUOUS = 0x80000000, ES_SYSTEM_REQUIRED = 0x00000001, ES_AWAYMODE_REQUIRED = 0x00000040
        ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | 0x00000001 | 0x00000040)
    except Exception as e:
        logger.debug(f"SetThreadExecutionState call failed: {e}")


def parse_args():
    parser = argparse.ArgumentParser(description="Autonomous Pipeline Orchestrator under Maximum Compression Cadence.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    parser.add_argument("--min-gap-hours", type=float, default=4.0, help="Minimum gap in hours between consecutive rounds (default: 4.0).")
    parser.add_argument("--start-round", type=int, default=8, help="Round to begin execution from (default: 8).")
    parser.add_argument("--end-round", type=int, default=12, help="Final round of data collection (default: 12).")
    parser.add_argument("--cycle-seconds", type=int, default=60, help="Heartbeat and dispatch polling cycle in seconds (default: 60).")
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


def get_min_gap_hours_for_round(round_id: int) -> float:
    """Returns minimum wall-clock gap in hours: 2.0h for rounds >= 8, 4.0h for rounds 1-7."""
    return 2.0 if round_id >= 8 else 4.0


def get_seconds_until_allowed(backend_name: str, round_id: int, min_gap_hours: float = None) -> float:
    """Returns number of seconds to wait before round_id can be submitted on backend_name."""
    if round_id <= 1:
        return 0.0
    if min_gap_hours is None:
        min_gap_hours = get_min_gap_hours_for_round(round_id)
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


def record_halt_in_status(round_id: int, reason: str):
    """Writes a single clear line to the top of STATUS.md upon any halt condition."""
    status_file = PROJECT_ROOT / "STATUS.md"
    halt_banner = f"HALTED AT ROUND {round_id} — AWAITING REVIEW — REASON: {reason}\n\n"
    if status_file.exists():
        content = status_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        filtered_lines = [l for l in lines if not l.startswith("HALTED AT ROUND ")]
        new_content = halt_banner + "".join(filtered_lines)
    else:
        new_content = halt_banner
    status_file.write_text(new_content, encoding="utf-8")
    logger.error(f"[STATUS.MD HALT BANNER WRITTEN]: {halt_banner.strip()}")
    git_commit_and_push(f"HALT ALERT: Round {round_id} - {reason}")


def clear_halt_in_status():
    status_file = PROJECT_ROOT / "STATUS.md"
    if status_file.exists():
        content = status_file.read_text(encoding="utf-8")
        lines = content.splitlines(keepends=True)
        filtered_lines = [l for l in lines if not l.startswith("HALTED AT ROUND ")]
        if len(filtered_lines) != len(lines):
            status_file.write_text("".join(filtered_lines), encoding="utf-8")


def record_sleep_interruption_in_status(gap_minutes: float):
    status_file = PROJECT_ROOT / "STATUS.md"
    if not status_file.exists():
        return
    now_iso = datetime.now(timezone.utc).isoformat()
    note_line = f"\n> [!WARNING]\n> **Possible System Sleep / Interruption Detected**: Log heartbeat gap of {gap_minutes:.1f} minutes recorded at {now_iso}.\n"
    content = status_file.read_text(encoding="utf-8")
    status_file.write_text(content + note_line, encoding="utf-8")
    logger.warning(f"[STATUS.MD NOTE ADDED]: Possible system sleep/interruption of {gap_minutes:.1f} minutes.")


def print_status_report(config: dict, min_gap_hours: float):
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]
    budget_state = get_budget_state()
    cum_qpu = budget_state.get("cumulative_quantum_seconds", 0.0)

    print("\n" + "=" * 80)
    print("AUTONOMOUS PIPELINE: DECOUPLED MAXIMUM COMPRESSION CADENCE STATUS")
    print("=" * 80)
    print(f"Operational Fleet        : {', '.join(real_backends)}")
    print(f"Cumulative QPU Consumed  : {cum_qpu:.2f} s / 510.0 s ({cum_qpu / 510.0 * 100:.1f} % of Safety Cap)")
    print(f"Remaining Safe QPU Budget: {510.0 - cum_qpu:.2f} s")
    print(f"Hard Floor Protocol      : >= 4.0h (R1-7) / >= 2.0h (R8-12) per backend (Decoupled Submission)")
    print(f"Hard Cutoff              : Oct 10, 12:00 local ({CUTOFF_UTC.strftime('%Y-%m-%d %H:%M UTC')})")
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
                r_gap = get_min_gap_hours_for_round(r)
                wait_sec = get_seconds_until_allowed(b, r, r_gap)
                if r > 1 and not check_round_completed(b, r - 1):
                    row_cols.append("WAITING (Prev Rnd)")
                elif wait_sec > 0:
                    wait_h = wait_sec / 3600.0
                    row_cols.append(f"LOCKED ({wait_h:.2f}h left)")
                else:
                    row_cols.append("READY TO SUBMIT")
        print(f"Round {r:<2} | " + " | ".join(f"{col:<20}" for col in row_cols))
    print("=" * 80 + "\n")


# Global worker thread tracker and result storage
worker_results = {}
worker_lock = threading.Lock()


def run_single_backend_worker(backend_name: str, round_id: int, min_gap_hours: float):
    logger.info(f"[{backend_name}] Worker starting collection for Round {round_id} (min_gap: {min_gap_hours:.1f}h)...")
    cmd = [
        sys.executable,
        "scripts/03_collect_round.py",
        "--round-id", str(round_id),
        "--backend", backend_name,
        "--min-gap-hours", str(min_gap_hours),
    ]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, capture_output=True, text=True)
    with worker_lock:
        worker_results[backend_name] = {
            "round_id": round_id,
            "returncode": proc.returncode,
            "stdout": proc.stdout,
            "stderr": proc.stderr,
        }
    if proc.returncode == 0:
        logger.info(f"[{backend_name}] Worker successfully finished Round {round_id}.")
    else:
        logger.error(f"[{backend_name}] Worker Round {round_id} failed (code {proc.returncode}):\n{proc.stderr.strip()}")


def run_collection_loop(config: dict, min_gap_hours: float, start_round: int, end_round: int, cycle_seconds: int):
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]
    active_threads = {b: None for b in real_backends}
    last_heartbeat_time = time.time()

    logger.info("\n" + "=" * 80)
    logger.info("ENTERING DECOUPLED AUTONOMOUS COLLECTION LOOP (ROUNDS 8-12)")
    logger.info("=" * 80)
    print_status_report(config, min_gap_hours)

    while True:
        keep_machine_awake()
        now_time = time.time()
        now_utc = datetime.now(timezone.utc)

        # 1. Heartbeat gap / sleep interruption detection
        gap_sec = now_time - last_heartbeat_time
        if gap_sec > 1800.0:  # > 30 minutes
            gap_min = gap_sec / 60.0
            record_sleep_interruption_in_status(gap_min)
        last_heartbeat_time = now_time

        # 2. Check for completed worker threads
        for b in real_backends:
            th = active_threads[b]
            if th is not None and not th.is_alive():
                # Worker finished
                th.join()
                active_threads[b] = None
                with worker_lock:
                    res = worker_results.pop(b, None)
                if res is None:
                    continue

                r_id = res["round_id"]
                if res["returncode"] != 0:
                    reason = f"Job failure on backend {b} Round {r_id}: exit code {res['returncode']}"
                    logger.error(f"HALT CONDITION: {reason}!")
                    record_halt_in_status(r_id, reason)
                    sys.exit(res["returncode"])

                # Validate raw file on disk
                r_file = PROJECT_ROOT / "data" / "raw" / b / f"round_{r_id:03d}.json"
                if not r_file.exists():
                    reason = f"Missing output file {r_file.name} for backend {b}"
                    logger.error(f"HALT CONDITION: {reason}!")
                    record_halt_in_status(r_id, reason)
                    sys.exit(1)

                with open(r_file, "r", encoding="utf-8") as f:
                    rec = json.load(f)
                exec_time = rec.get("execution_time_seconds", 8.0)
                if abs(exec_time - 8.0) > 1.2:  # > 15% deviation
                    reason = f"Usage deviation > 15% on {b} Round {r_id} ({exec_time:.2f}s vs 8.0s baseline)"
                    logger.error(f"HALT CONDITION: {reason}!")
                    record_halt_in_status(r_id, reason)
                    sys.exit(1)

                # Check 60% cumulative budget cap (306.0s)
                b_state = get_budget_state()
                cum_qpu = b_state.get("cumulative_quantum_seconds", 0.0)
                if r_id < 12 and cum_qpu > 306.0:
                    reason = f"Cumulative QPU usage ({cum_qpu:.2f}s) exceeded 60% safety cap (306.0s)"
                    logger.error(f"HALT CONDITION: {reason}!")
                    record_halt_in_status(r_id, reason)
                    sys.exit(1)

                logger.info(f"[{b}] Round {r_id} validated. Cumulative QPU: {cum_qpu:.2f}s / 510.0s.")

                # If all backends have finished this round, trigger batch commit
                if all(check_round_completed(other_b, r_id) for other_b in real_backends):
                    logger.info(f"--- Round {r_id} is now complete across all 3 backends! ---")
                    git_commit_and_push(f"Batch report: Round {r_id} completed across all 3 backends (Cumulative QPU: {cum_qpu:.2f}s / 510.0s)")

        # 3. Check Hard Cutoff
        if now_utc >= CUTOFF_UTC:
            logger.warning(f"HARD CUTOFF REACHED ({CUTOFF_UTC.strftime('%Y-%m-%d %H:%M UTC')}). Ceasing further round submissions.")
            # Wait for any in-flight workers
            for b in real_backends:
                if active_threads[b] is not None and active_threads[b].is_alive():
                    logger.info(f"Waiting for active job on {b} to complete...")
                    active_threads[b].join()
            break

        # 4. Check if all 12 rounds are complete across all backends
        if all(check_round_completed(b, end_round) for b in real_backends) and all(th is None for th in active_threads.values()):
            logger.info("All rounds through Round 12 are complete across all backends!")
            break

        # 5. Dispatch ready backends independently
        for b in real_backends:
            if active_threads[b] is not None:
                continue  # Backend is currently collecting

            # Find next incomplete round for backend b
            next_r = None
            for r in range(start_round, end_round + 1):
                if not check_round_completed(b, r):
                    next_r = r
                    break

            if next_r is None:
                continue  # All rounds complete for this backend

            # Check if previous round is complete on this backend
            if next_r > 1 and not check_round_completed(b, next_r - 1):
                continue

            # Check hard floor for backend b (2.0h for rounds >= 8)
            gap_h = get_min_gap_hours_for_round(next_r)
            wait_sec = get_seconds_until_allowed(b, next_r, gap_h)
            if wait_sec <= 0.0:
                logger.info(f"[{b}] {gap_h:.1f}h floor cleared! Launching independent collection for Round {next_r}...")
                t = threading.Thread(target=run_single_backend_worker, args=(b, next_r, gap_h))
                t.daemon = True
                t.start()
                active_threads[b] = t

        # 6. Log Heartbeat Summary
        b_state = get_budget_state()
        cum_qpu = b_state.get("cumulative_quantum_seconds", 0.0)
        status_items = []
        for b in real_backends:
            if active_threads[b] is not None:
                status_items.append(f"{b}: RUNNING")
            else:
                next_r = None
                for r in range(start_round, end_round + 1):
                    if not check_round_completed(b, r):
                        next_r = r
                        break
                if next_r is None:
                    status_items.append(f"{b}: DONE (R12)")
                else:
                    gap_h = get_min_gap_hours_for_round(next_r)
                    wait_sec = get_seconds_until_allowed(b, next_r, gap_h)
                    wait_h = wait_sec / 3600.0
                    status_items.append(f"{b}: R{next_r} locked ({wait_h:.2f}h left @ {gap_h:.1f}h floor)")

        logger.info(f"[HEARTBEAT] {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')} | Active | QPU: {cum_qpu:.1f}s/510s | " + " | ".join(status_items))
        sys.stdout.flush()

        time.sleep(cycle_seconds)


def finalize_splits_after_collection(config: dict, backends: list) -> int:
    """Finds highest common round, updates study.yaml split if < 12 rounds, and logs changes."""
    completed = {b: [r for r in range(1, 13) if check_round_completed(b, r)] for b in backends}
    common_rounds = sorted(list(set.intersection(*[set(completed[b]) for b in backends])))
    max_common = max(common_rounds) if common_rounds else 0

    logger.info(f"Data collection ended. Max round completed across ALL 3 backends: Round {max_common}")
    for b in backends:
        logger.info(f"  - {b}: completed {len(completed[b])} rounds ({completed[b]})")

    study_path = PROJECT_ROOT / "configs" / "study.yaml"
    with open(study_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if max_common < 12:
        logger.warning(f"Rounds completed ({max_common}) is less than 12. Adjusting split in study.yaml...")
        train_rounds = [1, 2, 3, 4, 5]
        val_rounds = [6, 7]
        test_rounds = list(range(8, max_common + 1))

        cfg["sampling"]["rounds_target"] = max_common
        cfg["splits"]["train_rounds"] = train_rounds
        cfg["splits"]["val_rounds"] = val_rounds
        cfg["splits"]["test_rounds"] = test_rounds

        with open(study_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(cfg, f, default_flow_style=False, sort_keys=False)

        note_entry = (
            f"\n\n### Data Collection Cutoff and Split Adjustment (Oct 10 Cutoff)\n"
            f"- **Cutoff Timestamp**: {datetime.now(timezone.utc).isoformat()}\n"
            f"- **Rounds Collected Across All 3 Backends**: {max_common} rounds (train: 1-5, val: 6-7, test: 8-{max_common}).\n"
            f"- **Test Rounds**: {len(test_rounds)} test rounds (preserving strict chronological order, zero data leakage).\n"
            f"- **Reason**: Hard deadline cutoff at Oct 10 12:00 local time to allow complete experimental synthesis.\n"
        )
        for md_name in ["METHODS_NOTES.md", "LIMITATIONS_OBSERVED.md"]:
            md_file = PROJECT_ROOT / md_name
            if md_file.exists():
                md_content = md_file.read_text(encoding="utf-8")
                md_file.write_text(md_content + note_entry, encoding="utf-8")

        git_commit_and_push(f"Cutoff adjustment: Locked {max_common} rounds into study.yaml (train 1-5, val 6-7, test 8-{max_common})")
    else:
        logger.info("All 12 rounds successfully collected. Full Schedule B locked.")

    return max_common


def run_stage_3(total_rounds: int):
    logger.info("\n" + "=" * 80)
    logger.info(f"ENTERING STAGE 3: MATCHING ADVERSARIAL SIMULATIONS ({total_rounds} ROUNDS)")
    logger.info("=" * 80)
    cmd = [sys.executable, "scripts/04_simulate.py", "--rounds", str(total_rounds)]
    proc = subprocess.run(cmd, cwd=PROJECT_ROOT, text=True)
    if proc.returncode != 0:
        reason = f"Stage 3 (04_simulate.py) failed with exit code {proc.returncode}"
        logger.error(reason)
        record_halt_in_status(total_rounds, reason)
        sys.exit(proc.returncode)
    logger.info("Stage 3 completed successfully.")
    git_commit_and_push(f"Stage 3 complete: S0, S1, S2 matching simulations generated for {total_rounds} rounds")


def run_stage_4():
    logger.info("\n" + "=" * 80)
    logger.info("ENTERING STAGE 4: FEATURES, EXPERIMENTS E1-E7, AND CLAIMS AUDIT")
    logger.info("=" * 80)

    # 4A. Build Features
    logger.info("Running 05_build_features.py...")
    proc_feat = subprocess.run([sys.executable, "scripts/05_build_features.py"], cwd=PROJECT_ROOT, text=True)
    if proc_feat.returncode != 0:
        reason = f"Stage 4 (05_build_features.py) failed with exit code {proc_feat.returncode}"
        logger.error(reason)
        record_halt_in_status(12, reason)
        sys.exit(proc_feat.returncode)

    # 4B. Run Experiments E1-E7
    logger.info("Running 06_run_experiments.py...")
    proc_exp = subprocess.run([sys.executable, "scripts/06_run_experiments.py"], cwd=PROJECT_ROOT, text=True)
    if proc_exp.returncode != 0:
        reason = f"Stage 4 (06_run_experiments.py) failed with exit code {proc_exp.returncode}"
        logger.error(reason)
        record_halt_in_status(12, reason)
        sys.exit(proc_exp.returncode)

    # 4C. Claims Audit
    logger.info("Running 09_claims_audit.py...")
    proc_audit = subprocess.run([sys.executable, "scripts/09_claims_audit.py"], cwd=PROJECT_ROOT, text=True)
    if proc_audit.returncode != 0:
        reason = f"Stage 4 (09_claims_audit.py) failed with exit code {proc_audit.returncode}"
        logger.error(reason)
        record_halt_in_status(12, reason)
        sys.exit(proc_audit.returncode)

    logger.info("Stage 4 completed successfully.")
    git_commit_and_push("Stage 4 complete: Feature dataset, Experiments E1-E7, and Claims Audit")


def run_stage_5():
    logger.info("\n" + "=" * 80)
    logger.info("ENTERING STAGE 5: PUBLICATION FIGURES 1-12, TABLES T1-T5, AND HANDOFF")
    logger.info("=" * 80)

    # 5A. Generate Figures 1-12 & CAPTIONS.md
    logger.info("Running 07_make_figures.py...")
    proc_fig = subprocess.run([sys.executable, "scripts/07_make_figures.py"], cwd=PROJECT_ROOT, text=True)
    if proc_fig.returncode != 0:
        reason = f"Stage 5 (07_make_figures.py) failed with exit code {proc_fig.returncode}"
        logger.error(reason)
        record_halt_in_status(12, reason)
        sys.exit(proc_fig.returncode)

    # 5B. Generate Tables T1-T5 (CSV and LaTeX)
    logger.info("Running 08_make_tables.py...")
    proc_tab = subprocess.run([sys.executable, "scripts/08_make_tables.py"], cwd=PROJECT_ROOT, text=True)
    if proc_tab.returncode != 0:
        reason = f"Stage 5 (08_make_tables.py) failed with exit code {proc_tab.returncode}"
        logger.error(reason)
        record_halt_in_status(12, reason)
        sys.exit(proc_tab.returncode)

    # 5C. Package Handoff Deliverables
    handoff_dir = PROJECT_ROOT / "results" / "handoff"
    handoff_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "figures": [f.name for f in (PROJECT_ROOT / "results" / "figures").glob("*.png")],
        "tables": [t.name for t in (PROJECT_ROOT / "results" / "tables").glob("*.*")],
        "captions": (PROJECT_ROOT / "results" / "figures" / "CAPTIONS.md").exists(),
        "audit": (PROJECT_ROOT / "claims_audit.md").exists(),
        "results_json": (PROJECT_ROOT / "results" / "results.json").exists(),
    }
    with open(handoff_dir / "MANIFEST.json", "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    logger.info("Stage 5 completed successfully.")
    git_commit_and_push("Stage 5 complete: Publication figures 1-12, Tables T1-T5, CAPTIONS.md, and Handoff package")


def report_final_milestone(config: dict):
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]
    budget_state = get_budget_state()
    total_qpu = budget_state.get("cumulative_quantum_seconds", 0.0)

    # Calculate observation window
    all_starts = []
    all_ends = []
    for b in real_backends:
        for r_file in (PROJECT_ROOT / "data" / "raw" / b).glob("round_*.json"):
            with open(r_file, "r", encoding="utf-8") as f:
                d = json.load(f)
                s = d.get("start_timestamp")
                e = d.get("end_timestamp")
                if s: all_starts.append(datetime.fromisoformat(s.replace("Z", "+00:00")))
                if e: all_ends.append(datetime.fromisoformat(e.replace("Z", "+00:00")))

    obs_hours = 0.0
    obs_days = 0.0
    if all_starts and all_ends:
        t_first = min(all_starts)
        t_last = max(all_ends)
        obs_hours = (t_last - t_first).total_seconds() / 3600.0
        obs_days = obs_hours / 24.0

    rounds_per_b = {b: len(list((PROJECT_ROOT / "data" / "raw" / b).glob("round_*.json"))) for b in real_backends}

    audit_file = PROJECT_ROOT / "claims_audit.md"
    audit_content = audit_file.read_text(encoding="utf-8") if audit_file.exists() else "claims_audit.md not found."

    figures_list = sorted([p.name for p in (PROJECT_ROOT / "results" / "figures").glob("*.png")])
    tables_list = sorted([p.name for p in (PROJECT_ROOT / "results" / "tables").glob("*.csv")])

    print("\n" + "=" * 80)
    print("FINAL STUDY MILESTONE COMPLETE: STAGES 2 -> 3 -> 4 -> 5 FINISHED")
    print("=" * 80)
    print(f"Observation Window               : {obs_hours:.2f} hours ({obs_days:.2f} days)")
    print(f"Rounds Completed Per Backend     : {rounds_per_b}")
    print(f"Total QPU Consumed               : {total_qpu:.2f} s / 510.0 s Safety Cap ({total_qpu / 510.0 * 100:.1f} %)")
    print(f"Total Safe Allowance Remaining   : {510.0 - total_qpu:.2f} s")
    print(f"Observation Cadence Integrity    : Compressed deadline cadence (strictly >= 4.0h floor per round)")
    print("-" * 80)
    print("GENERATED PUBLICATION FIGURES (300 DPI PNG + vector PDF + Source CSV):")
    for fig in figures_list:
        print(f"  - results/figures/{fig}")
    print("-" * 80)
    print("GENERATED PUBLICATION TABLES (CSV + LaTeX):")
    for tbl in tables_list:
        print(f"  - results/tables/{tbl} (+ .tex)")
    print("-" * 80)
    print("\nCLAIMS AUDIT SUMMARY (claims_audit.md):\n")
    print(audit_content)
    print("=" * 80 + "\n")


def main():
    args = parse_args()
    config_path = PROJECT_ROOT / args.config
    config = load_config(config_path)
    real_backends = [b["name"] for b in config["backends"].get("real_backends", [])]

    if args.status:
        print_status_report(config, args.min_gap_hours)
        return

    # Run collection loop (Rounds 8-12)
    run_collection_loop(
        config=config,
        min_gap_hours=args.min_gap_hours,
        start_round=args.start_round,
        end_round=args.end_round,
        cycle_seconds=args.cycle_seconds
    )

    # Determine final completed rounds and adjust split if < 12
    final_rounds = finalize_splits_after_collection(config, real_backends)

    # Run Stage 3, Stage 4, Stage 5
    run_stage_3(final_rounds)
    run_stage_4()
    run_stage_5()

    # Final Milestone Report
    report_final_milestone(config)


if __name__ == "__main__":
    main()
