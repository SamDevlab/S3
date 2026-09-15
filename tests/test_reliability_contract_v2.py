from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import reliability_contract_v2 as contract


ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "spec" / "reliability"

EXPECTED_OUTCOMES = (
    "PASS",
    "EXPECTED_REJECTION",
    "UNEXPECTED_REJECTION",
    "UNEXPECTED_ACCEPT",
    "MISCOMPILE",
    "CRASH",
    "TIMEOUT",
    "NONDETERMINISM",
    "RESOURCE_LIMIT",
    "HARNESS_ERROR",
)

EXPECTED_RESOURCE_POLICY = {
    "hosted_case_wall_ms": 5000,
    "native_case_wall_ms": 20000,
    "kill_grace_ms": 250,
    "stdout_max_bytes": 1048576,
    "stderr_max_bytes": 1048576,
    "source_max_bytes": 32768,
    "campaign_max_cases": 10000,
    "campaign_wall_ms": 3600000,
    "max_parallel_children": 1,
    "replay_bundle_max_bytes": 4194304,
    "minimizer_max_evaluations": 10000,
}


def _load(name: str) -> dict:
    return json.loads((SPEC / name).read_text(encoding="utf-8"))


def _walk_keys(value):
    if isinstance(value, dict):
        for key, child in value.items():
            yield key
            yield from _walk_keys(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_keys(child)


def test_r0_schema_identities_are_frozen() -> None:
    assert _load("case-result.schema.json")["properties"]["schema"]["const"] == (
        contract.CASE_RESULT_SCHEMA
    )
    assert _load("report.schema.json")["properties"]["schema"]["const"] == (
        contract.CAMPAIGN_REPORT_SCHEMA
    )
    assert _load("replay.schema.json")["properties"]["schema"]["const"] == contract.REPLAY_SCHEMA
    assert _load("worker-request.schema.json")["properties"]["schema"]["const"] == (
        contract.WORKER_REQUEST_SCHEMA
    )
    assert _load("worker-response.schema.json")["properties"]["schema"]["const"] == (
        contract.WORKER_RESPONSE_SCHEMA
    )


def test_r0_failure_taxonomy_is_exact() -> None:
    assert contract.OUTCOMES == EXPECTED_OUTCOMES
    case_schema = _load("case-result.schema.json")
    assert tuple(case_schema["properties"]["outcome"]["enum"]) == EXPECTED_OUTCOMES


def test_r0_resource_policy_is_exact() -> None:
    assert contract.DEFAULT_RESOURCE_POLICY.to_dict() == EXPECTED_RESOURCE_POLICY
    report = _load("report.schema.json")
    properties = report["properties"]["resource_policy"]["properties"]
    assert {name: item["const"] for name, item in properties.items()} == EXPECTED_RESOURCE_POLICY


def test_r0_seed_derivation_vector() -> None:
    assert contract.derive_case_seed(
        42,
        7,
        "s3.reliability.generator.v2.0.0",
        "valid",
    ) == 4153593214656228440


def test_r0_case_identity_vector() -> None:
    source = b"fn main() -> trit:\n    return 0\n"
    source_sha = contract.sha256_hex(source)
    assert source_sha == "b9e35a6c7b3d7116ce6a8a1782f60d09e47c2f69ca18d0f85c01e7ba6d4890c5"
    seed = contract.derive_case_seed(
        42,
        7,
        "s3.reliability.generator.v2.0.0",
        "valid",
    )
    assert contract.make_case_id(
        "campaign-alpha",
        7,
        seed,
        "s3.reliability.generator.v2.0.0",
        "valid",
        source_sha,
    ) == "dad28f906471f6a2a62ae331ed899b4ecc81ad47e73b4c03fe6f47632e4f3a46"


def test_r0_canonical_json_contract() -> None:
    value = {"z": 1, "a": "é", "nested": {"b": False, "a": None}}
    assert contract.canonical_json_payload(value) == (
        '{"a":"é","nested":{"a":null,"b":false},"z":1}'.encode("utf-8")
    )
    assert contract.canonical_json_document(value).endswith(b"\n")
    assert contract.canonical_json_document(value)[:-1] == contract.canonical_json_payload(value)


def test_r0_exact_source_transport_preserves_crlf() -> None:
    source = b"fn main() -> trit:\r\n    return 0\r\n"
    encoded, digest, size = contract.encode_source(source)
    assert contract.decode_and_verify_source(encoded, digest, size) == source

    lf_source = source.replace(b"\r\n", b"\n")
    assert contract.sha256_hex(lf_source) != digest


def test_r0_failure_signature_rules() -> None:
    contract.validate_failure_signature("PASS", None)
    contract.validate_failure_signature("EXPECTED_REJECTION", None)
    contract.validate_failure_signature(
        "TIMEOUT",
        "timeout:RUN_HOSTED:hosted:O1:5000",
    )

    with pytest.raises(ValueError):
        contract.validate_failure_signature("PASS", "not-allowed")

    with pytest.raises(ValueError):
        contract.validate_failure_signature("MISCOMPILE", None)


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("input.s3", True),
        ("artifacts/stdout.bin", True),
        ("a/b/c.json", True),
        ("../input.s3", False),
        ("a/../input.s3", False),
        ("/tmp/input.s3", False),
        ("C:/tmp/input.s3", False),
        ("C:\\tmp\\input.s3", False),
        ("a//b", False),
        (".", False),
    ],
)
def test_r0_replay_paths_are_relative_and_normalized(path: str, expected: bool) -> None:
    assert contract.is_relative_bundle_path(path) is expected


def test_r0_schemas_exclude_canonical_nondeterministic_fields() -> None:
    forbidden = {
        "pid",
        "timestamp",
        "hostname",
        "absolute_path",
        "duration_ms",
        "wall_clock",
    }
    for name in (
        "case-result.schema.json",
        "report.schema.json",
        "replay.schema.json",
        "worker-request.schema.json",
        "worker-response.schema.json",
    ):
        schema = _load(name)
        assert forbidden.isdisjoint(set(_walk_keys(schema))), name


def test_r0_worker_timeout_is_parent_adjudicated() -> None:
    response = _load("worker-response.schema.json")
    assert "TIMEOUT" not in response["properties"]["status"]["enum"]
    assert response["properties"]["status"]["enum"] == [
        "COMPLETED",
        "REJECTED",
        "WORKER_ERROR",
    ]


def test_r0_request_has_no_arbitrary_command_surface() -> None:
    request = _load("worker-request.schema.json")
    assert "command" not in request["properties"]
    assert request["properties"]["operation"]["enum"] == [
        "CHECK",
        "RUN_HOSTED",
        "RUN_NATIVE",
    ]
