"""Command-line interface for inspecting and running the S3 pipeline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from . import ast
from .assembly import AssemblyError
from .codegen import CodegenError
from .diagnostics import S3Error
from .emulator import Emulator
from .pipeline import compile_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s3",
        description="S3 balanced-ternary bootstrap toolchain",
    )
    parser.add_argument(
        "command",
        choices=("tokens", "ast", "ir", "asm", "run"),
        help="pipeline artifact to print or action to perform",
    )
    parser.add_argument("source", type=Path, help="path to an S3 source file")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        source = args.source.read_text(encoding="utf-8")
        compilation = compile_source(source)
        if args.command == "tokens":
            payload = [
                token.to_dict()
                for token in compilation.tokens
                if token.text or token.kind.name != "EOF"
            ]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif args.command == "ast":
            print(json.dumps(ast.to_dict(compilation.ast), indent=2))
        elif args.command == "ir":
            print(json.dumps(compilation.ir.to_dict(), indent=2))
        elif args.command == "asm":
            print(compilation.assembly_text, end="")
        elif args.command == "run":
            result = Emulator().execute(compilation.assembly)
            print(f"program returned: {result}")
        return 0
    except (OSError, UnicodeError, S3Error, AssemblyError, CodegenError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

