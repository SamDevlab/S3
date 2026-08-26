"""Prepare a candidate that turns parameter return operands into semantic value IDs.

The canonical Stage1 currently preserves parameter owner, name, ordinal, and type,
but ``ir_return_operand`` stores the function-local ABI ordinal for a parameter
return. That is useful for the emitter but it is not a stable global def/use
identity.

This candidate uses the parameter metadata slot itself as the semantic value ID:
``parameter_value_id == parameter_slot`` and therefore reserves the contiguous
namespace ``[0, parameter_count)`` without allocating another array. The general
emitter resolves that ID back through ``ir_parameter_ordinal`` only at lowering
time. Canonical source is never modified by this tool.
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
EXPECTED_SOURCE_SHA256 = "ec6bef92782fe253f4b1c1390d90f95017670a3cbb65497eff9dba12a2e7623c"


def _sha256_text(source: str) -> str:
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def _replace_exact(source: str, old: str, new: str, *, count: int, label: str) -> str:
    observed = source.count(old)
    if observed != count:
        raise ValueError(f"{label}: expected {count} anchor(s), found {observed}")
    return source.replace(old, new)


def transform(source: str) -> str:
    """Return a semantic-parameter-value candidate locked to the current source."""

    source_sha = _sha256_text(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            "source SHA does not match the promoted parameter checkpoint; "
            f"expected {EXPECTED_SOURCE_SHA256}, got {source_sha}"
        )

    candidate = _replace_exact(
        source,
        "ir_return_operand[current_function] = ir_parameter_ordinal[parameter_scan]",
        "ir_return_operand[current_function] = parameter_scan",
        count=1,
        label="parameter return semantic value capture",
    )

    candidate = _replace_exact(
        candidate,
        "match ir_return_operand[general_parameter_scan] < ir_function_param_count[general_parameter_scan]:",
        "match ir_return_operand[general_parameter_scan] < parameter_count:",
        count=2,
        label="parameter return value-id bounds",
    )

    candidate = _replace_exact(
        candidate,
        "match valid_type_name(ir_parameter_type[ir_function_param_start[general_parameter_scan]]):",
        "match ir_parameter_owner[ir_return_operand[general_parameter_scan]] == general_parameter_scan:",
        count=2,
        label="parameter return owner verifier",
    )

    candidate = _replace_exact(
        candidate,
        "emit_general_parameter_function(function_names[general_emit_index], ir_return_operand[general_emit_index])",
        "emit_general_parameter_function(function_names[general_emit_index], ir_parameter_ordinal[ir_return_operand[general_emit_index]])",
        count=2,
        label="semantic value-id to ABI ordinal lowering",
    )

    required = (
        "ir_return_operand[current_function] = parameter_scan",
        "match ir_return_operand[general_parameter_scan] < parameter_count:",
        "match ir_parameter_owner[ir_return_operand[general_parameter_scan]] == general_parameter_scan:",
        "ir_parameter_ordinal[ir_return_operand[general_emit_index]]",
        "while general_parameter_type_scan < parameter_count:",
        "match valid_type_name(ir_parameter_type[general_parameter_type_scan]):",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"candidate missing required marker: {marker}")

    if "mut ir_parameter_value_id:" in candidate:
        raise ValueError("candidate must not allocate a redundant parameter value-id array")

    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=SOURCE)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args(argv)

    source_path = args.source.resolve()
    baseline = source_path.read_text(encoding="utf-8")
    candidate = transform(baseline)
    destination = (
        args.output.resolve()
        if args.output is not None
        else source_path.with_suffix(".parameter-semantic-value-candidate.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={_sha256_text(baseline)}")
    print(f"SOURCE_AFTER_SHA256={_sha256_text(candidate)}")
    print("PARAMETER_VALUE_ID=PARAMETER_SLOT")
    print("PARAMETER_VALUE_NAMESPACE=[0,parameter_count)")
    print("EXTRA_VALUE_ID_STORAGE=0")
    print("CANONICAL_SOURCE_MUTATED=NO")
    print("STATUS=NATIVE_QUALIFICATION_REQUIRED")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
