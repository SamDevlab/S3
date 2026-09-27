"""Command-line interface for inspecting and running the S3 pipeline."""

from __future__ import annotations

import argparse
import json
import platform
import sys
import tempfile
from pathlib import Path
from typing import Sequence

from . import ast
from .assembly import AssemblyError
from .backends.registry import create_builtin_backend_registry
from .backends.x86_64 import (
    NativeCodegenPolicy,
    NativeBackendError,
    NativeToolchain,
    generate_native_assembly,
)
from .codegen import CodegenError
from .diagnostics import (
    Diagnostic,
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    DiagnosticSeverity,
    S3Error,
    diagnostic_from_exception,
)
from .emulator import DEFAULT_MAX_FRAMES, DEFAULT_MAX_INSTRUCTIONS, Emulator
from .docs_generator import DocumentationError, render_json, render_markdown
from .ffi import build_shared_library
from .formatter import FormatterError, format_source
from .ir_serialization import deserialize_ir, serialize_ir
from .lexer import SyntaxMode
from .optimizer import OptimizationLevel, instruction_count
from .pipeline import CompilationResult, compile_source
from .project_container import ProjectTooling
from .s3_docker import DockerProvider, DockerSpec
from .targets import BUILTIN_TARGETS
from .test_runner import TestRunnerError, render_test_report, run_test_manifest


class _CLIUsageError(Exception):
    diagnostic_category = DiagnosticCategory.SYNTAX
    diagnostic_code = DiagnosticCode.CLI_USAGE
    diagnostic_phase = DiagnosticPhase.CLI

    def __init__(self, message: str) -> None:
        self.message = message
        self.diagnostic_message = message
        super().__init__(message)


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise _CLIUsageError(message)


_SOURCE_SYNTAX_MODES = {
    "0.5": SyntaxMode.V0_5,
    "0.6": SyntaxMode.V0_6,
}
_NATIVE_POLICY_VALUES = tuple(policy.value for policy in NativeCodegenPolicy)


def _parser() -> argparse.ArgumentParser:
    parser = _ArgumentParser(
        prog="s3",
        description="S3 balanced-ternary bootstrap toolchain",
    )

    # --- Add common options to the main parser (with defaults) ---
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
    parser.add_argument(
        "--diagnostic-format",
        choices=("text", "json"),
        default="text",
        help="diagnostic output format on stderr (default: text)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="re-raise failures with a Python traceback",
    )
    parser.add_argument(
        "--source-syntax",
        choices=("0.5", "0.6"),
        default="0.6",
        help="Source syntax version (default: 0.6)",
    )
    parser.add_argument(
        "--native-policy",
        choices=_NATIVE_POLICY_VALUES,
        default=NativeCodegenPolicy.BASELINE.value,
        help="native code-generation policy (default: baseline)",
    )

    # --- Parent parser for subcommands (without defaults, so they don't overwrite) ---
    parent = argparse.ArgumentParser(add_help=False)
    parent.add_argument("source", type=Path, help="path to an S3 source file")
    parent.add_argument(
        "-o",
        "--output",
        type=Path,
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "--keep-assembly",
        type=Path,
        metavar="PATH",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "--max-frames",
        type=int,
        metavar="N",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "-O",
        dest="optimization",
        choices=("0", "1"),
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "--diagnostic-format",
        choices=("text", "json"),
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "--debug",
        action="store_true",
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )
    parent.add_argument(
        "--source-syntax",
        choices=("0.5", "0.6"),
        default=argparse.SUPPRESS,
        help=argparse.SUPPRESS,
    )

    subparsers = parser.add_subparsers(
        dest="command",
        parser_class=_ArgumentParser,
        help="pipeline artifact to print or action to perform",
    )
    subparsers.required = True

    subparsers.add_parser("doctor")
    subparsers.add_parser("targets")

    container = subparsers.add_parser(
        "container", help="inspect, plan, build, or run an S3 project container"
    )
    container_actions = container.add_subparsers(dest="container_action", required=True)
    for action in ("inspect", "plan", "build", "run"):
        action_parser = container_actions.add_parser(action)
        action_parser.add_argument("root", type=Path, help="project root containing s3.toml")
        action_parser.add_argument("--image", required=True, help="Docker image reference")

    commands = (
        "tokens",
        "ast",
        "check",
        "ir",
        "ir-json",
        "inspect",
        "verify-ir",
        "asm",
        "run",
        "native-asm",
        "build",
        "run-native",
        "ffi-build",
        "format",
        "docs",
    )
    for cmd in commands:
        p = subparsers.add_parser(cmd, parents=[parent])
        if cmd == "inspect":
            p.add_argument(
                "--emit",
                choices=("summary", "ir", "assembly"),
                default="summary",
                help="inspection output to print (default: summary)",
            )
        if cmd == "format":
            p.add_argument("--write", action="store_true", help="write canonical source in place")
        if cmd == "docs":
            p.add_argument("--json", action="store_true", help="emit machine-readable documentation")
        if cmd in ("run", "native-asm", "build", "run-native", "ffi-build"):
            p.add_argument(
                "--max-instructions",
                type=int,
                default=DEFAULT_MAX_INSTRUCTIONS,
                metavar="N",
                help=(
                    f"maximum S3 opcodes (default: {DEFAULT_MAX_INSTRUCTIONS})"
                ),
            )
        if cmd in ("native-asm", "build", "run-native", "ffi-build"):
            p.add_argument(
                "--native-policy",
                choices=_NATIVE_POLICY_VALUES,
                default=argparse.SUPPRESS,
                help="native code-generation policy",
            )
    test_parser = subparsers.add_parser("test")
    test_parser.add_argument("manifest", type=Path, help="path to an s3-test.toml manifest")
    test_parser.add_argument(
        "--mode",
        choices=("hosted", "native", "both"),
        help="execution mode overriding the manifest",
    )
    test_parser.add_argument(
        "--report",
        type=Path,
        help="write the deterministic machine-readable report to this path",
    )
    test_parser.set_defaults(diagnostic_format="text", debug=False)

    return parser


