"""Strict wrapper for Stage2/Stage3 fixed-point certification.

The underlying fixed-point harness builds Stage2/Stage3 and runs conformance.
This wrapper adds two independent anti-delegation proofs:
1. direct strace replay rejects descendant execve and Python/bootstrap file use;
2. Landlock replay requires a freestanding ELF and makes every filesystem object
   except the compiler itself unreadable/unexecutable before compiler execve.
Both replays must emit the exact assembly used to build the measured artifacts.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.qualify_selfhost_landlock_replay import (
    LandlockReplayError,
    replay as replay_landlock,
)
from tools.qualify_stage2_stage3_fixed_point import (
    DEFAULT_HOST_IO,
    DEFAULT_MANIFEST,
    DEFAULT_STAGE1_CERT,
    FixedPointError,
    _canonical_source,
    _sanitized_compiler_env,
    _sha256,
    qualify as qualify_fixed_point,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "reports" / "selfhost" / "stage2" / "stage2-stage3-strict-sandbox.json"
_TRACE_FILE_SYSCALLS = ("open", "openat", "openat2")
_PYTHON_PATH_SEGMENT = re.compile(r"/(?:python|python3(?:\.\d+)?)(?:/|$)", re.IGNORECASE)
_LIBPYTHON_BASENAME = re.compile(r"^libpython(?:3(?:\.\d+)*)?.*\.so(?:\..*)?$", re.IGNORECASE)


def _quoted_open_path(line: str) -> str | None:
    if not any(f"{name}(" in line for name in _TRACE_FILE_SYSCALLS):
        return None
    match = re.search(r"open(?:at2|at)?\([^\"]*\"([^\"]+)\"", line)
    return None if match is None else match.group(1)


def _is_python_runtime_path(normalized: str) -> bool:
    lowered = normalized.lower()
    basename = Path(normalized).name
    return (
        lowered.endswith((".py", ".pyc", ".pyo", ".pyz"))
        or "/site-packages/" in lowered
        or lowered.endswith("/site-packages")
        or "/dist-packages/" in lowered
        or lowered.endswith("/dist-packages")
        or _PYTHON_PATH_SEGMENT.search(normalized) is not None
        or _LIBPYTHON_BASENAME.match(basename) is not None
        or ("python" in basename.lower() and basename.lower().endswith(".zip"))
    )


def _is_forbidden_read(path: str) -> bool:
    candidate = Path(path)
    # The compiler receives its entire input on stdin and has no legitimate
    # reason to open cwd-relative files. Failing closed on every relative open
    # also avoids openat/openat2(dirfd, "../../repo/...") bypasses where a
    # textual path would not contain the absolute checkout prefix.
    if not candidate.is_absolute():
        return True
    resolved = candidate.resolve(strict=False)
    normalized = str(resolved).replace("\\", "/")
    root = str(ROOT.resolve()).replace("\\", "/")
    return (
        normalized == root
        or normalized.startswith(root + "/")
        or "/bootstrap/" in normalized
        or _is_python_runtime_path(normalized)
    )


def trace_compiler_sandbox(compiler: Path, source: bytes, *, directory: Path, strace: str) -> dict[str, object]:
    directory.mkdir(parents=True, exist_ok=True)
    trace_path = directory / "process-and-files.trace"
    env = _sanitized_compiler_env(directory / "sandbox-home")
    trace_expression = "execve," + ",".join(_TRACE_FILE_SYSCALLS)
    completed = subprocess.run(
        [strace, "-f", "-qq", "-e", f"trace={trace_expression}", "-o", str(trace_path), str(compiler.resolve())],
        cwd=str(directory),
        input=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        shell=False,
        check=False,
    )
    lines = trace_path.read_text(encoding="utf-8", errors="replace").splitlines() if trace_path.exists() else []
    execves = [line for line in lines if "execve(" in line]
    opens = [path for line in lines if (path := _quoted_open_path(line)) is not None]
    forbidden = [path for path in opens if _is_forbidden_read(path)]
    python_exec = any(re.search(r"python(?:3(?:\.\d+)?)?", line, flags=re.IGNORECASE) for line in execves)
    passed = (
        completed.returncode == 0
        and completed.stderr == b""
        and bool(completed.stdout)
        and len(execves) == 1
        and not python_exec
        and not forbidden
    )
    return {
        "status": "PASS_STRICT_PROCESS_AND_FILE_TRACE" if passed else "FAIL_STRICT_PROCESS_AND_FILE_TRACE",
        "returncode": completed.returncode,
        "stdout_sha256": _sha256(completed.stdout),
        "stdout_bytes": len(completed.stdout),
        "stderr_sha256": _sha256(completed.stderr),
        "stderr_bytes": len(completed.stderr),
        "execve_count": len(execves),
        "execve_lines": execves,
        "python_exec_seen": python_exec,
        "trace_file_syscalls": list(_TRACE_FILE_SYSCALLS),
        "opened_paths": opens,
        "forbidden_checkout_or_python_reads": forbidden,
        "trace_path": str(trace_path),
        "sanitized_environment": env,
    }


def _landlock_or_blocked(
    compiler: Path,
    source: bytes,
    *,
    expected_sha256: str,
    expected_bytes: int,
    workspace: Path,
) -> dict[str, object]:
    try:
        return replay_landlock(
            compiler,
            source,
            expected_assembly_sha256=expected_sha256,
            expected_assembly_bytes=expected_bytes,
            workspace=workspace,
        )
    except (OSError, LandlockReplayError) as error:
        return {
            "schema": "s3.selfhost.landlock-replay.v1",
            "status": "BLOCKED_LANDLOCK_REPLAY",
            "native_execution_evidence": False,
            "error": str(error),
            "qualification": {
                "filesystem_inaccessible_proof": "BLOCKED",
                "process_trace_still_required_independently": True,
                "full_self_hosting": False,
                "next": "REBUILD_STAGE_ARTIFACT_FREESTANDING_OR_FIX_LANDLOCK_SUPPORT",
            },
        }


def qualify_strict(*, stage1: Path, stage1_certification: Path, manifest: Path, host_io: Path, report: Path, workspace: Path, stage4: bool = False) -> dict[str, object]:
    strace = shutil.which("strace")
    if strace is None:
        raise FixedPointError("strace is required for strict process/bootstrap-access proof")
    workspace = workspace.resolve()
    intermediate_report = workspace.parent / (workspace.name + "-intermediate-fixed-point.json")
    base = qualify_fixed_point(
        stage1=stage1,
        stage1_certification=stage1_certification,
        manifest=manifest,
        host_io=host_io,
        report=intermediate_report,
        workspace=workspace,
        stage4=stage4,
    )
    _, source, _ = _canonical_source(manifest.resolve())
    stage1_path = stage1.resolve()
    stage2_path = Path(base["stage2"]["path"]).resolve()

    stage1_trace = trace_compiler_sandbox(stage1_path, source, directory=workspace / "strict-trace-stage1", strace=strace)
    stage2_trace = trace_compiler_sandbox(stage2_path, source, directory=workspace / "strict-trace-stage2", strace=strace)

    stage1_trace_matches_artifact = stage1_trace["stdout_sha256"] == base["stage2"]["build"]["assembly_sha256"]
    stage2_trace_matches_artifact = stage2_trace["stdout_sha256"] == base["stage3"]["build"]["assembly_sha256"]
    strict_trace_pass = (
        stage1_trace["status"] == "PASS_STRICT_PROCESS_AND_FILE_TRACE"
        and stage2_trace["status"] == "PASS_STRICT_PROCESS_AND_FILE_TRACE"
        and stage1_trace_matches_artifact
        and stage2_trace_matches_artifact
    )

    stage1_landlock = _landlock_or_blocked(
        stage1_path,
        source,
        expected_sha256=base["stage2"]["build"]["assembly_sha256"],
        expected_bytes=base["stage2"]["build"]["assembly_bytes"],
        workspace=workspace / "landlock-stage1-to-stage2",
    )
    stage2_landlock = _landlock_or_blocked(
        stage2_path,
        source,
        expected_sha256=base["stage3"]["build"]["assembly_sha256"],
        expected_bytes=base["stage3"]["build"]["assembly_bytes"],
        workspace=workspace / "landlock-stage2-to-stage3",
    )
    landlock_pass = (
        stage1_landlock["status"] == "PASS_LANDLOCK_FILESYSTEM_INACCESSIBLE_REPLAY"
        and stage2_landlock["status"] == "PASS_LANDLOCK_FILESYSTEM_INACCESSIBLE_REPLAY"
    )

    fixed_point_pass = bool(base["fixed_point"]["stage2_stage3_bytes_equal"] and base["fixed_point"]["stage2_stage3_sha256_equal"])
    conformance_pass = base["stage2"]["conformance"]["status"] == "PASS"
    full_self_hosting = bool(
        base["qualification"]["stage1_to_stage2"] == "PASS"
        and base["qualification"]["stage2_to_stage3"] == "PASS"
        and fixed_point_pass
        and conformance_pass
        and strict_trace_pass
        and landlock_pass
        and (not stage4 or base["stage4"]["status"] == "PASS")
    )

    if full_self_hosting:
        next_step = "FULL_SELF_HOSTING_CERTIFICATION_READY"
    elif not landlock_pass:
        next_step = "REBUILD_STAGE_ARTIFACTS_FREESTANDING_OR_REPAIR_LANDLOCK_GATE"
    else:
        next_step = "REPAIR_STRICT_TRACE_CONFORMANCE_OR_FIXED_POINT_GATE"

    result = {
        "schema": "s3.selfhost.stage2-stage3-strict-sandbox.v4",
        "base_fixed_point": base,
        "strict_runtime": {
            "stage1_compiles_stage2": stage1_trace,
            "stage2_compiles_stage3": stage2_trace,
            "stage1_trace_assembly_matches_stage2_build": stage1_trace_matches_artifact,
            "stage2_trace_assembly_matches_stage3_build": stage2_trace_matches_artifact,
            "process_and_file_trace_pass": strict_trace_pass,
            "relative_file_reads_fail_closed": True,
            "absolute_paths_resolved_before_checkout_comparison": True,
            "embedded_python_runtime_file_access_forbidden": True,
            "openat2_traced": True,
            "landlock": {
                "stage1_to_stage2": stage1_landlock,
                "stage2_to_stage3": stage2_landlock,
                "filesystem_inaccessible_proof_pass": landlock_pass,
                "fallback_allowed": False,
            },
            "bootstrap_checkout_inaccessible": landlock_pass,
        },
        "qualification": {
            "stage1_to_stage2": base["qualification"]["stage1_to_stage2"],
            "stage2_pythonless_compiler": "PASS_STRICT_PROCESS_AND_FILE_TRACE" if strict_trace_pass else "FAIL",
            "filesystem_inaccessible": "PASS_LANDLOCK" if landlock_pass else "FAIL_OR_BLOCKED",
            "stage2_conformance": base["stage2"]["conformance"]["status"],
            "stage2_to_stage3": base["qualification"]["stage2_to_stage3"],
            "stage2_stage3_exact_elf_fixed_point": fixed_point_pass,
            "full_self_hosting": full_self_hosting,
            "next": next_step,
        },
    }
    destination = report.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage1", type=Path, required=True)
    parser.add_argument("--stage1-certification", type=Path, default=DEFAULT_STAGE1_CERT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--host-io", type=Path, default=DEFAULT_HOST_IO)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--workspace", type=Path, default=Path(tempfile.gettempdir()) / "s3-stage2-stage3-strict")
    parser.add_argument("--stage4", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = qualify_strict(
            stage1=args.stage1,
            stage1_certification=args.stage1_certification,
            manifest=args.manifest,
            host_io=args.host_io,
            report=args.report,
            workspace=args.workspace,
            stage4=args.stage4,
        )
    except FixedPointError as error:
        parser.exit(2, f"strict self-hosting certification blocked: {error}\n")
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"STAGE2_PYTHONLESS_COMPILER={qualification['stage2_pythonless_compiler']}")
    print(f"FILESYSTEM_INACCESSIBLE={qualification['filesystem_inaccessible']}")
    print(f"STAGE2_CONFORMANCE={qualification['stage2_conformance']}")
    print(f"STAGE2_STAGE3_FIXED_POINT={qualification['stage2_stage3_exact_elf_fixed_point']}")
    print(f"FULL_SELF_HOSTING={qualification['full_self_hosting']}")
    print(f"NEXT={qualification['next']}")
    return 0 if qualification["full_self_hosting"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
