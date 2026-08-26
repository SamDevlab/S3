"""Qualify final Stage1 self-emission and materialize a real Stage2 candidate.

This is the last Stage1-specific gate before the machine-readable Stage1
certification document may be emitted.  Python is orchestration only: the exact
Stage1 executable receives the exact canonical compiler source on stdin and must
emit assembly itself.  Two independent strict-trace runs and two direct replays
must agree byte-for-byte.  Both assemblies are linked with the same host object
and deterministic recipe, and the resulting Stage2 ELFs must be exact bytes.
The Stage2 candidate must then compile and execute a minimal program under the
same strict process/filesystem trace policy.

PASS here still does not certify Stage2 and never authorizes Stage3 by itself.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from tools.audit_selfhost_freestanding_elf import audit_path as audit_elf
from tools.qualify_stage2_stage3_fixed_point import (
    DEFAULT_HOST_IO,
    FixedPointError,
    _assemble_link,
    _compile_host_object,
    _sanitized_compiler_env,
)
from tools.qualify_stage2_stage3_strict_sandbox import trace_compiler_sandbox


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "selfhost" / "compiler" / "s3c_stage1.s3"
DEFAULT_SEMANTIC_IR = (
    ROOT / "reports" / "selfhost" / "stage1"
    / "stage1-final-semantic-ir-verifier.json"
)
DEFAULT_CONTRACT = (
    ROOT / "reports" / "selfhost" / "stage1" / "final-self-emit-contract.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "stage1-final-self-emit.json"
)
DEFAULT_WORKSPACE = Path(tempfile.gettempdir()) / "s3-stage1-final-self-emit"
SMOKE_SOURCE = b"fn main() -> tryte:\n    return 7\n"


class FinalSelfEmitError(RuntimeError):
    pass


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha_path(path: Path) -> str:
    return _sha_bytes(path.read_bytes())


def _load_json(path: Path, label: str) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise FinalSelfEmitError(f"{label} is missing: {path}") from error
    except json.JSONDecodeError as error:
        raise FinalSelfEmitError(f"{label} is invalid JSON: {path}") from error
    if not isinstance(value, dict):
        raise FinalSelfEmitError(f"{label} must be a JSON object")
    return value


def _artifact_binding(path: Path) -> dict[str, Any]:
    resolved = path.resolve()
    if not resolved.is_file():
        raise FinalSelfEmitError(f"artifact is missing: {resolved}")
    return {
        "path": str(resolved),
        "sha256": _sha_path(resolved),
        "bytes": resolved.stat().st_size,
    }


def validate_semantic_ir_dependency(
    document: dict[str, Any],
    *,
    canonical_sha: str,
    canonical_bytes: int,
    stage1_sha: str,
    stage1_bytes: int,
) -> None:
    if document.get("schema") != "s3.selfhost.stage1-final-semantic-ir-verifier.v1":
        raise FinalSelfEmitError("final semantic IR/verifier report schema mismatch")
    qualification = document.get("qualification")
    if not isinstance(qualification, dict):
        raise FinalSelfEmitError("semantic IR report lacks qualification")
    expected = {
        "semantic_ir": "PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET",
        "verifier_v2": "PASS",
        "general_emitter": "PASS_BOOTSTRAP_REQUIRED_OPCODES",
    }
    for key, value in expected.items():
        if qualification.get(key) != value:
            raise FinalSelfEmitError(
                f"semantic IR prerequisite {key} must be {value!r}"
            )
    canonical = document.get("canonical_source")
    stage1 = document.get("stage1")
    if not isinstance(canonical, dict):
        raise FinalSelfEmitError("semantic IR report lacks canonical source binding")
    if canonical.get("sha256") != canonical_sha or canonical.get("bytes") != canonical_bytes:
        raise FinalSelfEmitError("semantic IR report is bound to a different canonical source")
    if not isinstance(stage1, dict):
        raise FinalSelfEmitError("semantic IR report lacks Stage1 binding")
    if stage1.get("sha256") != stage1_sha or stage1.get("bytes") != stage1_bytes:
        raise FinalSelfEmitError("semantic IR report is bound to a different Stage1 artifact")


def _direct_replay(
    compiler: Path,
    source: bytes,
    *,
    directory: Path,
) -> subprocess.CompletedProcess[bytes]:
    directory.mkdir(parents=True, exist_ok=True)
    return subprocess.run(
        [str(compiler.resolve())],
        cwd=str(directory),
        input=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
        env=_sanitized_compiler_env(directory / "sandbox-home"),
    )


def _trace_and_replay(
    compiler: Path,
    source: bytes,
    *,
    directory: Path,
    strace: str,
    label: str,
) -> tuple[bytes, dict[str, Any]]:
    trace = trace_compiler_sandbox(
        compiler,
        source,
        directory=directory / "trace",
        strace=strace,
    )
    if trace.get("status") != "PASS_STRICT_PROCESS_AND_FILE_TRACE":
        raise FinalSelfEmitError(f"{label} strict trace did not PASS")
    if trace.get("execve_count") != 1 or trace.get("python_exec_seen") is not False:
        raise FinalSelfEmitError(f"{label} strict process proof failed")
    forbidden = trace.get("forbidden_checkout_or_python_reads")
    if not isinstance(forbidden, list) or forbidden:
        raise FinalSelfEmitError(f"{label} accessed forbidden checkout/Python paths")

    replay = _direct_replay(
        compiler,
        source,
        directory=directory / "replay",
    )
    if replay.returncode != 0:
        raise FinalSelfEmitError(
            f"{label} replay failed with returncode {replay.returncode}"
        )
    if replay.stderr != b"":
        raise FinalSelfEmitError(f"{label} replay emitted stderr")
    if not replay.stdout:
        raise FinalSelfEmitError(f"{label} replay emitted empty assembly")
    assembly_sha = _sha_bytes(replay.stdout)
    if trace.get("stdout_sha256") != assembly_sha:
        raise FinalSelfEmitError(f"{label} trace/replay assembly SHA mismatch")
    if trace.get("stdout_bytes") != len(replay.stdout):
        raise FinalSelfEmitError(f"{label} trace/replay assembly byte-count mismatch")

    normalized_trace = dict(trace)
    normalized_trace["trace_replay_assembly_binding"] = True
    normalized_trace["replay_returncode"] = replay.returncode
    normalized_trace["replay_stderr_bytes"] = len(replay.stderr)
    normalized_trace["assembly_sha256"] = assembly_sha
    normalized_trace["assembly_bytes"] = len(replay.stdout)
    return replay.stdout, normalized_trace


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


def qualify(
    *,
    stage1: Path,
    source: Path,
    semantic_ir_report_path: Path,
    contract_path: Path,
    host_io: Path,
    report: Path,
    workspace: Path,
) -> dict[str, Any]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise FinalSelfEmitError("final Stage1 self-emit qualification requires Linux x86-64")
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    strace = shutil.which("strace")
    if cc is None:
        raise FinalSelfEmitError("cc/gcc/clang is required for Stage2 assembly/link")
    if strace is None:
        raise FinalSelfEmitError("strace is required for final Stage1 self-emit proof")

    contract = _load_json(contract_path.resolve(), "final self-emit contract")
    if contract.get("schema") != "s3.selfhost.stage1-final-self-emit-contract.v1":
        raise FinalSelfEmitError("final self-emit contract schema mismatch")

    stage1 = stage1.resolve()
    source = source.resolve()
    host_io = host_io.resolve()
    if not stage1.is_file() or not os.access(stage1, os.X_OK):
        raise FinalSelfEmitError("Stage1 artifact is missing or not executable")
    if not source.is_file():
        raise FinalSelfEmitError("canonical compiler source is missing")
    if not host_io.is_file():
        raise FinalSelfEmitError("Stage1 host I/O shim is missing")

    source_bytes = source.read_bytes()
    canonical = {
        "path": str(source),
        "sha256": _sha_bytes(source_bytes),
        "bytes": len(source_bytes),
    }
    stage1_binding = _artifact_binding(stage1)

    semantic_ir_path = semantic_ir_report_path.resolve()
    semantic_ir = _load_json(semantic_ir_path, "final semantic IR/verifier report")
    validate_semantic_ir_dependency(
        semantic_ir,
        canonical_sha=canonical["sha256"],
        canonical_bytes=canonical["bytes"],
        stage1_sha=stage1_binding["sha256"],
        stage1_bytes=stage1_binding["bytes"],
    )

    workspace = workspace.resolve()
    if workspace.exists():
        shutil.rmtree(workspace)
    workspace.mkdir(parents=True)
    host_object = _compile_host_object(cc, host_io, workspace)
    host_binding = _artifact_binding(host_object)

    assembly_a, run_a = _trace_and_replay(
        stage1,
        source_bytes,
        directory=workspace / "self-emit-a",
        strace=strace,
        label="Stage1 self-emit A",
    )
    assembly_b, run_b = _trace_and_replay(
        stage1,
        source_bytes,
        directory=workspace / "self-emit-b",
        strace=strace,
        label="Stage1 self-emit B",
    )
    if assembly_a != assembly_b:
        raise FinalSelfEmitError("Stage1 self-emitted assembly is not deterministic bytes")
    if _sha_bytes(assembly_a) != _sha_bytes(assembly_b):
        raise FinalSelfEmitError("Stage1 self-emitted assembly SHA mismatch")

    stage2_a = _assemble_link(
        assembly_a,
        cc=cc,
        host_object=host_object,
        directory=workspace / "stage2-a",
        output_name="s3c-stage2-a",
    )
    stage2_b = _assemble_link(
        assembly_b,
        cc=cc,
        host_object=host_object,
        directory=workspace / "stage2-b",
        output_name="s3c-stage2-b",
    )
    stage2_a_bytes = stage2_a.read_bytes()
    stage2_b_bytes = stage2_b.read_bytes()
    if stage2_a_bytes != stage2_b_bytes:
        raise FinalSelfEmitError("Stage2 ELF artifacts are not deterministic bytes")
    if _sha_bytes(stage2_a_bytes) != _sha_bytes(stage2_b_bytes):
        raise FinalSelfEmitError("Stage2 ELF SHA mismatch")

    elf_a = audit_elf(stage2_a)
    elf_b = audit_elf(stage2_b)
    if elf_a.get("status") != "PASS_FREESTANDING_STATIC_ELF":
        raise FinalSelfEmitError("Stage2 A is not a freestanding static ELF")
    if elf_b.get("status") != "PASS_FREESTANDING_STATIC_ELF":
        raise FinalSelfEmitError("Stage2 B is not a freestanding static ELF")

    smoke_assembly, smoke_trace = _trace_and_replay(
        stage2_a,
        SMOKE_SOURCE,
        directory=workspace / "stage2-smoke-compile",
        strace=strace,
        label="Stage2 smoke compile",
    )
    smoke_program = _assemble_link(
        smoke_assembly,
        cc=cc,
        host_object=host_object,
        directory=workspace / "stage2-smoke-program",
        output_name="program",
    )
    smoke_run = _run_program(smoke_program)
    if smoke_run.returncode != 7:
        raise FinalSelfEmitError(
            f"Stage2 smoke program returned {smoke_run.returncode}; expected 7"
        )
    if smoke_run.stdout != b"" or smoke_run.stderr != b"":
        raise FinalSelfEmitError("Stage2 smoke program emitted unexpected output")

    stage2_binding = _artifact_binding(stage2_a)
    result: dict[str, Any] = {
        "schema": contract["output_schema"],
        "canonical_source": canonical,
        "stage1": stage1_binding,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "compiler": cc,
            "strace": strace,
        },
        "semantic_ir_dependency": {
            "path": str(semantic_ir_path),
            "sha256": _sha_path(semantic_ir_path),
            "schema": semantic_ir["schema"],
            "same_canonical_source": True,
            "same_stage1_artifact": True,
        },
        "host_object": host_binding,
        "self_emit": {
            "run_a": run_a,
            "run_b": run_b,
            "assembly_bytes_equal": True,
            "assembly_sha256_equal": True,
            "assembly_sha256": _sha_bytes(assembly_a),
            "assembly_bytes": len(assembly_a),
            "same_host_object_for_both_links": True,
        },
        "stage2": {
            **stage2_binding,
            "second_artifact": _artifact_binding(stage2_b),
            "elf_bytes_equal": True,
            "elf_sha256_equal": True,
            "freestanding_elf_audit": elf_a,
            "second_freestanding_elf_audit": elf_b,
            "certified": False,
        },
        "stage2_smoke": {
            "source_sha256": _sha_bytes(SMOKE_SOURCE),
            "source_bytes": len(SMOKE_SOURCE),
            "strict_compiler_trace": smoke_trace,
            "trace_replay_assembly_binding": True,
            "assembly_sha256": _sha_bytes(smoke_assembly),
            "assembly_bytes": len(smoke_assembly),
            "program": _artifact_binding(smoke_program),
            "program_exit": smoke_run.returncode,
            "program_stdout_bytes": len(smoke_run.stdout),
            "program_stderr_bytes": len(smoke_run.stderr),
            "status": "PASS",
        },
        "qualification": {
            "self_emit": "PASS",
            "stage1_certified_candidate": True,
            "stage2_artifact_created": True,
            "stage2_certified": False,
            "stage3_started": False,
            "full_self_hosting": False,
            "next": "EMIT_AND_REVALIDATE_STAGE1_CERTIFICATION_GATE_THEN_RUN_STAGE2_STAGE3_HARNESS",
        },
    }

    destination = report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--semantic-ir-report", type=Path, default=DEFAULT_SEMANTIC_IR)
    parser.add_argument("--contract", type=Path, default=DEFAULT_CONTRACT)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--workspace", type=Path, default=DEFAULT_WORKSPACE)
    args = parser.parse_args(argv)
    try:
        result = qualify(
            stage1=args.stage1,
            source=args.source,
            semantic_ir_report_path=args.semantic_ir_report,
            contract_path=args.contract,
            host_io=args.host_io,
            report=args.report,
            workspace=args.workspace,
        )
    except (FinalSelfEmitError, FixedPointError, OSError, ValueError) as error:
        parser.exit(2, f"Stage1 final self-emit blocked: {error}\n")

    print(f"REPORT={args.report.resolve()}")
    print("SELF_EMIT=PASS")
    print(f"STAGE2_SHA256={result['stage2']['sha256']}")
    print("STAGE1_CERTIFIED_CANDIDATE=YES")
    print("STAGE2_CERTIFIED=NO")
    print("STAGE3_STARTED=NO")
    print("FULL_SELF_HOSTING=NO")
    print(f"NEXT={result['qualification']['next']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
