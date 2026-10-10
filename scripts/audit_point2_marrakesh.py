#!/usr/bin/env python3
"""Audit Item 2: Diagnose Marrakesh and Fez shifts between R7 and R8 (Rounds 5-10)."""

import json
import hashlib
from pathlib import Path
import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent

def main():
    backends = ["ibm_fez", "ibm_kingston", "ibm_marrakesh"]
    rounds = [5, 6, 7, 8, 9, 10]
    
    print("=== Metadata and Calibration Across Rounds 5-10 ===")
    records_summary = []
    
    for b in backends:
        for r in rounds:
            p = PROJECT_ROOT / "data" / "raw" / b / f"round_{r:03d}.json"
            if not p.exists():
                continue
            with open(p) as f:
                d = json.load(f)
                
            layout = d.get("physical_layout")
            shots = d.get("shots_per_circuit")
            num_chunks = d.get("num_chunks")
            tpath = d.get("transpile_path")
            rec = d.get("recovery", "none")
            circuits_keys = list(d.get("circuits", {}).keys())
            order_hash = hashlib.sha256(",".join(circuits_keys).encode()).hexdigest()[:8]
            
            # Calibration properties
            props = d.get("properties_snapshot") or {}
            cal_date = props.get("calibration_date")
            snap_time = props.get("timestamp")
            qprops = props.get("qubit_properties") or {}
            
            t1 = {int(q): round(qprops.get(str(q), {}).get("t1_seconds", 0)*1e6, 1) for q in layout}
            t2 = {int(q): round(qprops.get(str(q), {}).get("t2_seconds", 0)*1e6, 1) for q in layout}
            ro = {int(q): round(qprops.get(str(q), {}).get("readout_error", 0), 4) for q in layout}
            
            cz_dict = props.get("two_qubit_gate_errors") or {}
            cz = {k: round(v.get("error", 0), 4) for k, v in cz_dict.items()}
            
            records_summary.append({
                "backend": b,
                "round": r,
                "layout": layout,
                "shots": shots,
                "chunks": num_chunks,
                "path": tpath,
                "recovery": rec,
                "order_hash": order_hash,
                "cal_date": cal_date,
                "snap_time": snap_time,
                "t1": t1,
                "t2": t2,
                "ro": ro,
                "cz": cz,
            })

    for row in records_summary:
        print(f"{row['backend']:14s} | R{row['round']:02d} | Layout: {row['layout']} | Shots: {row['shots']} | Chunks: {row['chunks']} | Path: {row['path']} | Rec: {row['recovery'][:16]}")
        print(f"  OrderHash: {row['order_hash']} | CalDate: {row['cal_date']} | SnapTime: {row['snap_time']}")
        print(f"  T1 (us): {row['t1']}")
        print(f"  T2 (us): {row['t2']}")
        print(f"  RO err:  {row['ro']}")
        print(f"  CZ err:  {row['cz']}")

    print("\n=== Diagnosis: ibm_marrakesh R7 vs R8 Shift ===")
    with open(PROJECT_ROOT / "data" / "raw" / "ibm_marrakesh" / "round_007.json") as f:
        m7 = json.load(f)
    with open(PROJECT_ROOT / "data" / "raw" / "ibm_marrakesh" / "round_008.json") as f:
        m8 = json.load(f)
        
    print("c01_prep_000 (Ideal: 2048 |000>):")
    print(f"  R7 Counts: {m7['circuits']['c01_prep_000']['aggregate_counts']}")
    print(f"  R8 Counts: {m8['circuits']['c01_prep_000']['aggregate_counts']}")
    
    # Qubit breakdown for c01 in R8:
    c01_r8 = m8['circuits']['c01_prep_000']['aggregate_counts']
    excited_q1 = sum(cnt for bstr, cnt in c01_r8.items() if bstr[1] == '1')
    print(f"  R8 Spurious excitations on middle qubit (logical q1, physical q5): {excited_q1} / 2048 ({excited_q1/2048*100:.2f}%)")
    
    print("\nCalibration evolution on ibm_marrakesh physical qubit 5:")
    for r in [6, 7, 8, 9, 10]:
        with open(PROJECT_ROOT / "data" / "raw" / "ibm_marrakesh" / f"round_{r:03d}.json") as f:
            d = json.load(f)
        props = d.get("properties_snapshot") or {}
        qp5 = (props.get("qubit_properties") or {}).get("5") or {}
        print(f"  R{r:02d} ({props.get('calibration_date')}): T1={qp5.get('t1_seconds',0)*1e6:.1f}us, T2={qp5.get('t2_seconds',0)*1e6:.1f}us, Readout Error={qp5.get('readout_error',0):.4f}")

    print("\n=== Diagnosis: ibm_fez R7 vs R8 Shift ===")
    with open(PROJECT_ROOT / "data" / "raw" / "ibm_fez" / "round_007.json") as f:
        f7 = json.load(f)
    with open(PROJECT_ROOT / "data" / "raw" / "ibm_fez" / "round_008.json") as f:
        f8 = json.load(f)
        
    print("c10_mirror_depth24_delay (delay relaxation shift):")
    print(f"  R7 Counts: {f7['circuits']['c10_mirror_depth24_delay']['aggregate_counts']}")
    print(f"  R8 Counts: {f8['circuits']['c10_mirror_depth24_delay']['aggregate_counts']}")
    
    print("\nCalibration evolution on ibm_fez physical qubits [137, 147, 146]:")
    for r in [6, 7, 8, 9, 10]:
        with open(PROJECT_ROOT / "data" / "raw" / "ibm_fez" / f"round_{r:03d}.json") as f:
            d = json.load(f)
        props = d.get("properties_snapshot") or {}
        qps = props.get("qubit_properties") or {}
        print(f"  R{r:02d} ({props.get('calibration_date')}): "
              f"T1={ [round(qps.get(str(q),{}).get('t1_seconds',0)*1e6,1) for q in [137, 147, 146]] }, "
              f"T2={ [round(qps.get(str(q),{}).get('t2_seconds',0)*1e6,1) for q in [137, 147, 146]] }, "
              f"RO={ [round(qps.get(str(q),{}).get('readout_error',0),4) for q in [137, 147, 146]] }")

if __name__ == "__main__":
    main()
