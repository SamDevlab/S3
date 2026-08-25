"""Run non-native Stage1 IR-v2 preflights before expensive Linux qualification.

This command verifies physical storage assumptions and quantifies fixed-array
initializer payloads. A PASS is static only; it never substitutes for Stage1
native execution and never mutates the canonical compiler.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.audit_stage1_array_initializers import (
    DEFAULT_REPORT as DEFAULT_ARRAY_REPORT,
    audit as audit_arrays,
)
from tools.audit_stage1_ir_v2_storage_reuse import (
    DEFAULT_REPORT as DEFAULT_STORAGE_REPORT,
    audit as audit_storage,
)


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "codegen-ir-v2-static-preflight.json"
)


def _write(path: Path, value: dict[str, object]) -> None:
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(
    *,
    source_path: Path = SOURCE,
    storage_report_path: Path = DEFAULT_STORAGE_REPORT,
    array_report_path: Path = DEFAULT_ARRAY_REPORT,
    report_path: Path = DEFAULT_REPORT,
) -> dict[str, object]:
    source = source_path.resolve().read_text(encoding="utf-8")
    storage = audit_storage(source)
    arrays = audit_arrays(source)
    _write(storage_report_path, storage)
    _write(array_report_path, arrays)

    storage_pass = storage.get("status") == "STATIC_STORAGE_AUDIT_PASS"
    array_pass = arrays.get("status") == "STATIC_ARRAY_INITIALIZER_AUDIT_PASS"
    result = {
        "schema": "s3.selfhost.codegen-ir-v2-static-preflight.v1",
        "status": "PASS_STATIC_ONLY" if storage_pass and array_pass else "FAIL_STATIC",
        "native_evidence": False,
        "canonical_source_mutated": False,
        "storage_reuse_audit": {
            "status": storage.get("status"),
            "report": str(storage_report_path.resolve()),
        },
        "array_initializer_audit": {
            "status": arrays.get("status"),
            "report": str(array_report_path.resolve()),
            "zero_initializer_items": arrays.get("summary", {}).get("zero_initializer_items"),
            "all_zero_arrays": arrays.get("summary", {}).get("all_zero_arrays"),
        },
        "native_chain_allowed": bool(storage_pass and array_pass),
        "qualification_rule": "PASS_STATIC_ONLY authorizes attempting native candidate gates, not source promotion or self-hosting claims.",
        "stage2": "NOT_STARTED",
        "stage3": "NOT_STARTED",
        "full_self_hosting": False,
    }
    _write(report_path, result)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--storage-report", type=Path, default=DEFAULT_STORAGE_REPORT)
    parser.add_argument("--array-report", type=Path, default=DEFAULT_ARRAY_REPORT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    result = run(
        source_path=args.source,
        storage_report_path=args.storage_report,
        array_report_path=args.array_report,
        report_path=args.report,
    )
    print(f"REPORT={args.report.resolve()}")
    print(f"STATIC_PREFLIGHT={result['status']}")
    print(f"STORAGE_REUSE={result['storage_reuse_audit']['status']}")
    print(f"ARRAY_INITIALIZERS={result['array_initializer_audit']['status']}")
    print(f"ZERO_INITIALIZER_ITEMS={result['array_initializer_audit']['zero_initializer_items']}")
    print(f"NATIVE_CHAIN_ALLOWED={result['native_chain_allowed']}")
    print("NATIVE_EVIDENCE=False")
    return 0 if result["native_chain_allowed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