def _requested_diagnostic_format(argv: Sequence[str]) -> str:
    for index, argument in enumerate(argv):
        if argument.startswith("--diagnostic-format="):
            value = argument.partition("=")[2]
            return value if value in {"text", "json"} else "text"
        if argument == "--diagnostic-format" and index + 1 < len(argv):
            value = argv[index + 1]
            return value if value in {"text", "json"} else "text"
    return "text"


def _emit_diagnostic(diagnostic: Diagnostic, output_format: str) -> None:
    if output_format == "json":
        payload = diagnostic.to_json()
        byte_stream = getattr(sys.stderr, "buffer", None)
        if byte_stream is None:
            sys.stderr.write(payload)
        else:
            byte_stream.write(payload.encode("utf-8"))
            byte_stream.flush()
    else:
        raise ValueError("text diagnostics require their original exception")


def _emit_error(
    error: Exception,
    output_format: str,
    *,
    file: str | None = None,
    internal: bool = False,
) -> None:
    if output_format == "json":
        _emit_diagnostic(
            diagnostic_from_exception(error, file=file),
            output_format,
        )
    else:
        prefix = "internal error: " if internal else ""
        print(f"error: {prefix}{error}", file=sys.stderr)


def _print_targets() -> None:
    registry = create_builtin_backend_registry()
    lines = ["Targets:"]
    lines.extend(f"  {target.name}" for target in BUILTIN_TARGETS)
    lines.extend(("", "Hosted execution:"))
    lines.extend(f"  {name}" for name in registry.hosted_execution_names)
    lines.extend(("", "Native assembly:"))
    lines.extend(f"  {name}" for name in registry.native_assembly_targets)
    print("\n".join(lines))


def _print_doctor() -> None:
    registry = create_builtin_backend_registry()
    lines = [
        "S3 doctor",
        "",
        "Python:",
        f"  version: {platform.python_version()}",
        f"  executable: {sys.executable}",
        "",
        "Host:",
        f"  system: {platform.system()}",
        f"  machine: {platform.machine()}",
        "",
        "Targets:",
    ]
    lines.extend(f"  {target.name}" for target in BUILTIN_TARGETS)
    lines.extend(("", "Hosted execution:"))
    lines.extend(f"  {name}" for name in registry.hosted_execution_names)
    lines.extend(("", "Native assembly:"))
    lines.extend(f"  {name}" for name in registry.native_assembly_targets)
    lines.extend(("", "Native toolchain:"))
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        lines.extend(("  available: no", f"  reason: {error}"))
    else:
        lines.extend(
            (
                "  available: yes",
                f"  compiler: {toolchain.compiler}",
                f"  assembler: {toolchain.assembler or 'not found'}",
                f"  linker: {toolchain.linker or 'not found'}",
            )
        )
    print("\n".join(lines))


