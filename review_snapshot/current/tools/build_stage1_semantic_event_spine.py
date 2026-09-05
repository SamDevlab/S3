"""Build the bounded native semantic-event V replay observer."""

from __future__ import annotations

import argparse
from pathlib import Path

from tools.build_stage1_compiler import build_stage1


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "stage1_semantic_event_spine.s3"
DEFAULT_HOST_IO = ROOT / "selfhost" / "compiler" / "stage1_host_io.c"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--assembly", type=Path)
    args = parser.parse_args(argv)
    built = build_stage1(
        args.output,
        source=args.source,
        host_io=args.host_io,
        assembly_output=args.assembly,
    )
    print(built)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
