from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from bootstrap.s3.developer_experience import format_source, init_project
from bootstrap.s3.diagnostics import S3Error, diagnostic_from_exception
from bootstrap.s3.docs_generator import render_json, render_markdown
from bootstrap.s3.formatter import format_file
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.project_container import ProjectTooling
from bootstrap.s3.test_runner import render_test_report, run_test_manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="s3-tools")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser("commands", help="print commands supported by the pinned S3 CLI")

    project = commands.add_parser("project", help="inspect, compile, or explicitly run an s3.toml project")
    project.add_argument("action", choices=("init", "check", "inspect", "build", "run"))
    project.add_argument("path", type=Path)
    project.add_argument("--name", help="project name for init")

    source = commands.add_parser("source", help="format, check, or generate API docs for one source")
    source.add_argument("action", choices=("format", "check", "docs"))
    source.add_argument("path", type=Path)
    source.add_argument("--write", action="store_true", help="write formatter output to the source")
    source.add_argument("--json", action="store_true", help="emit JSON API documentation")

    test = commands.add_parser("test", help="run the existing S3 test manifest")
    test.add_argument("manifest", type=Path)
    test.add_argument("--mode", choices=("hosted", "native", "both"))
    test.add_argument("--report", type=Path)
    return parser


def _check(path: Path) -> tuple[int, dict[str, Any]]:
    try:
        source = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return 2, {"status": "IO_ERROR", "file": str(path), "message": str(error)}
    try:
        compile_source(source)
    except S3Error as error:
        diagnostic = diagnostic_from_exception(error, file=str(path))
        location = error.location
        lines = source.splitlines()
        line_text = lines[location.line - 1] if location and location.line <= len(lines) else ""
        return 1, {
            "status": "ERROR",
            "file": str(path),
            "category": diagnostic.category.value,
            "phase": diagnostic.phase.value,
            "code": diagnostic.code.value,
            "message": diagnostic.message,
            "line": location.line if location else None,
            "column": location.column if location else None,
            "excerpt": line_text,
        }
    return 0, {"status": "PASS", "file": str(path), "compiler": "pinned bootstrap"}


def _project(action: str, path: Path, name: str | None) -> tuple[int, Any]:
    if action == "init":
        if not name:
            return 2, {"status": "USAGE_ERROR", "message": "project init requires --name"}
        manifest = init_project(path, name)
        return 0, {"status": "PASS", "manifest": str(manifest)}
    tooling = ProjectTooling(path)
    if action in {"check", "inspect"}:
        result = tooling.inspect()
        return 0, {"status": "PASS", **result}
    if action == "build":
        compilation = tooling.build()
        ir, assembly = compilation.require_ordinary_artifacts()
        return 0, {
            "status": "PASS",
            "execution_mode": "COMPILE_ONLY",
            "ir_functions": len(ir.functions),
            "assembly_functions": len(assembly.functions),
        }
    if action == "run":
        # This path is only called by the explicit `project run` subcommand.
        return 0, {"status": "PASS", "execution_mode": "HOSTED_EXECUTION", "actual_output": tooling.run()}
    raise AssertionError(action)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "commands":
        from bootstrap.s3.cli import _parser as compiler_parser

        print(compiler_parser().format_help(), end="")
        return 0
    if args.command == "source":
        if args.action == "format":
            if args.write:
                formatted = format_file(args.path)
            else:
                formatted = format_source(args.path.read_text(encoding="utf-8"))
            print(formatted, end="")
            return 0
        if args.action == "docs":
            source = args.path.read_text(encoding="utf-8")
            output = render_json(source) if args.json else render_markdown(source)
            print(output, end="")
            return 0
        status, diagnostic = _check(args.path)
        print(json.dumps(diagnostic, ensure_ascii=False, indent=2, sort_keys=True))
        return status
    if args.command == "project":
        try:
            status, report = _project(args.action, args.path, args.name)
        except Exception as error:
            print(json.dumps({"status": "ERROR", "message": str(error)}, ensure_ascii=False))
            return 1
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        return status
    if args.command == "test":
        try:
            report = run_test_manifest(args.manifest, mode=args.mode)
        except Exception as error:
            print(json.dumps({"status": "ERROR", "message": str(error)}, ensure_ascii=False))
            return 1
        rendered = render_test_report(report)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered, encoding="utf-8", newline="\n")
        print(rendered, end="")
        return int(report["summary"]["status"] != "PASS")
    return 2


if __name__ == "__main__":
    sys.exit(main())