def _print_inspection(
    source_path: Path,
    compilation: CompilationResult,
    *,
    syntax: str,
    optimization: OptimizationLevel,
) -> None:
    ir, assembly = compilation.require_ordinary_artifacts()
    function_names = tuple(function.name for function in compilation.ast.functions)
    assembly_instructions = sum(
        len(block.instructions)
        for function in assembly.functions
        for block in function.blocks
    )
    lines = [
        "S3 inspect",
        "",
        "Source:",
        f"  path: {source_path}",
        "",
        "Compilation:",
        f"  syntax: {syntax}",
        f"  optimization: {optimization.value}",
        "",
        "Program:",
        f"  functions: {len(function_names)}",
        f"  entry: {'main' if 'main' in function_names else 'not found'}",
        "",
        "IR:",
        f"  instructions: {instruction_count(ir)}",
        "",
        "Assembly:",
        f"  instructions: {assembly_instructions}",
    ]
    print("\n".join(lines))


def _print_inspection_artifact(kind: str, artifact: str) -> None:
    print("\n".join(("S3 inspect", "", "Emit:", f"  kind: {kind}", "")))
    print(artifact, end="" if artifact.endswith("\n") else "\n")


def _print_check(source_path: Path) -> None:
    print("\n".join(("S3 check", f"  path: {source_path}", "  status: ok")))


