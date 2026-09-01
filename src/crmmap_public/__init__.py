"""Shareable CRMmap presentation and verification layer."""

from .tables import build_table_outputs
from .verify import validate_reference_inputs

__all__ = ["build_table_outputs", "validate_reference_inputs"]
