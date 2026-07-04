"""End-to-end orchestration for the S3 bootstrap toolchain."""

from __future__ import annotations

from dataclasses import dataclass

from . import ast
from .assembly import AssemblyProgram
from .codegen import generate_assembly
from .emulator import DEFAULT_MAX_FRAMES, Emulator
from .ir import IRProgram
from .lexer import Token, tokenize
from .lowering import lower
from .optimizer import OptimizationLevel, optimize_ir
from .parser import parse_tokens
from .semantic import SemanticModel, analyze


@dataclass(frozen=True, slots=True)
class CompilationResult:
    tokens: tuple[Token, ...]
    ast: ast.Program
    semantic_model: SemanticModel
    ir: IRProgram
    assembly: AssemblyProgram

    @property
    def assembly_text(self) -> str:
        return self.assembly.render()


def compile_source(
    source: str,
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
) -> CompilationResult:
    tokens = tokenize(source)
    syntax_tree = parse_tokens(tokens)
    semantic_model = analyze(syntax_tree)
    ir_program = optimize_ir(
        lower(syntax_tree, semantic_model),
        optimization,
    )
    assembly_program = generate_assembly(ir_program)
    return CompilationResult(
        tokens,
        syntax_tree,
        semantic_model,
        ir_program,
        assembly_program,
    )


def run_source(
    source: str,
    entry: str = "main",
    optimization: OptimizationLevel | str = OptimizationLevel.O0,
    *,
    max_frames: int = DEFAULT_MAX_FRAMES,
) -> int:
    compilation = compile_source(source, optimization)
    return Emulator(max_frames=max_frames).execute(compilation.assembly, entry)
