"""Authoritative static-link entrypoint for final Stage1 self-emission.

The base qualifier owns the self-emit semantics and evidence format. This thin
adapter replaces only its link function for the duration of the run so every
Stage2 candidate and smoke program uses the same deterministic freestanding
static recipe required by the later Landlock gate.

This adapter is also the final dependency boundary between semantic IR and
self-emission: only a semantic-IR report already bound to the exact native call
high-water evidence may reach final self-emit.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable

import tools.qualify_stage1_final_self_emit as base
from tools.selfhost_static_link import assemble_link_static


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CALL_BOUND_SEMANTIC_IR = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "stage1-final-semantic-ir-verifier-call-bound.json"
)
CALL_BOUND_AUTHORITY = "STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND"


class FinalSelfEmitStaticBoundaryError(base.FinalSelfEmitError):
    pass


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_call_bound_semantic_ir(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    try:
        value = json.loads(resolved.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FinalSelfEmitStaticBoundaryError(
            f"call-bound semantic IR report is missing: {resolved}"
        ) from error
    except json.JSONDecodeError as error:
        raise FinalSelfEmitStaticBoundaryError(
            f"call-bound semantic IR report is invalid JSON: {resolved}"
        ) from error
    if not isinstance(value, dict):
        raise FinalSelfEmitStaticBoundaryError(
            "call-bound semantic IR report must be a JSON object"
        )
    return value


def validate_call_bound_semantic_ir(document: dict[str, Any]) -> None:
    if document.get("schema") != "s3.selfhost.stage1-final-semantic-ir-verifier.v1":
        raise FinalSelfEmitStaticBoundaryError(
            "call-bound semantic IR report schema mismatch"
        )
    if document.get("authority") != CALL_BOUND_AUTHORITY:
        raise FinalSelfEmitStaticBoundaryError(
            "final self-emit requires STAGE1_FINAL_SEMANTIC_IR_NATIVE_CALL_BOUND authority"
        )

    qualification = document.get("qualification")
    if not isinstance(qualification, dict):
        raise FinalSelfEmitStaticBoundaryError(
            "call-bound semantic IR report lacks qualification"
        )
    expected = {
        "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
        "verifier_v2": "PASS",
        "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
        "native_call_capacity_boundary": "PASS",
    }
    for key, value in expected.items():
        if qualification.get(key) != value:
            raise FinalSelfEmitStaticBoundaryError(
                f"call-bound semantic IR prerequisite {key} must be {value!r}"
            )

    dependency = document.get("native_call_capacity_dependency")
    if not isinstance(dependency, dict):
        raise FinalSelfEmitStaticBoundaryError(
            "call-bound semantic IR report lacks native call dependency"
        )
    required_dependency = {
        "status": "PASS_NATIVE_CURRENT_SOURCE_CALL_RECONCILIATION",
        "same_canonical_source": True,
        "same_stage1_artifact": True,
        "semantic_calls_equal_native_high_water": True,
        "semantic_call_arguments_equal_native_high_water": True,
    }
    for key, value in required_dependency.items():
        if dependency.get(key) != value:
            raise FinalSelfEmitStaticBoundaryError(
                f"native call dependency {key} must be {value!r}"
            )


def _decorate_result(
    result: dict[str, Any],
    *,
    semantic_path: Path,
    semantic_document: dict[str, Any],
    report_path: Path,
) -> dict[str, Any]:
    result["link_recipe"] = {
        "mode": "STATIC_FREESTANDING_FINAL_AUTHORITY",
        "flags": [
            "-static",
            "-nostdlib",
            "-no-pie",
            "-s",
            "-Wl,--build-id=none",
        ],
        "authoritative_runner": "tools/qualify_stage1_final_self_emit_static.py",
    }
    dependency = semantic_document["native_call_capacity_dependency"]
    result["semantic_ir_call_boundary"] = {
        "authority": CALL_BOUND_AUTHORITY,
        "path": str(semantic_path.resolve()),
        "sha256": _sha256(semantic_path.resolve()),
        "native_call_reconciliation_sha256": dependency.get("report_sha256"),
        "same_canonical_source": True,
        "same_stage1_artifact": True,
        "semantic_calls_equal_native_high_water": True,
        "semantic_call_arguments_equal_native_high_water": True,
        "status": "PASS",
    }
    qualification = result.get("qualification")
    if not isinstance(qualification, dict):
        raise FinalSelfEmitStaticBoundaryError(
            "base self-emit result lacks qualification"
        )
    result["qualification"] = dict(qualification)
    result["qualification"]["semantic_ir_native_call_boundary"] = "PASS"

    report_path.resolve().write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def _qualify_static(
    runner: Callable[..., dict[str, Any]],
    **kwargs: Any,
) -> dict[str, Any]:
    kwargs = dict(kwargs)
    semantic_path = Path(
        kwargs.get("semantic_ir_report_path", DEFAULT_CALL_BOUND_SEMANTIC_IR)
    ).resolve()
    kwargs["semantic_ir_report_path"] = semantic_path
    semantic_document = _load_call_bound_semantic_ir(semantic_path)
    validate_call_bound_semantic_ir(semantic_document)

    original_link = base._assemble_link
    base._assemble_link = assemble_link_static
    try:
        result = runner(**kwargs)
    finally:
        base._assemble_link = original_link

    return _decorate_result(
        result,
        semantic_path=semantic_path,
        semantic_document=semantic_document,
        report_path=Path(kwargs["report"]),
    )


def qualify(**kwargs: Any) -> dict[str, Any]:
    return _qualify_static(base.qualify, **kwargs)


def main(argv: list[str] | None = None) -> int:
    original_qualify = base.qualify
    original_default_semantic_ir = base.DEFAULT_SEMANTIC_IR

    def patched_qualify(**kwargs: Any) -> dict[str, Any]:
        return _qualify_static(original_qualify, **kwargs)

    base.qualify = patched_qualify
    base.DEFAULT_SEMANTIC_IR = DEFAULT_CALL_BOUND_SEMANTIC_IR
    try:
        return base.main(argv)
    finally:
        base.qualify = original_qualify
        base.DEFAULT_SEMANTIC_IR = original_default_semantic_ir


if __name__ == "__main__":
    raise SystemExit(main())
