#!/usr/bin/env python3
"""Script 04: Generate matching adversarial simulations (S0, S1, S2).

Simulates adversary classes matching the collected rounds:
  - S0: Ideal noiseless statevector sampling
  - S1: Calibration-derived impersonator (AerSimulator.from_backend)
  - S2: Adaptive impersonator (S1 + empirical readout confusion calibrated
        exclusively from training-period |000> and |111> calibration circuits)

Enforces that S2 parameters are fitted ONLY on training rounds (rounds 1..4).
"""

import argparse
import json
import logging
import os
from pathlib import Path
import sys
import numpy as np
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from qfp.simulate import AdaptiveReadoutModel, generate_simulator_round

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("simulate")


def parse_args():
    parser = argparse.ArgumentParser(description="Generate S0, S1, S2 simulator rounds.")
    parser.add_argument("--dry-run", action="store_true", help="Run locally using fake backends.")
    parser.add_argument("--rounds", type=int, default=None, help="Number of rounds to simulate (default from config).")
    parser.add_argument("--config", type=str, default="configs/study.yaml", help="Path to study.yaml config.")
    return parser.parse_args()


def fit_adaptive_model_from_training_rounds(
    raw_dir: Path,
    backend_name: str,
    train_rounds: list,
) -> AdaptiveReadoutModel:
    """Fits empirical readout confusion model from training rounds of |000> and |111>."""
    accum_000 = {}
    accum_111 = {}
    
    b_dir = raw_dir / backend_name
    for r in train_rounds:
        r_file = b_dir / f"round_{r:03d}.json"
        if not r_file.exists():
            continue
        with open(r_file, "r", encoding="utf-8") as f:
            data = json.load(f)
            c_data = data.get("circuits", {})
            c01_counts = c_data.get("c01_prep_000", {}).get("aggregate_counts", {})
            c02_counts = c_data.get("c02_prep_111", {}).get("aggregate_counts", {})
            for bstr, cnt in c01_counts.items():
                accum_000[bstr] = accum_000.get(bstr, 0) + cnt
            for bstr, cnt in c02_counts.items():
                accum_111[bstr] = accum_111.get(bstr, 0) + cnt
                
    if not accum_000 or not accum_111:
        logger.warning(f"No calibration counts found for {backend_name} in training rounds {train_rounds}. Using default.")
        accum_000 = {"000": 1000}
        accum_111 = {"111": 1000}
        
    model = AdaptiveReadoutModel(num_qubits=3)
    model.fit_from_calibration_counts(accum_000, accum_111)
    logger.info(
        f"Fitted AdaptiveReadoutModel for {backend_name} from training rounds {train_rounds}: "
        f"P(1|0)={np.round(model.p1_given_0, 4)}, P(0|1)={np.round(model.p0_given_1, 4)}"
    )
    return model


def main():
    args = parse_args()
    config_path = Path(args.config)
    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    sampling_cfg = config.get("sampling", {})
    shots = int(sampling_cfg.get("shots_per_circuit", 2048))
    num_chunks = int(sampling_cfg.get("chunks_per_round", 8))
    total_rounds = args.rounds or int(sampling_cfg.get("rounds_target", 8))
    train_rounds = config.get("splits", {}).get("train_rounds", [1, 2, 3, 4])

    raw_dir = Path("dryrun/data/raw") if args.dry_run else Path("data/raw")

    if args.dry_run:
        from qiskit_ibm_runtime.fake_provider import FakeSherbrooke, FakeBrisbane, FakeKyiv
        fake_map = {
            "fake_sherbrooke": FakeSherbrooke,
            "fake_brisbane": FakeBrisbane,
            "fake_kyiv": FakeKyiv,
        }
        backends_cfg = config["backends"].get("dryrun_backends", [])
        
        for b_entry in backends_cfg:
            b_name = b_entry["name"]
            layout = b_entry["layout"]
            backend_obj = fake_map.get(b_name, FakeSherbrooke)()
            
            # Fit adaptive readout model strictly on training rounds
            import numpy as np
            adaptive_model = fit_adaptive_model_from_training_rounds(raw_dir, b_name, train_rounds)
            
            for r in range(1, total_rounds + 1):
                # S0: Ideal simulator
                generate_simulator_round(
                    adversary_level="S0",
                    target_backend=backend_obj,
                    layout=layout,
                    round_id=r,
                    shots=shots,
                    num_chunks=num_chunks,
                    is_dryrun=True,
                    seed=42,
                )
                # S1: Calibration-derived simulator
                generate_simulator_round(
                    adversary_level="S1",
                    target_backend=backend_obj,
                    layout=layout,
                    round_id=r,
                    shots=shots,
                    num_chunks=num_chunks,
                    is_dryrun=True,
                    seed=42,
                )
                # S2: Adaptive impersonator
                generate_simulator_round(
                    adversary_level="S2",
                    target_backend=backend_obj,
                    layout=layout,
                    round_id=r,
                    shots=shots,
                    num_chunks=num_chunks,
                    is_dryrun=True,
                    adaptive_model=adaptive_model,
                    seed=42,
                )
        logger.info("[Dry-Run] All S0, S1, S2 simulations generated successfully.")
        return

    # Real Hardware Simulators (simulating against real hardware backends)
    import numpy as np
    token = os.environ.get("QISKIT_IBM_TOKEN")
    from qiskit_ibm_runtime import QiskitRuntimeService
    service = QiskitRuntimeService(token=token) if token else QiskitRuntimeService()
    
    real_backends_cfg = config["backends"].get("real_backends", [])
    for b_entry in real_backends_cfg:
        b_name = b_entry["name"]
        layout = b_entry["layout"]
        backend_obj = service.backend(b_name)
        
        adaptive_model = fit_adaptive_model_from_training_rounds(raw_dir, b_name, train_rounds)
        
        for r in range(1, total_rounds + 1):
            generate_simulator_round("S0", backend_obj, layout, r, shots, num_chunks, is_dryrun=False, seed=42)
            generate_simulator_round("S1", backend_obj, layout, r, shots, num_chunks, is_dryrun=False, seed=42)
            generate_simulator_round("S2", backend_obj, layout, r, shots, num_chunks, is_dryrun=False, adaptive_model=adaptive_model, seed=42)
            
    logger.info("Real backend matching simulations S0, S1, S2 generated successfully.")


if __name__ == "__main__":
    main()
