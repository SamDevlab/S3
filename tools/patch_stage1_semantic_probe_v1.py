"""Build a native-observable Stage1 S1 semantic probe candidate.

This composes the non-mutating semantic S1 port, enables its S3IR2 stream, emits
the header before parsing, and exits before the normal assembly emitter. The
candidate deliberately writes completeness mask 0 because constants/results and
S2-S5 are not closed yet.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.patch_stage1_semantic_port_v1 import (
    DEFAULT_SOURCE,
    DEFAULT_STREAM,
    apply_patch as apply_s1_patch,
)

PROBE_MARKER = "# STAGE1_SEMANTIC_NATIVE_PROBE_V1"


def _replace_once(source: str, old: str, new: str, label: str) -> str:
    count = source.count(old)
    if count != 1:
        raise ValueError(f"{label}: expected one anchor, found {count}")
    return source.replace(old, new, 1)


def build_probe(source: str, stream_source: str) -> str:
    candidate = apply_s1_patch(source, stream_source)
    if PROBE_MARKER in candidate:
        return candidate

    candidate = _replace_once(
        candidate,
        "    mut semantic_stream_enabled: trit = 0\n",
        "    mut semantic_stream_enabled: trit = -1\n",
        "enable semantic stream",
    )

    token_anchor = "    mut token_kind: tryte[16] = ["
    token_index = candidate.find(token_anchor)
    if token_index < 0:
        raise ValueError("token-array anchor not found")
    candidate = (
        candidate[:token_index]
        + f"    {PROBE_MARKER}\n"
        + "    discard semantic_emit_header()\n"
        + candidate[token_index:]
    )

    emitter_anchor = (
        "    match pipeline_ok == -1:\n"
        "        -1:\n"
        "            match general_emitter_possible == -1:\n"
    )
    probe_exit = (
        "    match semantic_stream_enabled == -1:\n"
        "        -1:\n"
        "            # S1 is still partial: parameter/local definitions only.\n"
        "            discard semantic_emit_complete(0)\n"
        "            discard s3_stage1_exit(0)\n"
        "        0:\n"
        "            discard 0\n"
        "        1:\n"
        "            discard 0\n"
        + emitter_anchor
    )
    candidate = _replace_once(
        candidate,
        emitter_anchor,
        probe_exit,
        "pre-emitter semantic probe exit",
    )
    return candidate


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--stream-source", type=Path, default=DEFAULT_STREAM)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    candidate = build_probe(
        args.source.read_text(encoding="utf-8"),
        args.stream_source.read_text(encoding="utf-8"),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(candidate, encoding="utf-8", newline="\n")
    print(f"OUTPUT={args.output}")
    print("SEMANTIC_PROBE=ENABLED")
    print("COMPLETENESS_MASK=0")
    print("SELF_EMIT_AUTHORIZED=NO")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
