"""Experimental GNU assembly backend for Linux x86-64 ELF."""

from .backend import X8664Backend, generate_ffi_assembly, generate_native_assembly
from .diagnostics import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchainError,
)
from .layout import CalleeSavedSlot, CallerSavedSpillSlot, FrameLayout, layout_frame
from .toolchain import NativeToolchain
from .policy import BASELINE_NATIVE_POLICY, NativePolicy, policy_with

__all__ = [
    "CalleeSavedSlot",
    "CallerSavedSpillSlot",
    "FrameLayout",
    "NativeBackendError",
    "NativePlatformError",
    "NativeToolchain",
    "NativeToolchainError",
    "BASELINE_NATIVE_POLICY",
    "NativePolicy",
    "X8664Backend",
    "generate_native_assembly",
    "generate_ffi_assembly",
    "layout_frame",
    "policy_with",
]

