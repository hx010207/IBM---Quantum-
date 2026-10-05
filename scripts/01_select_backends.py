#!/usr/bin/env python3
"""Script 01: Discover and select 2-3 optimal IBM Quantum backends and physical 3-qubit layouts.

Queries available backends in the user's IBM Quantum instance, filters for
operational systems with at least 3 connected qubits, selects connected 3-qubit
triples with minimum two-qubit gate errors from target calibration data,
and updates configs/study.yaml.

Supports --dry-run for local pipeline verification using fake backends.
"""

import argparse
import logging
import os
from pathlib import Path
import sys
import yaml

# Ensure src/ is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("select_backends")


def parse_args():
    parser = argparse.ArgumentParser(description="Discover and select IBM backends and layouts.")
    parser.add_argument("--dry-run", action="store_true", help="Use local fake backends for testing.")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    return parser.parse_args()


def select_best_3qubit_line(backend) -> tuple:
    """Finds a connected line of 3 physical qubits with lowest aggregate gate and readout errors."""
    target = backend.target
    op_name = next((op for op in ["cz", "ecr", "cx"] if op in target.operation_names), None)
    if not op_name:
        return [0, 1, 2], 0.0, 0.0, 0.0, "none"
        
    edges = list(target[op_name].keys())
    adj = {}
    for u, v in edges:
        adj.setdefault(u, set()).add(v)
        adj.setdefault(v, set()).add(u)

    triples = []
    for v, neighbors in adj.items():
        n_list = sorted(list(neighbors))
        for i in range(len(n_list)):
            for j in range(i + 1, len(n_list)):
                triples.append([n_list[i], v, n_list[j]])

    if not triples:
        return [0, 1, 2], 0.0, 0.0, 0.0, op_name

    best_triple = triples[0]
    best_err = float("inf")
    best_e1, best_e2, best_ro = 0.0, 0.0, 0.0

    for u, v, w in triples:
        def get_err(q1, q2):
            inst = target[op_name].get((q1, q2)) or target[op_name].get((q2, q1))
            return inst.error if (inst and inst.error is not None) else 0.01

        e1 = get_err(u, v)
        e2 = get_err(v, w)

        def get_ro(q):
            inst = target["measure"].get((q,))
            return inst.error if (inst and inst.error is not None) else 0.01

        ro_avg = (get_ro(u) + get_ro(v) + get_ro(w)) / 3.0
        tot = e1 + e2 + ro_avg

        if tot < best_err:
            best_err = tot
            best_triple = [u, v, w]
            best_e1, best_e2, best_ro = e1, e2, ro_avg

    return best_triple, best_err, best_e1, best_e2, best_ro, op_name


def main():
    args = parse_args()
    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    if args.dry_run:
        logger.info("[Dry-Run] Selecting fake backends for pipeline verification.")
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeBrisbane, FakeKyiv

        candidates = [
            ("fake_sherbrooke", FakeSherbrooke()),
            ("fake_brisbane", FakeBrisbane()),
            ("fake_kyiv", FakeKyiv()),
        ]

        selected = []
        for name, b in candidates:
            layout, err, e1, e2, ro, op = select_best_3qubit_line(b)
            logger.info(f"Selected fake backend '{name}' with 3-qubit line layout: {layout}")
            selected.append({"name": name, "layout": layout})

        config["backends"]["dryrun_backends"] = selected
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False)

        logger.info(f"Updated {config_path} with {len(selected)} dryrun backends.")
        return

    # Real IBM hardware query
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass

    token = os.environ.get("QISKIT_IBM_TOKEN")
    instance = os.environ.get("QISKIT_IBM_INSTANCE")
    channel = os.environ.get("QISKIT_IBM_CHANNEL", "ibm_quantum_platform")

    logger.info("Connecting to IBM Quantum Runtime service...")
    try:
        from qiskit_ibm_runtime import QiskitRuntimeService
        if token and instance:
            service = QiskitRuntimeService(channel=channel, token=token, instance=instance)
        elif token:
            service = QiskitRuntimeService(channel=channel, token=token)
        else:
            service = QiskitRuntimeService()
    except Exception as e:
        logger.error(f"Failed to authenticate with IBM Quantum: {e}")
        sys.exit(1)

    all_backends = service.backends(operational=True, simulator=False)
    logger.info(f"Discovered {len(all_backends)} operational real hardware backends.")

    selected_real = []
    print("\n" + "=" * 80)
    print("IBM QUANTUM HARDWARE BACKEND DISCOVERY & 3-QUBIT LAYOUT OPTIMIZATION")
    print("=" * 80)
    for b in all_backends:
        layout, err, e1, e2, ro, op = select_best_3qubit_line(b)
        status = b.status()
        print(f"Backend: {b.name:<16} | Qubits: {b.num_qubits:>3} | Operational: {status.operational} | Pending Jobs: {status.pending_jobs:>2}")
        print(f"  Fixed 3-Qubit Line Layout : {layout}")
        print(f"  Entangling Gate ({op.upper()})    : Edge 1 error = {e1:.4e}, Edge 2 error = {e2:.4e}")
        print(f"  Average Readout Error     : {ro:.4e} | Composite Score = {err:.4e}\n")
        selected_real.append({
            "name": b.name,
            "num_qubits": b.num_qubits,
            "gate_2q": op,
            "layout": layout,
            "edge1_error": float(e1),
            "edge2_error": float(e2),
            "avg_readout_error": float(ro),
            "composite_error": float(err),
        })

    config["backends"]["real_backends"] = selected_real
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)

    logger.info(f"Successfully configured {len(selected_real)} real backends in {config_path}.")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()
