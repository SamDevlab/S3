"""M2.58 exact-input differential harness contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.differential import DifferentialCaseError, DifferentialHarness


def test_differential_harness_records_exact_input_provenance_and_match() -> None:
    harness = DifferentialHarness()
    result = harness.run(
        "add-one",
        {"value": 4, "order": ["a", "b"]},
        lambda value: {"result": value["value"] + 1},
        lambda value: {"result": value["value"] + 1},
        provenance={"candidate": "hosted-s3", "source": "fixture-1"},
    )
    assert result.match is True
    assert result.input_sha256
    assert result.input_json == '{"order":["a","b"],"value":4}\n'
    assert '"candidate":"hosted-s3"' in result.provenance_json
    assert result.to_dict()["match"] is True


def test_differential_harness_isolates_mutating_reference_input() -> None:
    harness = DifferentialHarness()

    def reference(value: object) -> object:
        value["items"].append("reference")  # type: ignore[index]
        return value

    result = harness.run(
        "isolated-input",
        {"items": []},
        reference,
        lambda value: value,
        provenance={"source": "mutation-fixture"},
    )
    assert result.match is False
    assert result.reference_output != result.candidate_output


def test_differential_harness_compares_structured_errors() -> None:
    harness = DifferentialHarness()

    def fail(_value: object) -> object:
        raise ValueError("bad input")

    result = harness.run(
        "error-parity",
        {"value": 1},
        fail,
        fail,
        provenance={"source": "error-fixture"},
    )
    assert result.match is True
    assert result.reference_output is None
    assert result.candidate_output is None
    assert result.reference_error == result.candidate_error


def test_differential_harness_fails_closed_on_missing_provenance_and_output() -> None:
    harness = DifferentialHarness(max_bytes=256)
    with pytest.raises(DifferentialCaseError):
        harness.run("missing", {}, lambda value: value, lambda value: value, provenance=None)  # type: ignore[arg-type]
    with pytest.raises(DifferentialCaseError, match="output"):
        harness.run(
            "unsupported-output",
            {},
            lambda _value: {"ok": True},
            lambda _value: {"bad"},
            provenance={"source": "bad-output"},
        )
