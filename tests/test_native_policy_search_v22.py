"""Focused V2.2 policy, canary, and corpus contracts."""

from __future__ import annotations

import platform

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64 import NativeToolchain, X8664Backend
from bootstrap.s3.backends.x86_64.experimental_policy import (
    ExperimentalNativePolicyMode,
    compact_ea_canary_eligible,
    parse_experimental_native_policy_mode,
    select_experimental_policy,
)
from bootstrap.s3.backends.x86_64.features import extract_function_features
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.backends.x86_64.policy import BASELINE_NATIVE_POLICY, policy_with
from bootstrap.s3.backends.x86_64.shadow_governor import ShadowGovernor
from tools.native_policy_search_v22 import POLICY_IDS, _policy_set, build_v22_corpus


def test_v22_policy_set_is_exactly_bounded() -> None:
    policies = _policy_set()
    assert tuple(policies) == POLICY_IDS
    assert policies["COMPACT_EA"].indexed_memory_policy == "compact_ea"
    assert policies["SCALAR"].scalar_promotion == "conservative_mem2reg"
    assert policies["COMPACT_EA_SCALAR"].indexed_memory_policy == "compact_ea"
    assert policies["COMPACT_EA_SCALAR"].scalar_promotion == "conservative_mem2reg"


def test_experimental_modes_fail_closed_and_default_off() -> None:
    assert parse_experimental_native_policy_mode(None) is ExperimentalNativePolicyMode.OFF
    assert parse_experimental_native_policy_mode("off") is ExperimentalNativePolicyMode.OFF
    assert parse_experimental_native_policy_mode("shadow") is ExperimentalNativePolicyMode.SHADOW
    assert parse_experimental_native_policy_mode("compact-ea-canary") is ExperimentalNativePolicyMode.COMPACT_EA_CANARY
    try:
        parse_experimental_native_policy_mode("production")
    except ValueError:
        pass
    else:
        raise AssertionError("unknown mode must fail closed")


def test_default_backend_and_explicit_off_keep_byte_identity() -> None:
    program = parse_assembly("""
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 7
    TRET r0
.end
""")
    assert X8664Backend().generate(program) == X8664Backend(native_policy=BASELINE_NATIVE_POLICY).generate(program)


def test_compact_ea_uses_live_logical_index_after_tmov_source_redefinition(tmp_path) -> None:
    program = parse_assembly("""
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .register r2, tryte
    .memory m0, tryte, 2, mutable
.label entry
    TCONST r0, 0
    TMOV r2, r0
    TCONST r0, 1
    TCONST r1, 7
    TSTORE m0, r2, r1
    TLOAD r1, m0, r2
    TRET r1
.end
""")
    assert Emulator().execute(program) == 7
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("requires Linux x86-64")
    policy = policy_with(name="reconciliation_compact_ea", indexed_memory_policy="compact_ea")
    toolchain = NativeToolchain.detect()
    for register_allocation in (False, True):
        assembly = X8664Backend(
            register_allocation=register_allocation,
            native_policy=policy,
        ).generate(program)
        executable = toolchain.build(
            assembly,
            tmp_path / f"compact-ea-tmov-index-{register_allocation}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        assert completed.stdout == "program returned: 7\n"


def test_canary_rejects_reference_sensitive_function() -> None:
    program = parse_assembly("""
.function main -> tryte
    .register r0, tryte
    .register r1, reference
.label entry
    TCONST r0, 1
    TADDR r1, r0
    TRET r0
.end
""")
    features = extract_function_features(program.functions[0])
    assert compact_ea_canary_eligible(features) is False
    assert select_experimental_policy(ExperimentalNativePolicyMode.COMPACT_EA_CANARY, features, _policy_set()) == ("BASELINE", "canary_safety_fallback")


def test_shadow_governor_whitelists_v22_and_falls_back_for_other_sets() -> None:
    program = parse_assembly("""
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 4, mutable
.label entry
    TCONST r0, 0
    TCONST r1, 3
    TSTORE m0, r0, r1
    TLOAD r1, m0, r0
    TRET r1
.end
""")
    features = extract_function_features(program.functions[0])
    decision = ShadowGovernor("BASELINE").recommend(features, _policy_set())
    assert decision.policy_id in {"COMPACT_EA", "COMPACT_EA_SCALAR"}
    fallback = ShadowGovernor("BASELINE").recommend(features, {"BASELINE": BASELINE_NATIVE_POLICY, "future": policy_with(name="future")})
    assert fallback.policy_id == "BASELINE"
    assert fallback.fallback_used is True


def test_v22_corpus_has_realistic_training_and_frozen_holdout() -> None:
    cases = build_v22_corpus()
    assert len(cases) >= 90
    assert {case.group for case in cases} >= {"attribution", "realistic-training", "realistic-holdout", "holdout-existing"}
    assert len({case.case_id for case in cases}) == len(cases)
    for case in cases:
        assert "benchmark" not in case.source.lower()
        assert "fixture" not in case.source.lower()
