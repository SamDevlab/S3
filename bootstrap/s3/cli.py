"""Command-line interface for inspecting and running the S3 pipeline."""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from . import ast
from .assembly import AssemblyError
from .backends.x86_64 import (
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from .codegen import CodegenError
from .diagnostics import S3Error
from .emulator import DEFAULT_MAX_FRAMES, Emulator
from .ir_serialization import deserialize_ir, serialize_ir
from .optimizer import OptimizationLevel
from .pipeline import compile_source


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="s3",
        description="S3 balanced-ternary bootstrap toolchain",
    )
    parser.add_argument(
        "command",
        choices=(
            "tokens",
            "ast",
            "ir",
            "ir-json",
            "verify-ir",
            "asm",
            "run",
            "native-asm",
            "build",
            "run-native",
        ),
        help="pipeline artifact to print or action to perform",
    )
    parser.add_argument("source", type=Path, help="path to an S3 source file")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output path for ir-json/native-asm/build",
    )
    parser.add_argument(
        "--keep-assembly",
        type=Path,
        metavar="PATH",
        help="preserve generated .s while building a native executable",
    )
    parser.add_argument(
        "--max-frames",
        type=int,
        default=DEFAULT_MAX_FRAMES,
        metavar="N",
        help=f"maximum S3 call depth (default: {DEFAULT_MAX_FRAMES})",
    )
    parser.add_argument(
        "-O",
        dest="optimization",
        choices=("0", "1"),
        default="0",
        help="IR optimization level (default: 0)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.max_frames < 1:
            raise NativeBackendError("--max-frames must be at least 1")
        source = args.source.read_text(encoding="utf-8")
        if args.command == "verify-ir":
            module = deserialize_ir(source)
            print(f"IR verified: {len(module.functions)} function(s)")
            return 0
        optimization = OptimizationLevel.parse(args.optimization)
        compilation = compile_source(source, optimization)
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
        elif args.command == "ir-json":
            artifact = serialize_ir(compilation.ir)
            if args.output is None:
                print(artifact, end="")
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(
                    artifact,
                    encoding="utf-8",
                    newline="\n",
                )
        elif args.command == "asm":
            print(compilation.assembly_text, end="")
        elif args.command == "run":
            result = Emulator(max_frames=args.max_frames).execute(
                compilation.assembly
            )
            print(f"program returned: {result}")
        elif args.command == "native-asm":
            native = generate_native_assembly(
                compilation.assembly,
                max_frames=args.max_frames,
            )
            if args.output is None:
                print(native, end="")
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(native, encoding="utf-8", newline="\n")
        elif args.command == "build":
            native = generate_native_assembly(
                compilation.assembly,
                max_frames=args.max_frames,
            )
            output = (
                args.output
                if args.output is not None
                else Path("build") / args.source.stem
            )
            NativeToolchain.detect().build(
                native,
                output,
                keep_assembly=args.keep_assembly,
            )
            print(output)
        elif args.command == "run-native":
            native = generate_native_assembly(
                compilation.assembly,
                max_frames=args.max_frames,
            )
            toolchain = NativeToolchain.detect()
            if args.output is not None:
                executable = toolchain.build(
                    native,
                    args.output,
                    keep_assembly=args.keep_assembly,
                )
                completed = toolchain.run(executable)
            else:
                with tempfile.TemporaryDirectory(prefix="s3-native-run-") as temporary:
                    executable = toolchain.build(
                        native,
                        Path(temporary) / "program",
                        keep_assembly=args.keep_assembly,
                    )
                    completed = toolchain.run(executable)
            if completed.stdout:
                print(completed.stdout, end="")
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode
        return 0
    except (
        OSError,
        UnicodeError,
        S3Error,
        AssemblyError,
        CodegenError,
        NativeBackendError,
    ) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
