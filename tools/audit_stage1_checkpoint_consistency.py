"""Audit Stage1 checkpoint provenance without rewriting historical evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
REQUIREMENTS = ROOT / "reports" / "selfhost" / "stage1" / "semantic-ir-requirements.json"
FINAL_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "FINAL_STAGE1_REPORT.md"
HANDOFF = ROOT / "reports" / "selfhost" / "stage1" / "FINAL_AUTONOMOUS_HANDOFF.txt"
BLOCKER = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "checkpoint-consistency-audit.json"
)
_SHA_RE = re.compile(r"\b[a-f0-9]{64}\b")


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _document_shas(text: str) -> list[str]:
    return sorted(set(_SHA_RE.findall(text.lower())))


def audit(
    *,
    source_bytes: bytes,
    requirements: dict[str, Any],
    final_report: str,
    handoff: str,
    blocker: str,
) -> dict[str, Any]:
    current_sha = _sha256(source_bytes)
    current_bytes = len(source_bytes)
    requirement_source = requirements.get("source", {})
    requirement_sha = requirement_source.get("sha256")
    requirement_bytes = requirement_source.get("bytes")

    documents = {
        "FINAL_STAGE1_REPORT.md": final_report,
        "FINAL_AUTONOMOUS_HANDOFF.txt": handoff,
        "GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md": blocker,
    }
    document_state: dict[str, Any] = {}
    for name, text in documents.items():
        shas = _document_shas(text)
        document_state[name] = {
            "mentions_current_source_sha": current_sha in shas,
            "source_shas_mentioned": shas,
            "classification": (
                "CONTAINS_CURRENT_CHECKPOINT"
                if current_sha in shas
                else "HISTORICAL_OR_STALE_FOR_CURRENT_SOURCE"
            ),
        }

    guards = {
        "semantic_requirements_matches_current_sha": requirement_sha == current_sha,
        "semantic_requirements_matches_current_bytes": requirement_bytes == current_bytes,
        "general_blocker_contains_current_sha": document_state[
            "GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md"
        ]["mentions_current_source_sha"],
    }
    stale = [
        name
        for name in ("FINAL_STAGE1_REPORT.md", "FINAL_AUTONOMOUS_HANDOFF.txt")
        if not document_state[name]["mentions_current_source_sha"]
    ]
    if all(guards.values()):
        status = (
            "CURRENT_CHECKPOINT_IDENTIFIED_HISTORICAL_HANDOFFS_PRESENT"
            if stale
            else "CURRENT_CHECKPOINT_DOCUMENTS_CONSISTENT"
        )
    else:
        status = "CURRENT_CHECKPOINT_PROVENANCE_RECONCILIATION_REQUIRED"

    return {
        "schema": "s3.selfhost.stage1-checkpoint-consistency-audit.v1",
        "status": status,
        "native_evidence": False,
        "canonical_source_mutated": False,
        "current_source": {
            "sha256": current_sha,
            "bytes": current_bytes,
        },
        "semantic_requirements_source": {
            "sha256": requirement_sha,
            "bytes": requirement_bytes,
            "matches_current": requirement_sha == current_sha
            and requirement_bytes == current_bytes,
        },
        "documents": document_state,
        "historical_or_stale_handoffs": stale,
        "authoritative_read_order": [
            "current canonical source hash/bytes",
            "semantic-ir-requirements.json matching that exact source",
            "latest matching section in GENERAL_EMITTER_CLOSURE_BLOCKER_20260826.md",
            "historical FINAL_STAGE1_REPORT.md / FINAL_AUTONOMOUS_HANDOFF.txt only for preserved campaign evidence",
        ],
        "guards": guards,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--requirements", type=Path, default=REQUIREMENTS)
    parser.add_argument("--final-report", type=Path, default=FINAL_REPORT)
    parser.add_argument("--handoff", type=Path, default=HANDOFF)
    parser.add_argument("--blocker", type=Path, default=BLOCKER)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = audit(
        source_bytes=args.source.resolve().read_bytes(),
        requirements=json.loads(args.requirements.resolve().read_text(encoding="utf-8")),
        final_report=args.final_report.resolve().read_text(encoding="utf-8"),
        handoff=args.handoff.resolve().read_text(encoding="utf-8"),
        blocker=args.blocker.resolve().read_text(encoding="utf-8"),
    )
    destination = args.report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"CURRENT_SOURCE_SHA256={result['current_source']['sha256']}")
    print(f"CURRENT_SOURCE_BYTES={result['current_source']['bytes']}")
    print(
        "HISTORICAL_OR_STALE_HANDOFFS="
        + ",".join(result["historical_or_stale_handoffs"])
    )
    print("NATIVE_EVIDENCE=False")
    return (
        0
        if result["status"]
        != "CURRENT_CHECKPOINT_PROVENANCE_RECONCILIATION_REQUIRED"
        else 2
    )


if __name__ == "__main__":
    raise SystemExit(main())
