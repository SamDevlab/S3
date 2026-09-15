from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from bootstrap.s3.diagnostics import S3Error
from bootstrap.s3.pipeline import compile_source
from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    canonical_json_document,
    decode_and_verify_source,
)
from tools.reliability_generator_v2 import (
    GENERATOR_VERSION,
    MALFORMED_FAMILIES,
    REQUIRED_VALID_FEATURES,
    VALID_FAMILIES,
    coverage_summary,
    generate_case,
    generate_cases,
    generator_manifest,
    valid_coverage_gaps,
)


pytestmark = [pytest.mark.s3_contract]
ROOT = Path(__file__).resolve().parent.parent


def test_r2_frozen_valid_vector() -> None:
    case = generate_case("r2-vector", 123, 0, "valid")
    assert case.case_seed == 433001260938302787
    assert case.family == "scalar-call"
    assert case.source == (
        b"fn add(a: tryte, b: tryte) -> tryte:\n"
        b"    return a + b\n\n"
        b"fn main() -> tryte:\n"
        b"    return add(17, 19)\n"
    )
    assert case.source_sha256 == (
        "85fdf536a55991b54a785f036c7f73515988296145af3cdc929963c2f1645341"
    )
    assert case.case_id == (
        "144a15ee9606fb32507226241b2dbb0900324dacb3664516b694c2eb92ae2f32"
    )


def test_r2_frozen_mutation_vector() -> None:
    case = generate_case("r2-vector", 123, 0, "mutated")
    assert case.case_seed == 2797293811038360610
    assert case.family == "scalar-call:replace-first-arrow"
    assert case.mutation == "replace-first-arrow"
    assert case.source == (
        b"fn add(a: tryte, b: tryte) => tryte:\n"
        b"    return a + b\n\n"
        b"fn main() -> tryte:\n"
        b"    return add(-6, 7)\n"
    )
    assert case.source_sha256 == (
        "4c65380db66dc27ef227366bf9ba886076ebba506ef51bd3d9616a02f2c29b4e"
    )


def test_r2_same_inputs_produce_byte_identical_cases() -> None:
    first = generate_cases("determinism", 991, "valid", 64)
    second = generate_cases("determinism", 991, "valid", 64)
    assert first == second
    assert canonical_json_document([case.metadata() for case in first]) == (
        canonical_json_document([case.metadata() for case in second])
    )


def test_r2_generator_is_independent_of_pythonhashseed() -> None:
    script = """
import json
from tools.reliability_generator_v2 import generate_cases
cases = generate_cases('hashseed', 8844, 'valid', 24)
print(json.dumps([(c.case_id, c.source_sha256) for c in cases], separators=(',', ':')))
"""
    outputs: list[str] = []
    for hash_seed in ("0", "1", "42"):
        env = os.environ.copy()
        env["PYTHONHASHSEED"] = hash_seed
        completed = subprocess.run(
            [sys.executable, "-c", script],
            cwd=ROOT,
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=20,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


def test_r2_first_valid_cycle_covers_every_required_feature() -> None:
    cases = generate_cases("coverage", 7, "valid", len(VALID_FAMILIES))
    assert tuple(case.family for case in cases) == VALID_FAMILIES
    assert valid_coverage_gaps(cases) == ()
    observed = {feature for case in cases for feature in case.features}
    assert REQUIRED_VALID_FEATURES <= observed


def test_r2_first_malformed_cycle_covers_every_family() -> None:
    cases = generate_cases("malformed", 7, "malformed", len(MALFORMED_FAMILIES))
    assert tuple(case.family for case in cases) == MALFORMED_FAMILIES
    assert all(case.expected_behavior == "REJECTION" for case in cases)


def test_r2_mutations_are_bounded_and_declared_rejections() -> None:
    cases = generate_cases("mutations", 99, "mutated", 32)
    assert all(case.expected_behavior == "REJECTION" for case in cases)
    assert all(case.mutation is not None for case in cases)
    assert all(case.source_bytes <= DEFAULT_RESOURCE_POLICY.source_max_bytes for case in cases)
    assert all("adversarial.mutation" in case.features for case in cases)


def test_r2_metadata_contains_no_source_or_host_nondeterminism() -> None:
    metadata = generate_case("metadata", 1, 3, "valid").metadata()
    assert "source" not in metadata
    forbidden = {"pid", "timestamp", "hostname", "absolute_path", "duration_ms"}
    assert forbidden.isdisjoint(metadata)


def test_r2_worker_request_preserves_exact_source_bytes() -> None:
    case = generate_case("transport", 55, 6, "valid")
    request = case.worker_request("a" * 40)
    assert decode_and_verify_source(
        request["source_b64"],
        request["source_sha256"],
        request["source_bytes"],
    ) == case.source
    assert request["case_id"] == case.case_id


def test_r2_coverage_summary_is_sorted_and_explicit() -> None:
    cases = (
        *generate_cases("summary", 77, "valid", 8),
        *generate_cases("summary", 77, "malformed", 6, start_index=8),
        *generate_cases("summary", 77, "mutated", 4, start_index=14),
    )
    summary = coverage_summary(cases)
    assert summary["total"] == 18
    assert list(summary["kinds"]) == sorted(summary["kinds"])
    assert list(summary["families"]) == sorted(summary["families"])
    assert list(summary["features"]) == sorted(summary["features"])
    assert summary["kinds"] == {"malformed": 6, "mutated": 4, "valid": 8}


def test_r2_manifest_records_single_source_module_boundary() -> None:
    manifest = generator_manifest()
    assert manifest["protocol"] == "s3.reliability.generator.v2"
    assert manifest["generator_version"] == GENERATOR_VERSION
    assert manifest["prng"] == "splitmix64-v1"
    assert manifest["multi_source_modules"] == "deferred-source-bundle-transport"


def test_r2_campaign_limit_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="campaign_max_cases"):
        generate_cases(
            "too-many",
            1,
            "valid",
            DEFAULT_RESOURCE_POLICY.campaign_max_cases + 1,
        )


@pytest.mark.parametrize("case_index", range(len(VALID_FAMILIES)))
def test_r2_each_valid_family_compiles(case_index: int) -> None:
    case = generate_case("compile-valid", 2026, case_index, "valid")
    compile_source(case.source.decode("utf-8"))


@pytest.mark.parametrize("case_index", range(len(MALFORMED_FAMILIES)))
def test_r2_each_malformed_family_is_rejected(case_index: int) -> None:
    case = generate_case("compile-malformed", 2026, case_index, "malformed")
    with pytest.raises(S3Error):
        compile_source(case.source.decode("utf-8"))


@pytest.mark.parametrize("case_index", range(len(VALID_FAMILIES)))
def test_r2_each_mutation_is_rejected(case_index: int) -> None:
    case = generate_case("compile-mutated", 2026, case_index, "mutated")
    with pytest.raises(S3Error):
        compile_source(case.source.decode("utf-8"))
