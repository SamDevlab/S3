"""Small, deterministic O0/O1 emulator/native differential harness."""

from __future__ import annotations

import random
import re
from dataclasses import dataclass
from pathlib import Path
from tempfile import TemporaryDirectory

from bootstrap.s3.backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source


class DifferentialExecutionError(AssertionError):
    """A four-path run failed with reproducible context."""


class DifferentialBackendUnavailable(RuntimeError):
    """The requested native backend cannot run on this host."""


@dataclass(frozen=True, slots=True)
class GeneratedProgram:
    seed: int
    source: str


@dataclass(frozen=True, slots=True)
class ExecutionObservation:
    optimization: str
    execution_mode: str
    return_value: int | None
    stdout: str
    stderr: str
    exit_status: int | None
    error: str | None = None
    timed_out: bool = False


def generate_programs(seed: int, count: int = 8) -> tuple[GeneratedProgram, ...]:
    if count < 1 or count > 32:
        raise ValueError("count must be between 1 and 32")
    rng = random.Random(seed)
    programs: list[GeneratedProgram] = []
    templates = (
        "fn main() -> tryte:\n    return {a} + {b}\n",
        "fn main() -> tryte:\n    return {a} <=> {b}\n",
        "fn main() -> tryte:\n    match {a} <=> {b}:\n        -1:\n            return -1\n        0:\n            return 0\n        else:\n            return 1\n",
    )
    for index in range(count):
        a = rng.randint(-20, 20)
        b = rng.randint(-20, 20)
        programs.append(GeneratedProgram(seed + index, templates[index % len(templates)].format(a=a, b=b)))
    return tuple(programs)


def run_four_paths(
    program: GeneratedProgram,
    *,
    toolchain: NativeToolchain | None = None,
    max_frames: int = 32,
    max_instructions: int = 10_000,
    native_timeout: float = 30.0,
) -> tuple[ExecutionObservation, ...]:
    """Run O0/O1 through the emulator and native backend with bounded limits."""
    try:
        native = toolchain or NativeToolchain.detect()
    except NativeBackendError as error:
        raise DifferentialBackendUnavailable(str(error)) from error

    observations: list[ExecutionObservation] = []
    with TemporaryDirectory(prefix="s3-differential-") as temporary:
        output_root = Path(temporary)
        for optimization in ("O0", "O1"):
            try:
                compilation = compile_source(
                    program.source,
                    optimization,
                    mode=SyntaxMode.V0_6,
                )
                result = Emulator(
                    max_frames=max_frames,
                    max_instructions=max_instructions,
                ).execute(compilation.assembly)
            except Exception as error:
                raise DifferentialExecutionError(
                    _context(program, optimization, "emulator", error)
                ) from error
            observations.append(
                ExecutionObservation(
                    optimization,
                    "emulator",
                    result if isinstance(result, int) else None,
                    "",
                    "",
                    0,
                )
            )

            try:
                native_assembly = generate_native_assembly(
                    compilation.assembly,
                    max_frames=max_frames,
                    max_instructions=max_instructions,
                )
                executable = native.build(
                    native_assembly,
                    output_root / f"{optimization.lower()}-native",
                )
                completed = native.run(executable, timeout=native_timeout)
            except Exception as error:
                raise DifferentialExecutionError(
                    _context(program, optimization, "native", error)
                ) from error
            match = re.fullmatch(r"program returned: (-?\d+)\n", completed.stdout)
            native_result = int(match.group(1)) if match else None
            observations.append(
                ExecutionObservation(
                    optimization,
                    "native",
                    native_result,
                    completed.stdout,
                    completed.stderr,
                    completed.returncode,
                    error=None if match else "unexpected native result output",
                )
            )
    return tuple(observations)


def assert_four_path_equivalence(
    program: GeneratedProgram,
    observations: tuple[ExecutionObservation, ...],
) -> None:
    if len(observations) != 4:
        raise DifferentialExecutionError(_context(program, "all", "matrix", "expected four observations"))
    first = observations[0]
    for observation in observations:
        if observation.error or observation.timed_out:
            raise DifferentialExecutionError(_context(program, observation.optimization, observation.execution_mode, observation.error or "timeout"))
        if observation.exit_status != first.exit_status:
            raise DifferentialExecutionError(_context(program, observation.optimization, observation.execution_mode, "exit status mismatch"))
        if observation.return_value != first.return_value:
            raise DifferentialExecutionError(_context(program, observation.optimization, observation.execution_mode, "return value mismatch"))


def _context(program: GeneratedProgram, optimization: str, mode: str, error: object) -> str:
    return f"seed={program.seed} optimization={optimization} mode={mode}: {error}; source={program.source!r}"
