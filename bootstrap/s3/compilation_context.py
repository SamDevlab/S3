"""Internal compilation state shared across pipeline stages."""

from __future__ import annotations

from dataclasses import dataclass

from .lexer import SyntaxMode
from .optimizer import OptimizationLevel


@dataclass(frozen=True, slots=True)
class CompilationContext:
    optimization: OptimizationLevel | str = OptimizationLevel.O0
    mode: SyntaxMode = SyntaxMode.V0_6
