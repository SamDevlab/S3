from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from bootstrap.s3.backends.x86_64 import NativeBackendError
from bootstrap.s3.backends.x86_64 import NativeToolchain
from tests.support.differential_execution import (
    DifferentialBackendUnavailable,
    DifferentialExecutionError,
    ExecutionObservation,
    GeneratedProgram,
    assert_four_path_equivalence,
    generate_programs,
    run_four_paths,
)

pytestmark = pytest.mark.s3_differential


def test_same_seed_is_reproducible_and_different_seeds_diverse() -> None:
    assert generate_programs(7, 5) == generate_programs(7, 5)
    assert generate_programs(7, 5) != generate_programs(8, 5)


def test_equivalence_accepts_four_matching_paths() -> None:
    program = GeneratedProgram(1, "fn main() -> tryte:\n    return 1\n")
    observations = tuple(
        ExecutionObservation(opt, mode, 1, "", "", 0)
        for opt, mode in (("O0", "emulator"), ("O0", "native"), ("O1", "emulator"), ("O1", "native"))
    )
    assert_four_path_equivalence(program, observations)


def test_divergence_contains_seed_and_reproducer() -> None:
    program = GeneratedProgram(42, "fn main() -> tryte:\n    return 1\n")
    observations = tuple(
        ExecutionObservation(opt, mode, value, "", "", 0)
        for opt, mode, value in (
            ("O0", "emulator", 1),
            ("O0", "native", 2),
            ("O1", "emulator", 1),
            ("O1", "native", 1),
        )
    )
    with pytest.raises(DifferentialExecutionError, match="seed=42.*source="):
        assert_four_path_equivalence(program, observations)


def test_timeout_is_not_treated_as_equivalence() -> None:
    program = GeneratedProgram(9, "fn main() -> tryte:\n    return 1\n")
    observations = tuple(
        ExecutionObservation(opt, mode, 1, "", "", 0, timed_out=(mode == "native"))
        for opt, mode in (("O0", "emulator"), ("O0", "native"), ("O1", "emulator"), ("O1", "native"))
    )
    with pytest.raises(DifferentialExecutionError, match="seed=9.*timeout"):
        assert_four_path_equivalence(program, observations)


def test_backend_unavailable_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    def unavailable():
        raise NativeBackendError("test backend unavailable")

    monkeypatch.setattr(
        "tests.support.differential_execution.NativeToolchain.detect",
        unavailable,
    )
    with pytest.raises(DifferentialBackendUnavailable, match="backend unavailable"):
        run_four_paths(GeneratedProgram(3, "fn main() -> tryte:\n    return 1\n"))


def test_native_path_builds_generated_x86_64_assembly() -> None:
    class RecordingToolchain:
        def __init__(self) -> None:
            self.assemblies: list[str] = []

        def build(self, assembly: str, output: Path) -> Path:
            self.assemblies.append(assembly)
            return output

        def run(
            self,
            executable: Path,
            *,
            timeout: float,
        ) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                [str(executable)],
                0,
                "program returned: 23\n",
                "",
            )

    toolchain = RecordingToolchain()
    program = GeneratedProgram(11, "fn main() -> tryte:\n    return 8 + 15\n")

    observations = run_four_paths(program, toolchain=toolchain)

    assert len(toolchain.assemblies) == 2
    assert all(
        assembly.startswith(".intel_syntax noprefix\n")
        for assembly in toolchain.assemblies
    )
    assert all(".s3asm" not in assembly for assembly in toolchain.assemblies)
    assert_four_path_equivalence(program, observations)


def test_generated_program_runs_all_four_paths() -> None:
    try:
        NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    program = generate_programs(11, 1)[0]
    observations = run_four_paths(program)
    assert_four_path_equivalence(program, observations)
