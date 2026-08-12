"""CLI for extracting research traces from an S3 Assembly text file.

Usage:
    python research-lab/prototypes/trace_cli.py path/to/file.s3asm

The exact Assembly filename extension is irrelevant; the file must contain text
accepted by `bootstrap.s3.assembly.parse_assembly`.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from bootstrap.s3.assembly import parse_assembly

from s3_adapter import compare_liveness
from value_trace import trace_as_jsonable


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("assembly_file", type=Path)
    parser.add_argument(
        "--function",
        help="Only emit one function by exact name; default emits all functions.",
    )
    args = parser.parse_args()

    program = parse_assembly(args.assembly_file.read_text(encoding="utf-8"))
    functions = tuple(
        function
        for function in program.functions
        if args.function is None or function.name == args.function
    )
    if args.function is not None and not functions:
        raise SystemExit(f"function not found: {args.function}")

    result = []
    for function in functions:
        result.append(
            {
                "function": function.name,
                "liveness_crosscheck": compare_liveness(function),
                "values": trace_as_jsonable(function),
            }
        )

    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
