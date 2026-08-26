"""Native Linux qualifier for the bounded seventh-parameter Stage1 candidate.

The qualifier never mutates the canonical compiler. It constructs the exact
candidate in a temporary directory, builds it through the real Stage0 boundary,
and proves three things: ordinal 6 lowers to the first SysV stack argument,
an eight-parameter function remains fail-closed, and the complete canonical
self-source still stops at the existing general-emitter capability boundary.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import subprocess
import tempfile
from pathlib import Path

from tools.build_stage1_compiler import build_stage1
from tools.patch_stage1_seventh_parameter_return import SOURCE, transform


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" / "seventh-parameter-native-candidate.json"
)

SEVENTH_PARAMETER_ASSEMBLY = b"mov rax, qword ptr [rsp + 8]"
BLOCKED_MARKER = "S3_STAGE1_EMITTER_BLOCKED"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _run_stage1(executable: Path, source: bytes) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(
        [str(executable)],
        input=source,
        capture_output=True,
        check=False,
        shell=False,
    )


def _last_stderr_line(completed: subprocess.CompletedProcess[bytes]) -> str | None:
    lines = completed.stderr.decode("ascii", errors="replace").splitlines()
    return lines[-1] if lines else None


def qualify(report_path: Path) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("seventh-parameter qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("seventh-parameter qualification requires cc, gcc, or clang")

    canonical_text = SOURCE.read_text(encoding="utf-8")
    canonical_bytes = canonical_text.encode("utf-8")
    candidate_text = transform(canonical_text)
    candidate_bytes = candidate_text.encode("utf-8")

    seven_parameter_fixture = (
        b"fn select7(a: i64, b: i64, c: i64, d: i64, e: i64, f: i64, g: i64) -> i64:\n"
        b"    return g\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )
    eight_parameter_fixture = (
        b"fn select8(a: i64, b: i64, c: i64, d: i64, e: i64, f: i64, g: i64, h: i64) -> i64:\n"
        b"    return h\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )

    with tempfile.TemporaryDirectory(prefix="s3-seventh-parameter-") as temporary:
        temp = Path(temporary)
        source_path = temp / "s3c_stage1.seventh-parameter-candidate.s3"
        executable = temp / "s3c-stage1-seventh-parameter"
        assembly_path = temp / "s3c-stage1-seventh-parameter.s"
        source_path.write_text(candidate_text, encoding="utf-8", newline="\n")

        build_stage1(executable, source=source_path, assembly_output=assembly_path)

        seven = _run_stage1(executable, seven_parameter_fixture)
        seven_pass = bool(
            seven.returncode == 0
            and seven.stderr == b""
            and SEVENTH_PARAMETER_ASSEMBLY in seven.stdout.lower()
        )

        eight = _run_stage1(executable, eight_parameter_fixture)
        eight_marker = _last_stderr_line(eight)
        eight_blocked = bool(
            eight.returncode == 2
            and eight.stdout == b""
            and eight_marker == BLOCKED_MARKER
        )

        self_run = _run_stage1(executable, candidate_bytes)
        self_marker = _last_stderr_line(self_run)
        self_boundary = bool(
            self_run.returncode == 2
            and self_run.stdout == b""
            and self_marker == BLOCKED_MARKER
        )

        native_pass = bool(seven_pass and eight_blocked and self_boundary)
        result: dict[str, object] = {
            "schema": "s3.selfhost.stage1-seventh-parameter-native-candidate.v1",
            "platform": {
                "system": platform.system(),
                "machine": platform.machine(),
                "compiler": compiler,
            },
            "canonical_source": {
                "path": str(SOURCE.resolve()),
                "sha256": _sha256(canonical_bytes),
                "bytes": len(canonical_bytes),
                "mutated": False,
            },
            "candidate": {
                "sha256": _sha256(candidate_bytes),
                "bytes": len(candidate_bytes),
                "executable_sha256": _sha256(executable.read_bytes()),
                "assembly_sha256": _sha256(assembly_path.read_bytes()),
                "supported_integer_parameter_ordinals": "0..6",
                "ordinal_6_location": "[rsp+8]",
                "ordinal_7_and_above": "BLOCKED",
            },
            "seven_parameter_fixture": {
                "status": "PASS" if seven_pass else "FAIL",
                "returncode": seven.returncode,
                "stdout_sha256": _sha256(seven.stdout),
                "stderr": seven.stderr.decode("ascii", errors="replace"),
                "required_assembly": SEVENTH_PARAMETER_ASSEMBLY.decode("ascii"),
            },
            "eight_parameter_boundary": {
                "status": "PASS_FAIL_CLOSED" if eight_blocked else "FAIL",
                "returncode": eight.returncode,
                "stdout_bytes": len(eight.stdout),
                "final_marker": eight_marker,
            },
            "self_source": {
                "status": "PASS_EXPECTED_EMITTER_BOUNDARY" if self_boundary else "FAIL_OR_DIFFERENT_BLOCKER",
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_sha256": _sha256(self_run.stderr),
                "final_marker": self_marker,
            },
            "qualification": {
                "candidate_build": "PASS",
                "seventh_parameter_emit": "PASS" if seven_pass else "FAIL",
                "eight_parameter_boundary": "PASS" if eight_blocked else "FAIL",
                "self_source_boundary": "PASS" if self_boundary else "FAIL",
                "seventh_parameter_candidate": "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL",
                "canonical_promotion_allowed": False,
                "canonical_promotion_reason": "Native candidate proof is necessary but not sufficient; promotion remains a separate reviewed step.",
                "general_emitter": "INCREMENTAL_ONLY",
                "self_emit": "BLOCKED_REMAINING_LOSSLESS_TYPED_IR_LANES",
                "stage2": "NOT_STARTED",
                "stage3": "NOT_STARTED",
                "full_self_hosting": False,
            },
        }

    destination = report_path.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)

    result = qualify(args.report)
    qualification = result["qualification"]
    print(f"REPORT={args.report.resolve()}")
    print(f"SEVENTH_PARAMETER_CANDIDATE={qualification['seventh_parameter_candidate']}")
    print(f"SEVENTH_PARAMETER_EMIT={qualification['seventh_parameter_emit']}")
    print(f"EIGHT_PARAMETER_BOUNDARY={qualification['eight_parameter_boundary']}")
    print(f"SELF_EMIT={qualification['self_emit']}")
    print(f"FULL_SELF_HOSTING={qualification['full_self_hosting']}")
    return 0 if qualification["seventh_parameter_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
