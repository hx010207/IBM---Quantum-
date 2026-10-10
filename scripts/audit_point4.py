#!/usr/bin/env python3
"""Audit Point 4: Record recovery tagging, E1/E3 without recovered rounds, and budget verification."""

import glob
import json
import os
from pathlib import Path
import sys
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

try:
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
except ImportError:
    pass

from qiskit_ibm_runtime import QiskitRuntimeService
from qfp.features import get_feature_subsets
from qfp.models import create_classifier_pipeline
from sklearn.metrics import accuracy_score

print("================================================================================")
print("POINT 4: RECOVERED RECORD AUDIT & TAGGING")
print("================================================================================")

# 1. Inspect all 30 hardware round files
raw_dir = PROJECT_ROOT / "data" / "raw"
hardware_records = []
recovered_records = []

for b in ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]:
    for r in range(1, 11):
        fpath = raw_dir / b / f"round_{r:03d}.json"
        if not fpath.exists():
            continue
        with open(fpath, "r", encoding="utf-8") as f:
            rec = json.load(f)
        
        job_id = rec.get("job_id")
        t_path = rec.get("transpile_path", "alap")
        rec_tag = rec.get("recovery", "none")
        
        is_recovered = False
        rec_details = "none"
        if b == "ibm_kingston" and r == 5:
            is_recovered = True
            rec_details = "transpile_fallback (Qiskit ALAP error resolved via native basis transpile)"
        elif b == "ibm_kingston" and r == 9:
            is_recovered = True
            rec_details = "post_hoc_api_retrieval (client socket timeout during system sleep; payload fetched via job_id db4c73o4qg6s73c1vucg)"
        elif b == "ibm_kingston" and r == 10:
            is_recovered = True
            rec_details = "post_hoc_api_retrieval (client socket timeout during system sleep; payload fetched via job_id db4gqkcvf2bc73cujge0)"
        
        # Tag recovery field into the raw file without altering counts
        rec["recovery"] = rec_details
        with open(fpath, "w", encoding="utf-8") as f:
            json.dump(rec, f, indent=2)
            
        hardware_records.append({
            "backend": b,
            "round": r,
            "job_id": job_id,
            "transpile_path": t_path,
            "exec_time_seconds": rec.get("execution_time_seconds"),
            "start": rec.get("start_timestamp"),
            "end": rec.get("end_timestamp"),
            "recovery": rec_details,
        })
        if is_recovered:
            recovered_records.append(hardware_records[-1])

print(f"Total hardware rounds analyzed: {len(hardware_records)}")
print(f"Recovered or non-standard rounds ({len(recovered_records)} total):")
for rec in recovered_records:
    print(f"  - {rec['backend']} Round {rec['round']}:")
    print(f"      Job ID       : {rec['job_id']}")
    print(f"      Transpile    : {rec['transpile_path']}")
    print(f"      Start -> End : {rec['start']} -> {rec['end']}")
    print(f"      QPU Sec      : {rec['exec_time_seconds']}")
    print(f"      Recovery Type: {rec['recovery']}")

print("\n================================================================================")
print("RE-RUN E1 AND E3 EXCLUDING RECOVERED BACKEND-ROUNDS")
print("================================================================================")
# Recovered pairs: (ibm_kingston, 5), (ibm_kingston, 9), (ibm_kingston, 10)
df = pd.read_csv(PROJECT_ROOT / "data" / "features" / "dataset_features.csv")
subsets = get_feature_subsets(df.columns)
full_feats = subsets["full"]

real_df = df[~df["backend"].str.startswith("sim_")].copy()

# Full dataset splits
train_rounds = [1, 2, 3, 4, 5]
val_rounds = [6, 7]
test_rounds = [8, 9, 10]

tr_full = real_df[real_df["round_id"].isin(train_rounds)]
te_full = real_df[real_df["round_id"].isin(test_rounds)]

# Filtered dataset (excluding recovered Kingston rounds 5, 9, 10)
exclude_mask = (real_df["backend"] == "ibm_kingston") & (real_df["round_id"].isin([5, 9, 10]))
filtered_df = real_df[~exclude_mask].copy()

tr_filt = filtered_df[filtered_df["round_id"].isin(train_rounds)]
te_filt = filtered_df[filtered_df["round_id"].isin(test_rounds)]

print(f"Full Test Set size: {len(te_full)} chunks | Filtered Test Set size: {len(te_filt)} chunks")

