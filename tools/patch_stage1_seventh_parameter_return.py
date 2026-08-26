"""Prepare a bounded Stage1 candidate for the seventh SysV integer parameter.

This transform is intentionally candidate-only. The current canonical Stage1
can emit direct returns from integer parameter ordinals 0 through 5. Under the
SysV x86-64 ABI, ordinal 6 is the first stack-passed integer argument and is
available at [rsp + 8] on entry to the current leaf emitter because the return
address occupies [rsp].

The transform changes only the general-emitter representability boundary and
the ordinal-6 lowering. It does not claim general call lowering, locals,
semantic def/use, complete terminators, Stage2, Stage3, or full self-hosting.
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
    """Return an ordinal-6 candidate without mutating the canonical source."""

    source_sha = _sha256_text(source)
    if source_sha != EXPECTED_SOURCE_SHA256:
        raise ValueError(
            "source SHA does not match the parameter-ordinal checkpoint; "
            f"expected {EXPECTED_SOURCE_SHA256}, got {source_sha}"
        )

    gate_old = "match ir_function_param_count[general_parameter_scan] < 7:"
    gate_new = "match ir_function_param_count[general_parameter_scan] < 8:"
    candidate = _replace_exact(
        source,
        gate_old,
        gate_new,
        count=2,
        label="seven-parameter representability gate",
    )

    emitter_old = (
        "                                    match ordinal == 4:\n"
        "                                        -1:\n"
        "                                            discard write_byte(114)\n"
        "                                            discard write_byte(56)\n"
        "                                        0:\n"
        "                                            discard write_byte(114)\n"
        "                                            discard write_byte(57)\n"
        "                                        1:\n"
        "                                            discard write_byte(114)\n"
        "                                            discard write_byte(57)\n"
    )
    emitter_new = (
        "                                    match ordinal == 4:\n"
        "                                        -1:\n"
        "                                            discard write_byte(114)\n"
        "                                            discard write_byte(56)\n"
        "                                        0:\n"
        "                                            match ordinal == 5:\n"
        "                                                -1:\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(57)\n"
        "                                                0:\n"
        "                                                    discard write_byte(113)\n"
        "                                                    discard write_byte(119)\n"
        "                                                    discard write_byte(111)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(100)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(112)\n"
        "                                                    discard write_byte(116)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(91)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(115)\n"
        "                                                    discard write_byte(112)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(43)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(56)\n"
        "                                                    discard write_byte(93)\n"
        "                                                1:\n"
        "                                                    discard write_byte(113)\n"
        "                                                    discard write_byte(119)\n"
        "                                                    discard write_byte(111)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(100)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(112)\n"
        "                                                    discard write_byte(116)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(91)\n"
        "                                                    discard write_byte(114)\n"
        "                                                    discard write_byte(115)\n"
        "                                                    discard write_byte(112)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(43)\n"
        "                                                    discard write_byte(32)\n"
        "                                                    discard write_byte(56)\n"
        "                                                    discard write_byte(93)\n"
        "                                        1:\n"
        "                                            discard write_byte(114)\n"
        "                                            discard write_byte(56)\n"
    )
    candidate = _replace_exact(
        candidate,
        emitter_old,
        emitter_new,
        count=1,
        label="ordinal-5/6 emitter tail",
    )

    required = (
        "match ordinal == 5:",
        "match ir_function_param_count[general_parameter_scan] < 8:",
        "discard write_byte(113)",
        "discard write_byte(91)",
        "discard write_byte(93)",
    )
    for marker in required:
        if marker not in candidate:
            raise ValueError(f"candidate missing required marker: {marker}")

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
        else source_path.with_suffix(".seventh-parameter-candidate.s3")
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(candidate, encoding="utf-8", newline="\n")

    print(f"SOURCE_BEFORE_SHA256={_sha256_text(baseline)}")
    print(f"SOURCE_AFTER_SHA256={_sha256_text(candidate)}")
    print("SYSV_REGISTER_ORDINALS=0..5")
    print("SYSV_STACK_ORDINAL_6=[rsp+8]")
    print("MAX_EMITTABLE_PARAMETER_COUNT=7")
    print("CANONICAL_SOURCE_MUTATED=NO")
    print("STATUS=NATIVE_QUALIFICATION_REQUIRED")
    print(f"OUTPUT={destination}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
