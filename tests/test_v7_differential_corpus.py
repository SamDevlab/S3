from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

import tools.v7_differential_corpus as corpus
from bootstrap.s3.compiler_provider import CompilerKind
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.native_compiler import NativeS3CTransportError
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.ir_serialization import serialize_ir


def test_manifest_is_explicit_and_limited_to_case_sample_evidence() -> None:
    corpus.validate_corpus()

    assert len(corpus.ALL_CORPUS_CASES) >= 11
    assert len({case.case_id for case in corpus.ALL_CORPUS_CASES}) == len(
        corpus.ALL_CORPUS_CASES
    )
    assert len({case.family for case in corpus.ALL_CORPUS_CASES}) >= 9
    assert all(case.sources for case in corpus.ALL_CORPUS_CASES)
    assert all(case.compare_hosted_execution for case in corpus.ALL_CORPUS_CASES)
    assert {
        case.case_id for case in corpus.ALL_CORPUS_CASES
    }.issuperset(
        {
            "maturity-ordering-vector-search",
            "maturity-hex-runtime-bytes",
            "maturity-csv-records-and-validation",
            "maturity-bounded-stack-vm",
            "maturity-pebble-compiler",
        }
    )


def test_each_manifest_case_is_valid_for_reference_and_hosted_oracle() -> None:
    for case in corpus.ALL_CORPUS_CASES:
        compilation = compile_sources(
            case.source_map(), entry_module=case.entry_module
        )
        assert compilation.ir is not None, case.case_id
        assert compilation.assembly is not None, case.case_id
        result = Emulator().execute(
            compilation.assembly, entry=case.entry_function
        )
        assert result == case.expected_return, case.case_id
        assert serialize_ir(compilation.ir)


def _install_fake_candidate(
    monkeypatch: pytest.MonkeyPatch,
    *,
    candidate_source: str | None = None,
    candidate_error: Exception | None = None,
) -> None:
    original_source = corpus.compile_source_set_with_provider

    def compile_provider(
        sources,
        optimization,
        *,
        compiler,
        executable,
        entry_module,
    ):
        if compiler is CompilerKind.PYTHON:
            return original_source(
                sources,
                optimization,
                compiler=compiler,
                executable=executable,
                entry_module=entry_module,
            )
        if candidate_error is not None:
            raise candidate_error
        candidate_sources = sources
        if candidate_source is not None:
            candidate_sources = {"main.s3": candidate_source}
        return compile_sources(candidate_sources, optimization, entry_module=entry_module)

    monkeypatch.setattr(corpus, "compile_source_set_with_provider", compile_provider)


def test_runner_compares_provider_ir_and_hosted_execution(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = corpus.CORPUS[0]
    _install_fake_candidate(monkeypatch)

    report = corpus.run_case(case, executable=tmp_path / "unused-candidate")

    assert report["status"] == "PASS"
    assert report["classification"] == "MATCH"
    assert report["canonical_ir"]["status"] == "MATCH"
    assert report["canonical_ir"]["python_sha256"] == report["canonical_ir"]["s3c_ng_sha256"]
    assert report["hosted_execution"]["status"] == "MATCH"
    assert report["hosted_execution"]["python_matches_expected"] is True
    assert report["native_execution"]["status"] == "NOT_COMPARED"


def test_runner_uses_stable_classification_for_ir_and_runtime_divergence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = corpus.CORPUS[0]
    _install_fake_candidate(
        monkeypatch,
        candidate_source="fn main() -> tryte:\n    return 12\n",
    )

    report = corpus.run_case(case, executable=tmp_path / "unused-candidate")

    assert report["status"] == "FAIL"
    assert report["classification"] == "IR_AND_HOSTED_EXECUTION_MISMATCH"
    assert report["canonical_ir"]["status"] == "MISMATCH"
    assert report["hosted_execution"]["status"] == "MISMATCH"


def test_runner_classifies_candidate_compile_failure_without_exception_text(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    case = corpus.CORPUS[0]
    _install_fake_candidate(
        monkeypatch,
        candidate_error=NativeS3CTransportError("temporary path differs"),
    )

    report = corpus.run_case(case, executable=tmp_path / "unused-candidate")

    assert report["status"] == "FAIL"
    assert report["classification"] == "COMPILE_OUTCOME_MISMATCH"
    assert report["compilation"]["s3c_ng"]["error"] == {
        "kind": "DIAGNOSTIC",
        "category": "toolchain",
        "code": "S3E_TOOLCHAIN_FAILED",
        "phase": "toolchain",
    }


def test_runner_rejects_unknown_case_and_never_claims_family_parity(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _install_fake_candidate(monkeypatch)
    report = corpus.run_corpus(
        executable=tmp_path / "unused-candidate",
        case_ids=("not-in-corpus",),
    )

    assert report["status"] == "FAIL"
    assert report["classification"] == "UNKNOWN_SELECTION"
    assert report["unknown_case_ids"] == ["not-in-corpus"]
    assert report["parity_claim"] == "NONE_CASE_SAMPLES_ONLY"


def test_runner_rejects_empty_selection(tmp_path: Path) -> None:
    report = corpus.run_corpus(executable=tmp_path / "unused-candidate", case_ids=())

    assert report["status"] == "FAIL"
    assert report["classification"] == "EMPTY_SELECTION"
    assert report["summary"] == {"selected": 0, "passed": 0, "failed": 1}
