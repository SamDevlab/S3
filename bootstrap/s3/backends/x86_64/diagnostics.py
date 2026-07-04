"""User-facing failures from the experimental x86-64 backend."""

from __future__ import annotations


class NativeBackendError(Exception):
    """Base error reported by native backend operations."""


class NativePlatformError(NativeBackendError):
    """Raised when native build or execution is unavailable on this host."""


class NativeToolchainError(NativeBackendError):
    """Raised when assembling, linking, or running a native program fails."""