def main(argv: Sequence[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    parser = _parser()
    requested_format = _requested_diagnostic_format(raw_argv)
    try:
        args = parser.parse_args(raw_argv)
    except _CLIUsageError as error:
        if requested_format == "json":
            _emit_error(error, requested_format)
        else:
            print(parser.format_usage(), end="", file=sys.stderr)
            print(f"{parser.prog}: error: {error}", file=sys.stderr)
        return 2

    if args.diagnostic_format == "json" and args.debug:
        _emit_error(
            _CLIUsageError(
                "--debug cannot be combined with --diagnostic-format json"
            ),
            args.diagnostic_format,
        )
        return 2


    if args.command in ("run", "native-asm", "build", "run-native", "ffi-build") and args.max_instructions < 1:
        _usage_error = _CLIUsageError("--max-instructions must be at least 1")
        if args.diagnostic_format == "json":
            _emit_error(_usage_error, args.diagnostic_format)
        else:
            print(parser.format_usage(), end="", file=sys.stderr)
            print(f"{parser.prog}: error: {_usage_error}", file=sys.stderr)
        return 2

    try:
        if args.command == "doctor":
            _print_doctor()
            return 0
        if args.command == "targets":
            _print_targets()
            return 0
        if args.command == "container":
            tooling = ProjectTooling(args.root)
            provider = DockerProvider()
            if args.container_action == "inspect":
                print(json.dumps(tooling.inspect(), indent=2, sort_keys=True))
                return 0
            if args.container_action == "plan":
                spec = DockerSpec(args.image, ("s3", "run", f"/app/{tooling.manifest.entrypoint}.s3"))
                print(json.dumps(provider.plan(spec), indent=2, sort_keys=True))
                return 0
            context, owner = tooling.docker_context(provider, image=args.image)
            try:
                if args.container_action == "build":
                    result = provider.build(context, args.image)
                else:
                    result = provider.run(
                        DockerSpec(args.image, ("s3", "run", f"/app/{tooling.manifest.entrypoint}.s3"))
                    )
                if result.stdout:
                    print(result.stdout, end="")
                if result.stderr:
                    print(result.stderr, end="", file=sys.stderr)
                return result.returncode
            finally:
                owner.cleanup()
        if args.command == "test":
            report = run_test_manifest(args.manifest, mode=args.mode)
            rendered = render_test_report(report)
            if args.report is not None:
                args.report.parent.mkdir(parents=True, exist_ok=True)
                args.report.write_text(rendered, encoding="utf-8", newline="\n")
            print(rendered, end="")
            return 1 if report["summary"]["status"] == "FAIL" else 2 if report["summary"]["status"] == "SKIP" else 0
        if args.command == "format":
            formatted = format_source(args.source.read_text(encoding="utf-8"))
            if args.write:
                args.source.write_text(formatted, encoding="utf-8", newline="\n")
            else:
                print(formatted, end="")
            return 0
        if args.command == "docs":
            source = args.source.read_text(encoding="utf-8")
            print((render_json if args.json else render_markdown)(source), end="")
            return 0
        if args.max_frames < 1:
            raise NativeBackendError("--max-frames must be at least 1")
        source = args.source.read_text(encoding="utf-8")
        if args.command == "verify-ir":
            module = deserialize_ir(source)
            print(f"IR verified: {len(module.functions)} function(s)")
            return 0
        optimization = OptimizationLevel.parse(args.optimization)
        mode = _SOURCE_SYNTAX_MODES[args.source_syntax]
        compilation = compile_source(source, optimization, mode=mode)
        if args.command == "check":
            _print_check(args.source)
        elif args.command == "inspect":
            if args.emit == "summary":
                _print_inspection(
                    args.source,
                    compilation,
                    syntax=args.source_syntax,
                    optimization=optimization,
                )
            elif args.emit == "ir":
                ir, _ = compilation.require_ordinary_artifacts()
                _print_inspection_artifact(
                    "ir",
                    json.dumps(ir.to_dict(), indent=2),
                )
            elif args.emit == "assembly":
                _print_inspection_artifact(
                    "assembly",
                    compilation.assembly_text,
                )
        elif args.command == "tokens":
            payload = [
                token.to_dict()
                for token in compilation.tokens
                if token.text or token.kind.name != "EOF"
            ]
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        elif args.command == "ast":
            print(json.dumps(ast.to_dict(compilation.ast), indent=2))
        elif args.command == "ir":
            ir, _ = compilation.require_ordinary_artifacts()
            print(json.dumps(ir.to_dict(), indent=2))
        elif args.command == "ir-json":
            ir, _ = compilation.require_ordinary_artifacts()
            artifact = serialize_ir(ir)
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
            _, assembly = compilation.require_ordinary_artifacts()
            result = Emulator(
                max_frames=args.max_frames,
                max_instructions=args.max_instructions,
            ).execute(
                assembly
            )
            print(f"program returned: {result}")
        elif args.command == "native-asm":
            _, assembly = compilation.require_ordinary_artifacts()
            native = generate_native_assembly(
                assembly,
                max_frames=args.max_frames,
                max_instructions=args.max_instructions,
                native_policy=args.native_policy,
            )
            if args.output is None:
                print(native, end="")
            else:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(native, encoding="utf-8", newline="\n")
        elif args.command == "build":
            _, assembly = compilation.require_ordinary_artifacts()
            native = generate_native_assembly(
                assembly,
                max_frames=args.max_frames,
                max_instructions=args.max_instructions,
                native_policy=args.native_policy,
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
        elif args.command == "ffi-build":
            output = (
                args.output
                if args.output is not None
                else Path("build") / f"lib{args.source.stem}.so"
            )
            build_shared_library(
                source,
                output,
                keep_assembly=args.keep_assembly,
                max_instructions=args.max_instructions,
                native_policy=args.native_policy,
                optimization=optimization,
                mode=mode,
            )
            print(output)
        elif args.command == "run-native":
            _, assembly = compilation.require_ordinary_artifacts()
            native = generate_native_assembly(
                assembly,
                max_frames=args.max_frames,
                max_instructions=args.max_instructions,
                native_policy=args.native_policy,
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
            if completed.returncode != 0 and args.diagnostic_format == "json":
                notes = (
                    (completed.stderr.rstrip("\n"),)
                    if completed.stderr
                    else ("standalone ELF emitted no stderr",)
                )
                _emit_diagnostic(
                    Diagnostic(
                        DiagnosticSeverity.ERROR,
                        DiagnosticCategory.NATIVE_RUNTIME,
                        DiagnosticPhase.NATIVE_RUNTIME,
                        DiagnosticCode.NATIVE_PROCESS_FAILED,
                        (
                            "standalone native program exited with status "
                            f"{completed.returncode}"
                        ),
                        file=str(args.source),
                        exit_code=completed.returncode,
                        notes=notes,
                    ),
                    args.diagnostic_format,
                )
            elif completed.stderr:
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
        TestRunnerError,
        DocumentationError,
        FormatterError,
    ) as error:
        if args.debug:
            raise
        _emit_error(
            error,
            args.diagnostic_format,
            file=str(getattr(args, "source", getattr(args, "manifest", ""))),
            internal=False,
        )
        return 1
    except Exception as error:
        if args.debug:
            raise
        _emit_error(
            error,
            args.diagnostic_format,
            file=str(getattr(args, "source", getattr(args, "manifest", ""))),
            internal=True,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
