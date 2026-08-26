"""Replay a freestanding Stage compiler under kernel-enforced Landlock.

Python is orchestration only: it validates the ELF, builds the fixed host sandbox
launcher, feeds source through stdin, captures assembly from stdout, and compares
the exact assembly bytes/SHA to a previously measured build. The compiler cannot
read or execute any other filesystem object after Landlock is installed.
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

from tools.audit_selfhost_freestanding_elf import audit_path
from tools.qualify_stage2_stage3_fixed_point import _sanitized_compiler_env


ROOT = Path(__file__).resolve().parents[1]
LAUNCHER_SOURCE = ROOT / "tools" / "selfhost_landlock_launcher.c"


class LandlockReplayError(RuntimeError):
    pass


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def build_launcher(*, cc: str, directory: Path) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    output = directory / "s3-landlock-launcher"
    completed = subprocess.run(
        [
            cc,
            "-std=c11",
            "-O2",
            "-Wall",
            "-Wextra",
            "-Werror",
            str(LAUNCHER_SOURCE.resolve()),
            "-o",
            str(output),
        ],
        cwd=str(directory),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        shell=False,
    )
    if completed.returncode != 0:
        detail = completed.stderr.decode("utf-8", errors="replace")
        raise LandlockReplayError(
            f"Landlock launcher build failed with status {completed.returncode}: {detail.strip()}"
        )
    return output


def replay(
    compiler: Path,
    source: bytes,
    *,
    expected_assembly_sha256: str,
    expected_assembly_bytes: int | None = None,
    workspace: Path,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise LandlockReplayError("Landlock replay requires Linux x86-64")
    cc = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if cc is None:
        raise LandlockReplayError("cc/gcc/clang is required to build the fixed Landlock launcher")
    compiler = compiler.resolve()
    if not compiler.is_file() or not os.access(compiler, os.X_OK):
        raise LandlockReplayError("compiler artifact is missing or not executable")
    if len(expected_assembly_sha256) != 64 or any(
        char not in "0123456789abcdefABCDEF" for char in expected_assembly_sha256
    ):
        raise LandlockReplayError("expected assembly SHA256 must be a 64-digit hexadecimal digest")

    elf = audit_path(compiler)
    if elf["status"] != "PASS_FREESTANDING_STATIC_ELF":
        raise LandlockReplayError("compiler failed freestanding static ELF prerequisite")

    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    launcher = build_launcher(cc=cc, directory=workspace / "launcher")
    run_dir = workspace / "run"
    run_dir.mkdir(parents=True, exist_ok=True)
    env = _sanitized_compiler_env(run_dir / "sandbox-home")
    completed = subprocess.run(
        [str(launcher.resolve()), str(compiler)],
        cwd=str(run_dir),
        input=source,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        check=False,
        shell=False,
    )
    assembly = completed.stdout
    actual_sha = _sha256(assembly)
    expected_sha = expected_assembly_sha256.lower()
    size_matches = expected_assembly_bytes is None or len(assembly) == expected_assembly_bytes
    passed = (
        completed.returncode == 0
        and completed.stderr == b""
        and bool(assembly)
        and actual_sha == expected_sha
        and size_matches
    )
    return {
        "schema": "s3.selfhost.landlock-replay.v1",
        "status": "PASS_LANDLOCK_FILESYSTEM_INACCESSIBLE_REPLAY" if passed else "FAIL_LANDLOCK_REPLAY",
        "native_execution_evidence": True,
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "cc": cc,
        },
        "compiler": {
            "path": str(compiler),
            "sha256": elf["artifact"]["sha256"],
            "bytes": elf["artifact"]["bytes"],
            "freestanding_elf_status": elf["status"],
        },
        "launcher": {
            "source": str(LAUNCHER_SOURCE.resolve()),
            "path": str(launcher.resolve()),
            "sha256": _sha256(launcher.read_bytes()),
        },
        "sandbox": {
            "mechanism": "LANDLOCK_EXACT_COMPILER_READ_EXEC_ONLY",
            "source_via_stdin": True,
            "other_filesystem_read_allowed": False,
            "other_filesystem_execute_allowed": False,
            "fallback_if_landlock_unsupported": False,
            "sanitized_environment": env,
        },
        "execution": {
            "returncode": completed.returncode,
            "stdout_bytes": len(assembly),
            "stdout_sha256": actual_sha,
            "stderr_bytes": len(completed.stderr),
            "stderr_sha256": _sha256(completed.stderr),
        },
        "artifact_binding": {
            "expected_assembly_sha256": expected_sha,
            "expected_assembly_bytes": expected_assembly_bytes,
            "assembly_sha256_matches": actual_sha == expected_sha,
            "assembly_bytes_matches": size_matches,
        },
        "qualification": {
            "filesystem_inaccessible_proof": "PASS" if passed else "FAIL",
            "process_trace_still_required_independently": True,
            "full_self_hosting": False,
            "next": "COMBINE_WITH_STRICT_PROCESS_TRACE" if passed else "REPAIR_FREESTANDING_OR_LANDLOCK_REPLAY",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--compiler", type=Path, required=True)
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--source", type=Path)
    source_group.add_argument("--source-stdin", action="store_true")
    parser.add_argument("--expected-assembly-sha256", required=True)
    parser.add_argument("--expected-assembly-bytes", type=int)
    parser.add_argument("--workspace", type=Path, default=Path(tempfile.gettempdir()) / "s3-landlock-replay")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    source = (
        os.read(0, 16 * 1024 * 1024)
        if args.source_stdin
        else args.source.resolve().read_bytes()
    )
    try:
        result = replay(
            args.compiler,
            source,
            expected_assembly_sha256=args.expected_assembly_sha256,
            expected_assembly_bytes=args.expected_assembly_bytes,
            workspace=args.workspace,
        )
    except (OSError, LandlockReplayError) as error:
        parser.exit(2, f"Landlock replay blocked: {error}\n")

    if args.report is not None:
        destination = args.report.resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(result, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"REPORT={destination}")
    print(f"STATUS={result['status']}")
    print(f"COMPILER_SHA256={result['compiler']['sha256']}")
    print(f"ASSEMBLY_SHA256={result['execution']['stdout_sha256']}")
    print(f"FILESYSTEM_INACCESSIBLE_PROOF={result['qualification']['filesystem_inaccessible_proof']}")
    print("FULL_SELF_HOSTING=False")
    print(f"NEXT={result['qualification']['next']}")
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
