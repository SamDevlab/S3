"""S3 reference bootstrap compiler, artifacts, optimizer, and emulator."""

from .ir_serialization import deserialize_ir, serialize_ir
from .optimizer import OptimizationLevel
from .pipeline import CompilationCache, CompilationCacheInfo, compile_source, run_source

__all__ = [
    "OptimizationLevel",
    "CompilationCache",
    "CompilationCacheInfo",
    "compile_source",
    "deserialize_ir",
    "run_source",
    "serialize_ir",
]