models = ["logistic_regression", "svm_rbf", "random_forest", "gradient_boosting", "mlp"]
print("\n--- E1 Performance: Full vs Excluding Recovered Kingston Rounds ---")
print(f"  {'Model':<20} | {'Full Test Acc':<14} | {'Excl Recovered Acc':<20} | {'Difference':<12}")
print("  " + "-" * 72)
for m in models:
    # Full
    p_full = create_classifier_pipeline(m, seed=42)
    p_full.fit(tr_full[full_feats].values, tr_full["backend"].values)
    acc_full = accuracy_score(te_full["backend"].values, p_full.predict(te_full[full_feats].values))
    
    # Filtered
    p_filt = create_classifier_pipeline(m, seed=42)
    p_filt.fit(tr_filt[full_feats].values, tr_filt["backend"].values)
    acc_filt = accuracy_score(te_filt["backend"].values, p_filt.predict(te_filt[full_feats].values))
    
    diff = acc_filt - acc_full
    print(f"  {m:<20} | {acc_full:<14.4f} | {acc_filt:<20.4f} | {diff:+12.4f}")

print("\n--- E3 Longitudinal Persistence: Full vs Excluding Recovered Rounds ---")
p_e3_full = create_classifier_pipeline("random_forest", seed=42)
tr_e3_full = real_df[real_df["round_id"].isin([1, 2])]
p_e3_full.fit(tr_e3_full[full_feats].values, tr_e3_full["backend"].values)

p_e3_filt = create_classifier_pipeline("random_forest", seed=42)
tr_e3_filt = filtered_df[filtered_df["round_id"].isin([1, 2])]
p_e3_filt.fit(tr_e3_filt[full_feats].values, tr_e3_filt["backend"].values)

print(f"  {'Round':<8} | {'Full Acc':<12} | {'Excl Recovered Acc':<20} | {'Difference':<12}")
print("  " + "-" * 56)
for r in range(3, 11):
    df_r_full = real_df[real_df["round_id"] == r]
    df_r_filt = filtered_df[filtered_df["round_id"] == r]
    
    acc_r_full = accuracy_score(df_r_full["backend"].values, p_e3_full.predict(df_r_full[full_feats].values))
    acc_r_filt = accuracy_score(df_r_filt["backend"].values, p_e3_filt.predict(df_r_filt[full_feats].values)) if not df_r_filt.empty else np.nan
    diff_r = acc_r_filt - acc_r_full if not np.isnan(acc_r_filt) else np.nan
    print(f"  Round {r:<2} | {acc_r_full:<12.4f} | {acc_r_filt:<20.4f} | {diff_r:+12.4f}")

print("\n================================================================================")
print("QPU USAGE VERIFICATION AGAINST service.job(id).usage() (NO ASSUMED DEFAULTS)")
print("================================================================================")
service = QiskitRuntimeService(
    channel=os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform"),
    token=os.environ.get("QISKIT_IBM_TOKEN"),
    instance=os.environ.get("QISKIT_IBM_INSTANCE"),
)

# Initial probe jobs
probe_jobs = {
    "ibm_fez": "db16qhrid5ic73eq5t60",
    "ibm_kingston": "db16qhrb694s73drp1lg",
    "ibm_marrakesh": "db16qhqvog1s73fi01tg",
}

all_jobs_to_query = []
for b, jid in probe_jobs.items():
    all_jobs_to_query.append((b, 0, jid, "initial_probe"))

for rec in hardware_records:
    all_jobs_to_query.append((rec["backend"], rec["round"], rec["job_id"], f"round_{rec['round']}"))

print(f"Querying exact cloud usage for {len(all_jobs_to_query)} jobs via Qiskit Runtime API...")
exact_usages = []
for b, r, jid, desc in all_jobs_to_query:
    try:
        job_obj = service.job(jid)
        usage_val = job_obj.usage()
        # Extract qpu seconds
        q_sec = None
        if isinstance(usage_val, (int, float)):
            q_sec = float(usage_val)
        elif isinstance(usage_val, dict):
            q_sec = float(usage_val.get("qpu_charge_time_seconds") or usage_val.get("quantum_seconds"))
        exact_usages.append((b, r, jid, desc, q_sec))
        print(f"  {b:<14} R{r:<2} ({desc:<13}) Job={jid} -> Exact QPU Usage = {q_sec} s")
    except Exception as e:
        print(f"  ERROR querying {jid}: {e}")
        exact_usages.append((b, r, jid, desc, None))

total_exact_qpu = sum(u[4] for u in exact_usages if u[4] is not None)
print("-" * 80)
print(f"Sum of exact service.job(id).usage() across all {len(exact_usages)} jobs: {total_exact_qpu:.3f} s")

with open(PROJECT_ROOT / "data" / "interim" / "budget_state.json") as f:
    b_state = json.load(f)
recorded_qpu = b_state.get("cumulative_quantum_seconds")
print(f"Value in budget_state.json: {recorded_qpu:.3f} s")
print(f"Exact Discrepancy: {abs(total_exact_qpu - recorded_qpu):.4f} s")
