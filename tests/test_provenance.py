"""Unit tests for strict provenance enforcement and data integrity guards."""

import pandas as pd
import pytest
from qfp.provenance import (
    Provenance,
    ProvenanceViolationError,
    enforce_dataframe_provenance,
    validate_record_provenance,
)


def test_valid_dryrun_provenance():
    rec = {"provenance": "synthetic_dryrun", "backend": "fake_sherbrooke"}
    validate_record_provenance(rec, is_dryrun=True)


def test_reject_synthetic_in_production():
    rec = {"provenance": "synthetic_dryrun", "backend": "ibm_kyiv"}
    with pytest.raises(ProvenanceViolationError, match="strictly prohibited"):
        validate_record_provenance(rec, is_dryrun=False)


def test_reject_real_hardware_without_ibm_tag():
    df = pd.DataFrame([
        {"backend": "ibm_kyiv", "provenance": "aer_ideal", "val": 1.0}
    ])
    with pytest.raises(ProvenanceViolationError, match="Strict Provenance Guard Violation"):
        enforce_dataframe_provenance(df, is_dryrun=False)


def test_allow_genuine_hardware_in_production():
    df = pd.DataFrame([
        {"backend": "ibm_kyiv", "provenance": "ibm_hardware", "val": 1.0},
        {"backend": "sim_S1_ibm_kyiv", "provenance": "aer_noise_model", "val": 0.5},
    ])
    enforce_dataframe_provenance(df, is_dryrun=False)


def test_dryrun_dataframe_enforcement():
    df_valid = pd.DataFrame([
        {"backend": "fake_sherbrooke", "provenance": "synthetic_dryrun", "val": 1.0}
    ])
    enforce_dataframe_provenance(df_valid, is_dryrun=True)
    
    df_invalid = pd.DataFrame([
        {"backend": "fake_sherbrooke", "provenance": "ibm_hardware", "val": 1.0}
    ])
    with pytest.raises(ProvenanceViolationError):
        enforce_dataframe_provenance(df_invalid, is_dryrun=True)
