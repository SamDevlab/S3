from __future__ import annotations

import inspect
from dataclasses import dataclass

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends._native_assembly import (
    _generate_native_assembly_with_registry,
)
from bootstrap.s3.backends.registry import (
    BackendRegistry,
    create_builtin_backend_registry,
)
from bootstrap.s3.backends.x86_64 import (
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.backends.x86_64.backend import (
    generate_native_assembly as generate_native_assembly_from_backend,
)
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.targets import LINUX_X86_64_TARGET


def _program():
    return compile_source("fn main() -> tryte:\n    return 6\n").assembly


@dataclass(frozen=True, slots=True)
class _RecordingNativeAssemblyProvider:
    result: str
    calls: list[tuple[object, int, int, int]]

    def generate(
        self,
        program,
        *,
        max_memory_trits: int,
        max_frames: int,
        max_instructions: int,
    ) -> str:
        self.calls.append(
            (program, max_memory_trits, max_frames, max_instructions)
        )
        return self.result


@dataclass(frozen=True, slots=True)
class _FailingHostedProvider:
    def execute(self, program, entry: str = "main", **limits) -> int:
        del program, entry, limits
        raise AssertionError("hosted provider must not be used")


def _raised_by(callback) -> tuple[type[Exception], str]:
    with pytest.raises(Exception) as error:
        callback()
    return type(error.value), str(error.value)


def test_public_generate_native_assembly_signature_is_unchanged() -> None:
    signature = inspect.signature(generate_native_assembly)
    parameters = signature.parameters

    assert generate_native_assembly_from_backend is generate_native_assembly
    assert tuple(parameters) == (
        "program",
        "max_memory_trits",
        "max_frames",
        "max_instructions",
    )
    assert parameters["program"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    assert parameters["max_memory_trits"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_frames"].kind is inspect.Parameter.KEYWORD_ONLY
    assert parameters["max_instructions"].kind is inspect.Parameter.KEYWORD_ONLY
    assert "registry" not in parameters
    assert "target" not in parameters


def test_public_route_matches_direct_x86_64_backend_output() -> None:
    program = _program()
    limits = {
        "max_memory_trits": 6561,
        "max_frames": 7,
        "max_instructions": 123,
    }

    assert generate_native_assembly(program, **limits) == X8664Backend(
        **limits
    ).generate(program)


def test_private_route_selects_linux_x86_64_native_provider() -> None:
    program = _program()
    calls: list[tuple[object, int, int, int]] = []
    provider = _RecordingNativeAssemblyProvider("native assembly\n", calls)
    registry = BackendRegistry(
        hosted_execution=(("hosted", _FailingHostedProvider()),),
        native_assembly=((LINUX_X86_64_TARGET, provider),),
    )
    targets_before = registry.native_assembly_targets

    result = _generate_native_assembly_with_registry(
        program,
        max_memory_trits=99,
        max_frames=5,
        max_instructions=8,
        registry=registry,
    )

    assert result == "native assembly\n"
    assert calls == [(program, 99, 5, 8)]
    assert registry.native_assembly_targets == targets_before


@pytest.mark.parametrize(
    ("limits", "expected_message"),
    (
        (
            {"max_frames": 0, "max_instructions": True},
            "max_instructions must be an integer",
        ),
        (
            {"max_frames": 0, "max_instructions": 0},
            "max_frames must be at least 1",
        ),
    ),
)
def test_public_route_preserves_limit_error_type_message_and_order(
    limits,
    expected_message: str,
) -> None:
    program = _program()

    routed_error = _raised_by(
        lambda: generate_native_assembly(program, **limits)
    )

    assert routed_error == _raised_by(
        lambda: X8664Backend(**limits).generate(program)
    )
    assert expected_message in routed_error[1]


def test_public_route_preserves_program_validation_errors() -> None:
    program = parse_assembly(
        """\
.function main -> tryte
    .register r0, tryte
.label other
    TCONST r0, 6
    TRET r0
.end
"""
    )

    assert _raised_by(
        lambda: generate_native_assembly(program)
    ) == _raised_by(lambda: X8664Backend().generate(program))


def test_public_route_is_deterministic_without_mutating_builtin_registry() -> None:
    program = _program()
    registry_before = create_builtin_backend_registry()

    first = generate_native_assembly(program)
    second = generate_native_assembly(program)

    assert first == second
    assert registry_before.hosted_execution_names == ("hosted-emulator",)
    assert registry_before.native_assembly_targets == ("linux-x86_64",)
    assert create_builtin_backend_registry().native_assembly_targets == (
        "linux-x86_64",
    )
