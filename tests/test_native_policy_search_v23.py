"""Focused V2.3 compact-EA canary contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyOpcode,
    AssemblyProgram,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.backends.x86_64 import X8664Backend
from bootstrap.s3.backends.x86_64.diagnostics import NativeBackendError
from bootstrap.s3.backends.x86_64.experimental_policy import (
    ExperimentalNativePolicyMode,
    compact_ea_canary_policy,
    parse_experimental_native_policy_mode,
    resolve_experimental_policies,
)
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY, policy_with


def _indexed_program() -> object:
    return parse_assembly(
        """
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 2, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 7
    TSTORE m0, r0, r1
    TLOAD r1, m0, r0
    TRET r1
.end
"""
    )


def _reference_sensitive_program() -> object:
    return AssemblyProgram(
        (
            AssemblyFunction(
                name="main",
                return_type=AssemblyType.TRYTE,
                parameters=(),
                register_types=((0, AssemblyType.TRYTE), (1, AssemblyType.REFERENCE)),
                blocks=(
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(AssemblyOpcode.TCONST, (0,), immediate=1),
                            AssemblyInstruction(
                                AssemblyOpcode.TADDR,
                                (1, 0),
                                reference_target=AssemblyType.TRYTE,
                                reference_mutable=True,
                            ),
                            AssemblyInstruction(AssemblyOpcode.TRET, (0,)),
                        ),
                    ),
                ),
                reference_targets=((1, AssemblyType.TRYTE, True),),
            ),
        ),
    )


def test_v23_mode_contract_is_explicit_and_fail_closed() -> None:
    assert parse_experimental_native_policy_mode(None) is ExperimentalNativePolicyMode.OFF
    assert parse_experimental_native_policy_mode("off") is ExperimentalNativePolicyMode.OFF
    assert parse_experimental_native_policy_mode("shadow") is ExperimentalNativePolicyMode.SHADOW
    assert parse_experimental_native_policy_mode("compact-ea-canary") is ExperimentalNativePolicyMode.COMPACT_EA_CANARY
    with pytest.raises(ValueError):
        parse_experimental_native_policy_mode("autonomous")


def test_canary_changes_only_indexed_memory_policy() -> None:
    canary = compact_ea_canary_policy()
    assert canary.indexed_memory_policy == "compact_ea"
    assert canary.scalar_promotion == BASELINE_NATIVE_POLICY.scalar_promotion
    assert canary.spill_policy == BASELINE_NATIVE_POLICY.spill_policy
    assert canary.rematerialization == BASELINE_NATIVE_POLICY.rematerialization
    assert canary.live_range_split == BASELINE_NATIVE_POLICY.live_range_split
    assert canary.move_coalescing == BASELINE_NATIVE_POLICY.move_coalescing
    assert canary.load_forwarding == BASELINE_NATIVE_POLICY.load_forwarding
    assert canary.writeback_policy == BASELINE_NATIVE_POLICY.writeback_policy


def test_off_and_shadow_are_byte_identical_to_canonical_baseline() -> None:
    program = _indexed_program()
    baseline = X8664Backend().generate(program)
    assert X8664Backend(experimental_mode="off").generate(program) == baseline
    assert X8664Backend(experimental_mode="shadow").generate(program) == baseline


def test_canary_is_explicit_and_function_local() -> None:
    program = _indexed_program()
    selections = resolve_experimental_policies(program, "compact-ea-canary")
    assert selections["main"].applied is True
    assert selections["main"].policy.indexed_memory_policy == "compact_ea"
    assert selections["main"].policy.scalar_promotion == "disabled"
    assert X8664Backend(experimental_mode="compact-ea-canary").generate(program) != X8664Backend().generate(program)


def test_reference_sensitive_canary_falls_back_exactly_to_baseline() -> None:
    program = _reference_sensitive_program()
    selection = resolve_experimental_policies(program, "compact-ea-canary")["main"]
    assert selection.applied is False
    assert selection.reason.startswith("canary_safety_fallback:")
    assert X8664Backend(experimental_mode="compact-ea-canary").generate(program) == X8664Backend().generate(program)


def test_canary_rejects_explicit_nonbaseline_policy_composition() -> None:
    program = _indexed_program()
    scalar = policy_with(name="scalar_only", scalar_promotion="conservative_mem2reg")
    with pytest.raises(NativeBackendError, match="experimental policy modes"):
        X8664Backend(native_policy=scalar, experimental_mode="compact-ea-canary").generate(program)


def test_canary_resolution_is_independent_of_case_names() -> None:
    first = _indexed_program()
    second = parse_assembly(first.render().replace(".function main", ".function renamed", 1).replace("TRET r1", "TRET r1", 1))
    assert resolve_experimental_policies(first, "compact-ea-canary")["main"].applied is True
    assert resolve_experimental_policies(second, "compact-ea-canary")["renamed"].applied is True
