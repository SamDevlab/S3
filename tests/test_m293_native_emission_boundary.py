"""M2.93 explicit native emission boundary contracts."""

from pathlib import Path

import pytest

from bootstrap.s3.canonical_ir_candidate import (
    CanonicalIRBlock,
    CanonicalIRFunction,
    CanonicalIRInstruction,
    CanonicalIRProgram,
)
from bootstrap.s3.ir import IRType, IROpcode
from bootstrap.s3.native_emission_boundary import (
    NativeEmissionBoundaryError,
    run_native_emission_boundary_differential,
)


ROOT = Path(__file__).parents[1]
SELFHOST_SOURCE = (
    ROOT / "selfhost" / "native" / "native_emission_boundary_candidate.s3"
).read_text(encoding="utf-8")


def _program() -> CanonicalIRProgram:
    return CanonicalIRProgram(
        functions=(
            CanonicalIRFunction(
                name_id=0,
                return_type=IRType.TRYTE,
                register_types=(IRType.TRYTE, IRType.TRYTE),
                blocks=(
                    CanonicalIRBlock(
                        name_id=0,
                        instructions=(
                            CanonicalIRInstruction(IROpcode.CONST, result=0, immediate=1),
                            CanonicalIRInstruction(IROpcode.ADD, result=1, operands=(0, 0)),
                            CanonicalIRInstruction(IROpcode.RETURN, operands=(1,)),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_candidate_source_has_one_native_boundary_entrypoint_and_no_main() -> None:
    assert "fn prepare_native_plan" in SELFHOST_SOURCE
    assert "fn main" not in SELFHOST_SOURCE


@pytest.mark.parametrize("target", ["x86_64", "aarch64", "macos_arm64"])
def test_native_boundary_is_deterministic_and_requires_host_tool(target: str) -> None:
    reference, candidate = run_native_emission_boundary_differential(_program(), target)
    assert reference == candidate
    assert reference.host_tool_required
    assert reference.native_artifact is None
    assert reference.target == target
    assert reference.assembly_text.startswith(".s3asm 0.6.0\n")


def test_unknown_target_fails_closed_without_host_tool_fallback() -> None:
    with pytest.raises(NativeEmissionBoundaryError, match="unsupported native target"):
        run_native_emission_boundary_differential(_program(), "wasm32")
