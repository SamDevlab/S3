"""User-facing failures from the experimental x86-64 backend."""

from __future__ import annotations

from typing import Mapping

from ...diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
)


class NativeBackendError(Exception):
    """Base error reported by native backend operations."""

    diagnostic_category = DiagnosticCategory.VERIFICATION
    diagnostic_code = DiagnosticCode.NATIVE_BACKEND
    diagnostic_phase = DiagnosticPhase.NATIVE_BACKEND

    def __init__(
        self,
        message: str,
        *,
        diagnostic_code: DiagnosticCode | None = None,
        diagnostic_context: Mapping[str, object] | None = None,
    ) -> None:
        self.message = message
        self.diagnostic_message = message
        if diagnostic_code is not None:
            self.diagnostic_code = diagnostic_code
        self.diagnostic_context = dict(diagnostic_context or {})
        super().__init__(message)


class NativePlatformError(NativeBackendError):
    """Raised when native build or execution is unavailable on this host."""

    diagnostic_category = DiagnosticCategory.UNSUPPORTED_TARGET
    diagnostic_code = DiagnosticCode.UNSUPPORTED_TARGET
    diagnostic_phase = DiagnosticPhase.TOOLCHAIN


class NativeToolchainError(NativeBackendError):
    """Raised when assembling, linking, or running a native program fails."""

    diagnostic_category = DiagnosticCategory.TOOLCHAIN
    diagnostic_code = DiagnosticCode.TOOLCHAIN_FAILED
    diagnostic_phase = DiagnosticPhase.TOOLCHAIN
