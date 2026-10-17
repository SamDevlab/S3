"""Experimental, provider-neutral S3 Quantum foundation."""

from .ir import (
    DiagnosticCode, QuantumDiagnostic, QuantumInstruction, QuantumProgram,
    QuantumTarget, S3QuantumIR, emit_openqasm3, validate_capabilities,
)
from .providers import QuantumProvider, QirBackend, QirCapabilities, QirTargetProfile

__all__ = [
    "DiagnosticCode", "QuantumDiagnostic", "QuantumInstruction", "QuantumProgram",
    "QuantumTarget", "S3QuantumIR", "emit_openqasm3", "validate_capabilities",
    "QuantumProvider", "QirBackend", "QirCapabilities", "QirTargetProfile",
]
