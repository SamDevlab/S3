"""Deterministic failure grouping and replay minimization for R4.

The machine report and its Markdown rendering are both projections of the same
sorted data.  No host, timestamp, process, or absolute path is part of a
triage identity.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Callable, Iterable, Mapping

from tools.reliability_contract_v2 import (
    DEFAULT_RESOURCE_POLICY,
    NON_FAILURE_OUTCOMES,
    canonical_json_document,
    is_relative_bundle_path,
    sha256_hex,
    validate_failure_signature,
    validate_relative_bundle_path,
)
from tools.reliability_differential_v2 import load_replay
from tools.reliability_minimizer_v2 import (
    Evaluator,
    MinimizationResult,
    minimize_failure,
)

TRIAGE_SCHEMA = "s3.reliability.triage.v1"
MINIMIZATION_SCHEMA = "s3.reliability.minimization.v1"


@dataclass(frozen=True, slots=True)
class FailureGroup:
    outcome: str
    failure_signature: str
    count: int
    first_case_index: int
    case_ids: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "outcome": self.outcome,
            "failure_signature": self.failure_signature,
            "count": self.count,
            "first_case_index": self.first_case_index,
            "case_ids": list(self.case_ids),
        }


@dataclass(frozen=True, slots=True)
class ReplayMinimizationResult:
    case_id: str
    compiler_head: str
    output_dir: Path
    minimization: MinimizationResult

    def to_dict(self) -> dict[str, object]:
        value = self.minimization.to_dict()
        value.update(
            {
                "case_id": self.case_id,
                "compiler_head": self.compiler_head,
            }
        )
        return value


def _result_mapping(result: object) -> Mapping[str, object]:
    if isinstance(result, Mapping):
        return result
    to_dict = getattr(result, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
        if isinstance(value, Mapping):
            return value
    raise TypeError("triage results must be mappings or expose to_dict()")


def group_failures(results: Iterable[object]) -> tuple[FailureGroup, ...]:
    """Group non-success results using the frozen R0 ordering contract."""
    grouped: dict[tuple[str, str], dict[str, object]] = {}
    for result in results:
        value = _result_mapping(result)
        outcome = value.get("outcome")
        signature = value.get("failure_signature")
        case_id = value.get("case_id")
        case_index = value.get("case_index")
        if not isinstance(outcome, str):
            raise ValueError("triage result outcome must be a string")
        if outcome in NON_FAILURE_OUTCOMES:
            validate_failure_signature(outcome, signature)
            continue
        if not isinstance(signature, str):
            raise ValueError("triage result failure_signature must be a string")
        validate_failure_signature(outcome, signature)
        if not isinstance(case_id, str) or not case_id:
            raise ValueError("triage result case_id must be a non-empty string")
        if isinstance(case_index, bool) or not isinstance(case_index, int) or case_index < 0:
            raise ValueError("triage result case_index must be non-negative")
        key = (outcome, signature)
        item = grouped.setdefault(
            key,
            {"count": 0, "first_case_index": case_index, "case_ids": set()},
        )
        item["count"] = int(item["count"]) + 1
        item["first_case_index"] = min(int(item["first_case_index"]), case_index)
        ids = item["case_ids"]
        assert isinstance(ids, set)
        ids.add(case_id)

    groups = [
        FailureGroup(
            outcome=outcome,
            failure_signature=signature,
            count=int(item["count"]),
            first_case_index=int(item["first_case_index"]),
            case_ids=tuple(sorted(item["case_ids"])),
        )
        for (outcome, signature), item in grouped.items()
    ]
    return tuple(
        sorted(groups, key=lambda group: (
            group.outcome,
            group.failure_signature,
            group.first_case_index,
        ))
    )


def _sorted_counts(results: Iterable[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        outcome = _result_mapping(result).get("outcome")
        if not isinstance(outcome, str):
            raise ValueError("triage result outcome must be a string")
        counts[outcome] = counts.get(outcome, 0) + 1
    return {key: counts[key] for key in sorted(counts)}


def build_triage_report(
    campaign_report: Mapping[str, object],
    *,
    minimizations: Iterable[Mapping[str, object]] = (),
) -> dict[str, object]:
    """Build a canonical R4 report from one R3 campaign report."""
    raw_results = campaign_report.get("results")
    if not isinstance(raw_results, list):
        raise ValueError("campaign report results must be a list")
    groups = group_failures(raw_results)
    report: dict[str, object] = {
        "schema": TRIAGE_SCHEMA,
        "campaign_id": campaign_report.get("campaign_id"),
        "compiler_head": campaign_report.get("compiler_head"),
        "case_count": len(raw_results),
        "counts": _sorted_counts(raw_results),
        "failure_groups": [group.to_dict() for group in groups],
        "minimizations": sorted(
            (dict(value) for value in minimizations),
            key=lambda value: (str(value.get("case_id", "")), str(value.get("minimized_source_sha256", ""))),
        ),
    }
    for key in ("campaign_seed", "native_case_count", "confirmation_runs_per_path"):
        if key in campaign_report:
            report[key] = campaign_report[key]
    if report["campaign_id"] is None or report["compiler_head"] is None:
        raise ValueError("campaign report must identify campaign_id and compiler_head")
    return report


def write_triage_report(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(canonical_json_document(dict(report)))


def _markdown_cell(value: object) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_triage_markdown(report: Mapping[str, object]) -> str:
    """Render the already-canonical triage model without adding telemetry."""
    groups = report.get("failure_groups", [])
    if not isinstance(groups, list):
        raise ValueError("triage report failure_groups must be a list")
    lines = [
        "# Reliability Triage",
        "",
        f"- Campaign: `{_markdown_cell(report.get('campaign_id'))}`",
        f"- Compiler head: `{_markdown_cell(report.get('compiler_head'))}`",
        f"- Cases: `{_markdown_cell(report.get('case_count'))}`",
        "",
        "## Failure Groups",
        "",
    ]
    if not groups:
        lines.append("No failure groups.")
    else:
        lines.extend(
            [
                "| Outcome | Failure signature | Count | First case index | Case IDs |",
                "| --- | --- | ---: | ---: | --- |",
            ]
        )
        for group in groups:
            if not isinstance(group, Mapping):
                raise ValueError("failure group must be an object")
            ids = group.get("case_ids", [])
            if not isinstance(ids, list):
                raise ValueError("failure group case_ids must be a list")
            lines.append(
                "| "
                + " | ".join(
                    (
                        _markdown_cell(group.get("outcome")),
                        _markdown_cell(group.get("failure_signature")),
                        _markdown_cell(group.get("count")),
                        _markdown_cell(group.get("first_case_index")),
                        _markdown_cell(", ".join(str(item) for item in ids)),
                    )
                )
                + " |"
            )
    lines.extend(["", "## Outcome Counts", "", "| Outcome | Count |", "| --- | ---: |"])
    counts = report.get("counts", {})
    if not isinstance(counts, Mapping):
        raise ValueError("triage report counts must be an object")
    for outcome in sorted(counts):
        lines.append(f"| {_markdown_cell(outcome)} | {_markdown_cell(counts[outcome])} |")
    return "\n".join(lines) + "\n"


def write_triage_markdown(path: Path, report: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_triage_markdown(report), encoding="utf-8", newline="\n")


def _bundle_file(bundle: Path, relative: object) -> Path:
    if not isinstance(relative, str) or not is_relative_bundle_path(relative):
        raise ValueError("replay artifact path must be a normalized relative POSIX path")
    validate_relative_bundle_path(relative)
    candidate = bundle.joinpath(*PurePosixPath(relative).parts)
    root = bundle.resolve()
    resolved = candidate.resolve()
    if resolved != root and root not in resolved.parents:
        raise ValueError("replay artifact escapes its bundle")
    return candidate


def _read_json(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("replay JSON artifact must contain an object")
    return value


def minimize_replay_bundle(
    bundle: Path,
    evaluator: Evaluator,
    *,
    output_dir: Path | None = None,
    max_evaluations: int = DEFAULT_RESOURCE_POLICY.minimizer_max_evaluations,
) -> ReplayMinimizationResult:
    """Verify one R3 replay bundle, then write a separate minimized bundle."""
    manifest = load_replay(bundle / "replay.json")
    source_path = _bundle_file(bundle, manifest.get("source_path"))
    metadata_path = _bundle_file(bundle, manifest.get("metadata_path"))
    result_path = _bundle_file(bundle, manifest.get("result_path"))
    source = source_path.read_bytes()
    if len(source) > DEFAULT_RESOURCE_POLICY.source_max_bytes:
        raise ValueError("replay source exceeds frozen source_max_bytes")
    source_digest = sha256_hex(source)
    if manifest.get("source_sha256") != source_digest:
        raise ValueError("replay source SHA-256 does not match")
    metadata_bytes = metadata_path.read_bytes()
    result_bytes = result_path.read_bytes()
    if manifest.get("metadata_sha256") != sha256_hex(metadata_bytes):
        raise ValueError("replay metadata SHA-256 does not match")
    if manifest.get("result_sha256") != sha256_hex(result_bytes):
        raise ValueError("replay result SHA-256 does not match")
    metadata = _read_json(metadata_path)
    result = _read_json(result_path)
    case_id = manifest.get("case_id")
    compiler_head = manifest.get("compiler_head")
    outcome = result.get("outcome")
    signature = manifest.get("expected_failure_signature")
    if result.get("case_id") != case_id or metadata.get("case_id") != case_id:
        raise ValueError("replay artifacts disagree on case_id")
    if metadata.get("source_sha256") != source_digest:
        raise ValueError("replay metadata source SHA-256 does not match")
    if "source_bytes" in metadata and metadata.get("source_bytes") != len(source):
        raise ValueError("replay metadata source byte count does not match")
    if not isinstance(case_id, str) or not isinstance(compiler_head, str):
        raise ValueError("replay manifest identity is invalid")
    if not isinstance(outcome, str) or not isinstance(signature, str):
        raise ValueError("replay failure identity is incomplete")
    if "expected_outcome" in manifest and manifest.get("expected_outcome") != outcome:
        raise ValueError("replay artifacts disagree on expected outcome")
    if result.get("failure_signature") != signature:
        raise ValueError("replay artifacts disagree on failure_signature")
    validate_failure_signature(outcome, signature)
    if outcome in NON_FAILURE_OUTCOMES:
        raise ValueError("replay minimization requires a failure outcome")

    result_value = minimize_failure(
        source,
        evaluator,
        expected_outcome=outcome,
        expected_failure_signature=signature,
        max_evaluations=max_evaluations,
    )
    destination = output_dir or bundle.parent / "minimized" / bundle.name
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "input.s3").write_bytes(result_value.minimized_source)
    (destination / "minimization.json").write_bytes(
        canonical_json_document(
            {
                "schema": MINIMIZATION_SCHEMA,
                "case_id": case_id,
                "compiler_head": compiler_head,
                "replay_source_sha256": source_digest,
                **result_value.to_dict(),
            }
        )
    )
    return ReplayMinimizationResult(case_id, compiler_head, destination, result_value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a deterministic S3 R4 triage report")
    parser.add_argument("report", type=Path, help="canonical R3 campaign report")
    parser.add_argument("--json-out", required=True, type=Path)
    parser.add_argument("--markdown-out", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    report_value = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report_value, Mapping):
        raise SystemExit("campaign report must be a JSON object")
    triage = build_triage_report(report_value)
    write_triage_report(args.json_out, triage)
    write_triage_markdown(args.markdown_out, triage)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
