"""Qualify representative codegen-complete Stage1 fixtures on Linux x86-64.

Python is orchestration only.  The supplied Stage1 executable receives fixture
source on stdin and must emit assembly itself.  Compiler invocations use the
strict process/filesystem trace policy; emitted assembly is assembled/linked
with the same freestanding host shim used by the compiler seed and then executed.
This report is necessary evidence for Stage1 certification but is not itself a
self-hosting certificate.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.qualify_stage2_stage3_fixed_point import (
    DEFAULT_HOST_IO,
    FixedPointError,
    _assemble_link,
    _compile_host_object,
    _sha256,
)
from tools.qualify_stage2_stage3_strict_sandbox import trace_compiler_sandbox


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_FIXTURES = ROOT / "tests" / "stage1_codegen_complete_fixtures.json"
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage1" / "stage1-codegen-complete-fixtures-native.json"


def _run_program(path: Path) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(path.resolve())],
        cwd=str(path.parent),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        env={"PATH": "/nonexistent", "LANG": "C", "LC_ALL": "C", "TZ": "UTC"},
    )


def _fixture_document(path: Path) -> dict[str, object]:
    document = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or document.get("schema") != "s3.selfhost.stage1-codegen-complete-fixtures.v1":
        raise FixedPointError("Stage1 codegen fixture schema mismatch")
    if not isinstance(document.get("fixtures"), list) or not isinstance(document.get("negative_fixtures"), list):
        raise FixedPointError("Stage1 fixture document lacks fixture lists")
    return document


def qualify(*, stage1: Path, fixtures: Path, host_io: Path, report: Path, workspace: Path) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise FixedPointError("Stage1 codegen-complete fixture qualification requires Linux x86-64")
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    strace = shutil.which("strace")
    if cc is None:
        raise FixedPointError("cc/gcc/clang is required for fixture assembly/link")
    if strace is None:
        raise FixedPointError("strace is required for strict Stage1 compiler trace")
    stage1 = stage1.resolve()
    if not stage1.is_file() or not os.access(stage1, os.X_OK):
        raise FixedPointError("Stage1 executable is missing or not executable")

    document = _fixture_document(fixtures.resolve())
    workspace = workspace.resolve()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    host_object = _compile_host_object(cc, host_io.resolve(), workspace)

    positive_results: list[dict[str, object]] = []
    positive_pass = True
    for raw in document["fixtures"]:
        if not isinstance(raw, dict):
            raise FixedPointError("fixture entry is not an object")
        name = raw.get("name")
        source = raw.get("source")
        expected_exit = raw.get("expected_exit")
        expected_stdout_hex = raw.get("expected_stdout_hex")
        if not isinstance(name, str) or not isinstance(source, str) or not isinstance(expected_exit, int) or not isinstance(expected_stdout_hex, str):
            raise FixedPointError("fixture entry is malformed")
        directory = workspace / "positive" / name
        trace = trace_compiler_sandbox(
            stage1,
            source.encode("utf-8"),
            directory=directory,
            strace=strace,
        )
        compile_pass = trace["status"] == "PASS_STRICT_PROCESS_AND_FILE_TRACE" and trace["stdout_bytes"] > 0
        actual_exit: int | None = None
        actual_stdout = b""
        actual_stderr = b""
        assembly_sha: str | None = None
        if compile_pass:
            # Replay is safe because the strict trace already proved this exact
            # source compile does not delegate; bind the assembly by SHA.
            replay = subprocess.run(
                [str(stage1)],
                cwd=str(directory),
                input=source.encode("utf-8"),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=False,
                shell=False,
                env={"PATH": "/nonexistent", "PYTHONPATH": "", "PYTHONHOME": "", "LANG": "C", "LC_ALL": "C", "TZ": "UTC"},
            )
            assembly_sha = _sha256(replay.stdout)
            compile_pass = (
                replay.returncode == 0
                and replay.stderr == b""
                and bool(replay.stdout)
                and assembly_sha == trace["stdout_sha256"]
            )
            if compile_pass:
                program = _assemble_link(
                    replay.stdout,
                    cc=cc,
                    host_object=host_object,
                    directory=directory,
                    output_name="program",
                )
                executed = _run_program(program)
                actual_exit = executed.returncode
                actual_stdout = executed.stdout
                actual_stderr = executed.stderr
        expected_stdout = bytes.fromhex(expected_stdout_hex)
        passed = (
            compile_pass
            and actual_exit == expected_exit
            and actual_stdout == expected_stdout
            and actual_stderr == b""
        )
        positive_pass = positive_pass and passed
        positive_results.append({
            "name": name,
            "logical_requirements": raw.get("logical_requirements", []),
            "strict_compiler_trace": trace,
            "compile_pass": compile_pass,
            "assembly_sha256": assembly_sha,
            "expected_exit": expected_exit,
            "actual_exit": actual_exit,
            "expected_stdout_hex": expected_stdout_hex,
            "actual_stdout_hex": actual_stdout.hex(),
            "runtime_stderr_bytes": len(actual_stderr),
            "pass": passed,
        })

    negative_results: list[dict[str, object]] = []
    negative_pass = True
    for raw in document["negative_fixtures"]:
        if not isinstance(raw, dict) or not isinstance(raw.get("name"), str) or not isinstance(raw.get("source"), str):
            raise FixedPointError("negative fixture entry is malformed")
        name = raw["name"]
        source_bytes = raw["source"].encode("utf-8")
        directory = workspace / "negative" / name
        first = trace_compiler_sandbox(stage1, source_bytes, directory=directory / "first", strace=strace)
        second = trace_compiler_sandbox(stage1, source_bytes, directory=directory / "second", strace=strace)
        passed = (
            first["status"] == "FAIL_STRICT_PROCESS_AND_FILE_TRACE"
            and second["status"] == "FAIL_STRICT_PROCESS_AND_FILE_TRACE"
            and first["returncode"] != 0
            and second["returncode"] == first["returncode"]
            and first["stdout_sha256"] == second["stdout_sha256"]
            and first["stderr_sha256"] == second["stderr_sha256"]
            and first["execve_count"] == 1
            and second["execve_count"] == 1
            and not first["python_exec_seen"]
            and not second["python_exec_seen"]
            and not first["forbidden_checkout_or_python_reads"]
            and not second["forbidden_checkout_or_python_reads"]
        )
        negative_pass = negative_pass and passed
        negative_results.append({
            "name": name,
            "required": raw.get("required"),
            "first": first,
            "second": second,
            "pass": passed,
        })

    passed = positive_pass and negative_pass
    result = {
        "schema": "s3.selfhost.stage1-codegen-complete-fixtures-native.v1",
        "stage1": {"path": str(stage1), "sha256": _sha256(stage1.read_bytes()), "bytes": stage1.stat().st_size},
        "host_object": {"sha256": _sha256(host_object.read_bytes()), "bytes": host_object.stat().st_size},
        "positive": {"status": "PASS" if positive_pass else "FAIL", "fixtures": positive_results},
        "negative": {"status": "PASS" if negative_pass else "FAIL", "fixtures": negative_results},
        "qualification": {
            "codegen_complete_representative_fixtures": "PASS" if passed else "FAIL",
            "stage1_certified_for_stage2": False,
            "native_evidence": True,
            "next": "CANONICAL_SELF_EMIT_AND_VERIFIER_V2_CERTIFICATION_STILL_REQUIRED" if passed else "REPAIR_STAGE1_VERIFIED_IR_OR_GENERAL_EMITTER",
        },
    }
    destination = report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--fixtures", type=Path, default=DEFAULT_FIXTURES)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--workspace", type=Path, default=Path(tempfile.gettempdir()) / "s3-stage1-codegen-complete-fixtures")
    args = parser.parse_args(argv)
    try:
        result = qualify(
            stage1=args.stage1,
            fixtures=args.fixtures,
            host_io=args.host_io,
            report=args.report,
            workspace=args.workspace,
        )
    except FixedPointError as error:
        parser.exit(2, f"Stage1 fixture qualification blocked: {error}\n")
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"POSITIVE={result['positive']['status']}")
    print(f"NEGATIVE={result['negative']['status']}")
    print(f"CODEGEN_COMPLETE_FIXTURES={qualification['codegen_complete_representative_fixtures']}")
    print("STAGE1_CERTIFIED_FOR_STAGE2=False")
    print(f"NEXT={qualification['next']}")
    return 0 if qualification["codegen_complete_representative_fixtures"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
