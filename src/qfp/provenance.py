"""Provenance enforcement and data integrity tracking for QFP experiments.

Every measurement result, raw data record, and derived feature vector MUST
bear an explicit provenance tag to prevent fabrication, relabeling, or accidental
mixing of synthetic and real data.
"""

from enum import Enum
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Union
import pandas as pd


class Provenance(str, Enum):
    """Enumeration of allowed data provenance origins."""
    IBM_HARDWARE = "ibm_hardware"
    AER_IDEAL = "aer_ideal"
    AER_NOISE_MODEL = "aer_noise_model"
    SYNTHETIC_DRYRUN = "synthetic_dryrun"


class ProvenanceViolationError(ValueError):
    """Raised when data provenance is missing, forged, or invalid for the operational context."""
    pass


def validate_record_provenance(record: Dict[str, Any], is_dryrun: bool = False) -> None:
    """Validates the provenance tag of an individual data dictionary.
    
    Args:
        record: Data record dictionary containing at least 'provenance' and 'class_type' or 'backend'.
        is_dryrun: Whether the pipeline is currently operating in dry-run mode.
        
    Raises:
        ProvenanceViolationError: If provenance is invalid, missing, or mismatched with run mode.
    """
    if "provenance" not in record:
        raise ProvenanceViolationError("Data record is missing required 'provenance' field.")
    
    prov = record["provenance"]
    valid_provs = {p.value for p in Provenance}
    if prov not in valid_provs:
        raise ProvenanceViolationError(f"Invalid provenance value '{prov}'. Must be one of {valid_provs}.")
    
    if is_dryrun:
        if prov != Provenance.SYNTHETIC_DRYRUN.value:
            raise ProvenanceViolationError(
                f"Dry-run mode requires provenance '{Provenance.SYNTHETIC_DRYRUN.value}', but found '{prov}'."
            )
    else:
        if prov == Provenance.SYNTHETIC_DRYRUN.value:
            raise ProvenanceViolationError(
                "Publication/real mode encountered 'synthetic_dryrun' data! "
                "Synthetic data is strictly prohibited in real analyses and publication figures."
            )


def enforce_dataframe_provenance(
    df: pd.DataFrame,
    is_dryrun: bool = False,
    allow_simulators_in_pub: bool = True
) -> None:
    """Enforces strict provenance constraints across a complete Pandas DataFrame.
    
    In real publication mode (is_dryrun=False):
      - Real backend classes (e.g. class starting with 'R' or backend starting with 'ibm_')
        MUST have provenance == 'ibm_hardware'.
      - No synthetic_dryrun rows are permitted under any circumstances.
    
    In dry-run mode (is_dryrun=True):
      - All rows MUST have provenance == 'synthetic_dryrun'.
      
    Args:
        df: Pandas DataFrame with 'provenance' column.
        is_dryrun: Flag indicating dry-run mode.
        allow_simulators_in_pub: Whether S0 (aer_ideal) and S1/S2 (aer_noise_model) are permitted in real runs.
        
    Raises:
        ProvenanceViolationError: If any row fails provenance validation.
    """
    if "provenance" not in df.columns:
        raise ProvenanceViolationError("DataFrame is missing required 'provenance' column.")
    
    unique_provs = set(df["provenance"].unique())
    
    if is_dryrun:
        non_dryrun = unique_provs - {Provenance.SYNTHETIC_DRYRUN.value}
        if non_dryrun:
            raise ProvenanceViolationError(
                f"Dry-run data contains unauthorized provenance tags: {non_dryrun}. Expected only 'synthetic_dryrun'."
            )
    else:
        if Provenance.SYNTHETIC_DRYRUN.value in unique_provs:
            count = (df["provenance"] == Provenance.SYNTHETIC_DRYRUN.value).sum()
            raise ProvenanceViolationError(
                f"Strict Provenance Guard Violation: Found {count} rows tagged with 'synthetic_dryrun' "
                "in a production dataset. Processing halted to prevent corrupted scientific findings."
            )
        
        # Verify that real backend rows carry ibm_hardware provenance
        if "backend" in df.columns:
            real_mask = df["backend"].astype(str).str.startswith("ibm_")
            real_non_hw = df[real_mask & (df["provenance"] != Provenance.IBM_HARDWARE.value)]
            if not real_non_hw.empty:
                raise ProvenanceViolationError(
                    f"Strict Provenance Guard Violation: Found {len(real_non_hw)} rows claiming real hardware "
                    f"backend names without '{Provenance.IBM_HARDWARE.value}' provenance!"
                )


def compute_file_sha256(filepath: Union[str, Path]) -> str:
    """Computes SHA256 checksum for immutable raw data file verification."""
    path = Path(filepath)
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest()


def generate_data_manifest(directory: Union[str, Path], output_file: Union[str, Path]) -> Dict[str, str]:
    """Generates an append-only cryptographic manifest of all raw data files.
    
    Args:
        directory: Directory containing raw data files.
        output_file: Path to write the manifest JSON.
        
    Returns:
        Dictionary mapping relative file paths to their SHA256 checksums.
    """
    dir_path = Path(directory)
    manifest = {}
    if dir_path.exists():
        for file in sorted(dir_path.rglob("*")):
            if file.is_file() and not file.name.endswith(".manifest.json"):
                rel_path = str(file.relative_to(dir_path)).replace("\\", "/")
                manifest[rel_path] = compute_file_sha256(file)
    
    out_path = Path(output_file)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    import json
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)
    return manifest
