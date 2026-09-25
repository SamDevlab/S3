"""Experimental GNU assembly backend for Linux x86-64 ELF."""

from .backend import X8664Backend, generate_ffi_assembly, generate_native_assembly
from .diagnostics import (
    NativeBackendError,
    NativePlatformError,
    NativeToolchainError,
)
from .instruction_budget import InstructionBudgetMode
from .layout import CalleeSavedSlot, CallerSavedSpillSlot, FrameLayout, layout_frame
from .native_policy import NativeCodegenPolicy, NativePolicySummary
from .toolchain import NativeToolchain

__all__ = [
    "CalleeSavedSlot",
    "CallerSavedSpillSlot",
    "FrameLayout",
    "NativeBackendError",
    "NativePlatformError",
    "NativeToolchain",
    "NativeToolchainError",
    "NativeCodegenPolicy",
    "NativePolicySummary",
    "InstructionBudgetMode",
    "X8664Backend",
    "generate_native_assembly",
    "generate_ffi_assembly",
    "layout_frame",
]

