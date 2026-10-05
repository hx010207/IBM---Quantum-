"""QPU budget guard and execution time estimator for IBM Open Plan limits.

Enforces the strict rule that projected experiment quantum execution time
must NEVER exceed 85% of the remaining monthly QPU allowance (default 10 minutes = 600s).
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class BudgetExceededError(RuntimeError):
    """Raised when an operation would violate the 85% QPU budget safety limit."""
    pass


class QPUBudgetGuard:
    """Tracks, estimates, and guards QPU budget consumption."""

    def __init__(
        self,
        allowance_seconds: float = 600.0,
        safety_fraction: float = 0.85,
        state_file: Optional[Path] = None,
    ):
        """Initializes the budget guard.
        
        Args:
            allowance_seconds: Total monthly allowance (Open Plan = 600 seconds).
            safety_fraction: Maximum allowed utilization fraction (0.85).
            state_file: Path to persistent JSON file tracking used seconds.
        """
        self.allowance_seconds = allowance_seconds
        self.safety_fraction = safety_fraction
        self.max_allowed_seconds = allowance_seconds * safety_fraction
        self.state_file = state_file or Path("data/interim/budget_state.json")
        self.used_seconds = self._load_state()

    def _load_state(self) -> float:
        """Loads cumulative consumed quantum seconds from disk."""
        if self.state_file.exists():
            try:
                with open(self.state_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    return float(data.get("cumulative_quantum_seconds", 0.0))
            except Exception as e:
                logger.warning(f"Failed to read budget state file {self.state_file}: {e}")
        return 0.0

    def _save_state(self) -> None:
        """Persists cumulative consumed quantum seconds to disk."""
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "cumulative_quantum_seconds": self.used_seconds,
                        "allowance_seconds": self.allowance_seconds,
                        "max_allowed_seconds": self.max_allowed_seconds,
                        "remaining_safe_seconds": max(0.0, self.max_allowed_seconds - self.used_seconds),
                    },
                    f,
                    indent=2,
                )
        except Exception as e:
            logger.error(f"Failed to save budget state: {e}")

    def estimate_job_seconds(
        self,
        num_circuits: int = 10,
        shots_per_circuit: int = 2048,
        avg_circuit_time_seconds: float = 0.80,
    ) -> float:
        """Empirical estimate of job execution time in quantum seconds.
        
        For 3-qubit circuits at 2048 shots on IBM Heron hardware,
        the measured cost is 8.000s for a 10-circuit round (0.80s per circuit).
        
        Args:
            num_circuits: Number of circuits in the batch/job.
            shots_per_circuit: Shots requested per circuit.
            avg_circuit_time_seconds: Baseline empirical quantum seconds per 2048 shots.
            
        Returns:
            Projected quantum seconds.
        """
        scale = (shots_per_circuit / 2048.0)
        return num_circuits * avg_circuit_time_seconds * scale

    def check_preflight_budget(
        self,
        projected_job_seconds: float,
        is_dryrun: bool = False,
    ) -> Tuple[bool, str]:
        """Verifies if the projected job fits within the 85% safety limit.
        
        Args:
            projected_job_seconds: Quantum execution seconds estimated for the next job.
            is_dryrun: Whether running in dry-run mode (dry-run does not consume hardware time).
            
        Returns:
            Tuple of (is_safe: bool, status_message: str).
            
        Raises:
            BudgetExceededError: If the safety cap would be breached in real mode.
        """
        if is_dryrun:
            return True, f"Dry-run mode: {projected_job_seconds:.2f}s simulated (no real QPU budget consumed)."

        projected_total = self.used_seconds + projected_job_seconds
        remaining_safe = self.max_allowed_seconds - self.used_seconds

        msg = (
            f"Budget Check: Current Used = {self.used_seconds:.2f}s, "
            f"Projected Job = {projected_job_seconds:.2f}s, "
            f"Projected Total = {projected_total:.2f}s / {self.max_allowed_seconds:.2f}s (85% cap of {self.allowance_seconds}s). "
            f"Remaining Safe Budget = {remaining_safe:.2f}s."
        )

        if projected_total > self.max_allowed_seconds:
            err_msg = (
                f"SAFETY SHUTDOWN: Job projected to require {projected_job_seconds:.2f}s, which pushes "
                f"cumulative usage ({projected_total:.2f}s) beyond the 85% safety cap ({self.max_allowed_seconds:.2f}s)! "
                "Must reduce circuit count, shots, or backend count before proceeding."
            )
            logger.error(err_msg)
            raise BudgetExceededError(err_msg)

        return True, msg

    def record_job_consumption(
        self,
        measured_seconds: float,
        job_id: Optional[str] = None,
        is_dryrun: bool = False,
    ) -> float:
        """Records actual quantum seconds consumed by a completed job.
        
        Args:
            measured_seconds: Quantum seconds reported by job.usage() or metrics.
            job_id: Optional IBM Quantum Job ID for logging.
            is_dryrun: Whether this was a dry-run job.
            
        Returns:
            New cumulative used seconds.
        """
        if is_dryrun:
            logger.info(f"[Dry-Run] Recorded simulated job {job_id}: {measured_seconds:.3f}s")
            return self.used_seconds

        self.used_seconds += measured_seconds
        self._save_state()
        logger.info(
            f"Recorded Job {job_id}: used {measured_seconds:.3f}s. "
            f"New cumulative usage: {self.used_seconds:.2f}s / {self.max_allowed_seconds:.2f}s"
        )
        return self.used_seconds
