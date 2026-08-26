"""Native Linux qualifier for the parameter semantic-value-ID candidate.

The qualifier never edits the canonical compiler. It builds the transformed
candidate through the real Stage0 boundary, proves that global parameter value
IDs resolve back to the correct ABI ordinal across multiple functions, and
requires the complete candidate self-source to remain at the existing guarded
general-emitter boundary.
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
from tools.patch_stage1_parameter_semantic_value_ids import SOURCE, transform


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = (
    ROOT
    / "reports"
    / "selfhost"
    / "stage1"
    / "parameter-semantic-value-native-candidate.json"
)
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
        raise RuntimeError("parameter semantic-value qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("parameter semantic-value qualification requires cc, gcc, or clang")

    canonical_text = SOURCE.read_text(encoding="utf-8")
    canonical_bytes = canonical_text.encode("utf-8")
    candidate_text = transform(canonical_text)
    candidate_bytes = candidate_text.encode("utf-8")

    # The second function starts after two parameter slots. Its z parameter has
    # global semantic value ID 4 but ABI ordinal 2. If lowering accidentally
    # treats the semantic ID as an ABI ordinal it would select r8 rather than rdx.
    fixture = (
        b"fn first(a: i64, b: i64) -> i64:\n"
        b"    return b\n"
        b"fn target(x: i64, y: i64, z: i64) -> i64:\n"
        b"    return z\n"
        b"fn main() -> tryte:\n"
        b"    return 9\n"
    )

    with tempfile.TemporaryDirectory(prefix="s3-parameter-value-id-") as temporary:
        temp = Path(temporary)
        source_path = temp / "s3c_stage1.parameter-semantic-value-candidate.s3"
        executable = temp / "s3c-stage1-parameter-semantic-value"
        assembly_path = temp / "s3c-stage1-parameter-semantic-value.s"
        source_path.write_text(candidate_text, encoding="utf-8", newline="\n")

        build_stage1(executable, source=source_path, assembly_output=assembly_path)

        fixture_run = _run_stage1(executable, fixture)
        fixture_lower = fixture_run.stdout.lower()
        fixture_pass = bool(
            fixture_run.returncode == 0
            and fixture_run.stderr == b""
            and b"mov rax, rsi" in fixture_lower
            and b"mov rax, rdx" in fixture_lower
        )

        self_run = _run_stage1(executable, candidate_bytes)
        self_marker = _last_stderr_line(self_run)
        self_boundary = bool(
            self_run.returncode == 2
            and self_run.stdout == b""
            and self_marker == BLOCKED_MARKER
        )

        native_pass = bool(fixture_pass and self_boundary)
        result: dict[str, object] = {
            "schema": "s3.selfhost.stage1-parameter-semantic-value-native-candidate.v1",
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
                "parameter_value_id": "parameter_slot",
                "parameter_value_namespace": "[0,parameter_count)",
                "extra_value_id_storage": 0,
            },
            "cross_function_parameter_fixture": {
                "status": "PASS" if fixture_pass else "FAIL",
                "returncode": fixture_run.returncode,
                "stdout_sha256": _sha256(fixture_run.stdout),
                "stderr": fixture_run.stderr.decode("ascii", errors="replace"),
                "required_lowerings": ["mov rax, rsi", "mov rax, rdx"],
                "distinguishing_case": {
                    "function": "target",
                    "parameter": "z",
                    "semantic_value_id": 4,
                    "abi_ordinal": 2,
                    "expected_register": "rdx",
                },
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
                "semantic_value_id_lowering": "PASS" if fixture_pass else "FAIL",
                "self_source_boundary": "PASS" if self_boundary else "FAIL",
                "parameter_semantic_value_candidate": "PASS_NATIVE_CANDIDATE" if native_pass else "FAIL",
                "canonical_promotion_allowed": False,
                "canonical_promotion_reason": "Native candidate proof is necessary but promotion remains a separate reviewed source change.",
                "parameter_mutability": "NOT_REPRESENTED",
                "locals": "NOT_REBASED_TO_PROMOTED_PARAMETER_NAMESPACE",
                "unified_value_def_use": "INCOMPLETE",
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
    print(f"PARAMETER_SEMANTIC_VALUE_CANDIDATE={qualification['parameter_semantic_value_candidate']}")
    print(f"SEMANTIC_VALUE_ID_LOWERING={qualification['semantic_value_id_lowering']}")
    print(f"PARAMETER_MUTABILITY={qualification['parameter_mutability']}")
    print(f"SELF_EMIT={qualification['self_emit']}")
    print(f"FULL_SELF_HOSTING={qualification['full_self_hosting']}")
    return 0 if qualification["parameter_semantic_value_candidate"] == "PASS_NATIVE_CANDIDATE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
