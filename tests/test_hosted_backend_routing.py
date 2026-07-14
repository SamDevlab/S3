from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from bootstrap.s3.assembly import AssemblyProgram, parse_assembly
from bootstrap.s3.backends._hosted_execution import (
    _execute_hosted_assembly_with_registry,
)
from bootstrap.s3.backends.registry import (
    BackendRegistry,
    create_builtin_backend_registry,
)
from bootstrap.s3.emulator import Emulator, execute_assembly
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.targets import LINUX_X86_64_TARGET


def _program() -> AssemblyProgram:
    return compile_source("fn main() -> tryte:\n    return 6\n").assembly


@dataclass(frozen=True, slots=True)
class _RecordingHostedProvider:
    result: int
    calls: list[tuple[object, str, int, int, int]]

    def execute(
        self,
        program,
        entry: str = "main",
        *,
        max_frames: int,
        max_instructions: int,
        max_memory_trits: int,
    ) -> int:
        self.calls.append(
            (
                program,
                entry,
                max_frames,
                max_instructions,
                max_memory_trits,
            )
        )
        return self.result


@dataclass(frozen=True, slots=True)
class _FailingNativeProvider:
    def generate(self, program, **limits) -> str:
        del program, limits
        raise AssertionError("native provider must not be used")


def _raised_by(callback) -> tuple[type[Exception], str]:
    with pytest.raises(Exception) as error:
        callback()
    return type(error.value), str(error.value)


def test_execute_assembly_signature_is_unchanged() -> None:
    parameters = inspect.signature(execute_assembly).parameters

    assert tuple(parameters) == (
        "assembly",
        "entry",
        "max_frames",
        "max_instructions",
        "max_memory_trits",
    )
    assert parameters["assembly"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["entry"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["max_frames"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_instructions"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_memory_trits"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "registry" not in parameters
    assert "provider" not in parameters
    assert "target" not in parameters


def test_run_source_signature_is_unchanged() -> None:
    parameters = inspect.signature(run_source).parameters

    assert tuple(parameters) == (
        "source",
        "entry",
        "optimization",
        "max_frames",
        "max_instructions",
        "mode",
    )
    assert parameters["source"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["entry"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["optimization"].kind is (
        inspect.Parameter.POSITIONAL_OR_KEYWORD
    )
    assert parameters["max_frames"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_instructions"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["mode"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "registry" not in parameters
    assert "provider" not in parameters
    assert "target" not in parameters


def test_execute_assembly_matches_direct_emulator_result() -> None:
    program = _program()

    assert execute_assembly(program) == Emulator().execute(program)
    assert execute_assembly(program.render()) == Emulator().execute(program)


def test_run_source_matches_compile_source_and_direct_emulator_result() -> None:
    source = "fn helper(value: tryte) -> tryte:\n    return value + 1\nfn main() -> tryte:\n    return helper(5)\n"
    compilation = compile_source(source, "O1")

    assert run_source(source, optimization="O1") == Emulator().execute(
        compilation.assembly
    )


def test_private_route_selects_hosted_emulator_provider_and_limits() -> None:
    program = _program()
    calls: list[tuple[object, str, int, int, int]] = []
    provider = _RecordingHostedProvider(42, calls)
    registry = BackendRegistry(
        hosted_execution=(("hosted-emulator", provider),),
        native_assembly=((LINUX_X86_64_TARGET, _FailingNativeProvider()),),
    )
    hosted_before = registry.hosted_execution_names
    native_before = registry.native_assembly_targets

    result = _execute_hosted_assembly_with_registry(
        program,
        "main",
        max_frames=5,
        max_instructions=8,
        max_memory_trits=13,
        registry=registry,
    )

    assert result == 42
    assert calls == [(program, "main", 5, 8, 13)]
    assert registry.hosted_execution_names == hosted_before
    assert registry.native_assembly_targets == native_before


def test_execute_assembly_preserves_entry_and_public_errors() -> None:
    program = parse_assembly(
        """\
.function alternate -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 9
    TRET r0
.end

.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 6
    TRET r0
.end
"""
    )

    assert execute_assembly(program, entry="alternate") == Emulator().execute(
        program,
        "alternate",
    )
    assert _raised_by(
        lambda: execute_assembly(program, entry="missing")
    ) == _raised_by(lambda: Emulator().execute(program, "missing"))


@pytest.mark.parametrize(
    "limits",
    (
        {"max_frames": 0, "max_instructions": 0},
        {"max_frames": 1, "max_instructions": 0},
    ),
)
def test_execute_assembly_preserves_limit_error_type_message_and_order(
    limits,
) -> None:
    program = _program()
    routed_error = _raised_by(lambda: execute_assembly(program, **limits))

    assert routed_error == _raised_by(lambda: Emulator(**limits).execute(program))


def test_run_source_preserves_limit_errors() -> None:
    source = "fn main() -> tryte:\n    return 6\n"

    assert _raised_by(
        lambda: run_source(source, max_frames=0, max_instructions=0)
    ) == _raised_by(lambda: Emulator(max_frames=0, max_instructions=0))


def test_frame_and_instruction_limits_still_come_from_emulator() -> None:
    recursive = """\
fn recurse() -> tryte:
    return recurse()
fn main() -> tryte:
    return recurse()
"""
    program = compile_source(recursive).assembly

    assert _raised_by(
        lambda: execute_assembly(program, max_frames=2)
    ) == _raised_by(lambda: Emulator(max_frames=2).execute(program))
    assert _raised_by(
        lambda: execute_assembly(program, max_instructions=1)
    ) == _raised_by(lambda: Emulator(max_instructions=1).execute(program))


def test_public_routes_are_deterministic_without_mutating_builtin_registry() -> None:
    program = _program()
    source = "fn main() -> tryte:\n    return 6\n"
    registry_before = create_builtin_backend_registry()

    assert execute_assembly(program) == execute_assembly(program)
    assert run_source(source) == run_source(source)
    assert registry_before.hosted_execution_names == ("hosted-emulator",)
    assert registry_before.native_assembly_targets == ("linux-x86_64",)
    assert create_builtin_backend_registry().hosted_execution_names == (
        "hosted-emulator",
    )
