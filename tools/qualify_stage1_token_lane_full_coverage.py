"""Strengthen Stage1 token-lane qualification with native byte-coverage evidence.

The existing native token-lane qualifier compares the candidate's self-source
AST/call audit against a complete static model.  That is necessary, but a future
regression could in principle leave an unobserved source suffix whose tokens do
not affect those aggregate counters.  This wrapper adds an independent native
coverage proof without changing the S3 candidate source: it links the exact
candidate against a qualification-only host I/O shim that records every source
byte index requested through ``s3_stage1_read_byte``.

PASS requires every input byte to be touched, no unread gap, and the maximum
read index to be the final input byte.  The ordinary Stage1 host I/O remains the
canonical runtime boundary; the coverage shim is test instrumentation only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import re
import shutil
import sys
import tempfile
from pathlib import Path

from tools.build_stage1_compiler import build_stage1
from tools.patch_stage1_token_lane_wide_literals import SOURCE, transform
from tools.qualify_stage1_codegen_ir_v2_capacity import _run_stage1
import tools.qualify_stage1_token_lane_wide_literals as base_qualifier


ROOT = Path(__file__).resolve().parents[1]
COVERAGE_HOST_IO = ROOT / "selfhost" / "compiler" / "stage1_host_io_coverage.c"
DEFAULT_BASE_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "packed-token-lane-native-candidate.json"
)
DEFAULT_REPORT = (
    ROOT / "reports" / "selfhost" / "stage1" /
    "packed-token-lane-native-full-coverage.json"
)
_COVERAGE_RE = re.compile(
    r"^S3_STAGE1_COVERAGE length=(?P<length>-?\d+) "
    r"touched=(?P<touched>-?\d+) "
    r"first_unread=(?P<first_unread>-?\d+) "
    r"max_read=(?P<max_read>-?\d+)$"
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _parse_coverage(stderr: bytes) -> dict[str, int] | None:
    for raw_line in stderr.decode("ascii", errors="replace").splitlines():
        match = _COVERAGE_RE.match(raw_line.strip())
        if match is not None:
            return {key: int(value) for key, value in match.groupdict().items()}
    return None


def qualify(
    *,
    report_path: Path = DEFAULT_REPORT,
    base_report_path: Path = DEFAULT_BASE_REPORT,
    run_tests: bool = True,
) -> dict[str, object]:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        raise RuntimeError("full token coverage qualification requires Linux x86-64")
    compiler = shutil.which("cc") or shutil.which("gcc") or shutil.which("clang")
    if compiler is None:
        raise RuntimeError("full token coverage qualification requires cc, gcc, or clang")
    if not COVERAGE_HOST_IO.is_file():
        raise RuntimeError(f"coverage host I/O is missing: {COVERAGE_HOST_IO}")

    base = base_qualifier.qualify(
        report_path=base_report_path,
        run_tests=run_tests,
    )
    base_pass = (
        base.get("qualification", {}).get("token_lane_candidate")
        == "PASS_NATIVE_CANDIDATE"
    )

    baseline_text = SOURCE.read_text(encoding="utf-8")
    candidate_text = transform(baseline_text)
    candidate_bytes = candidate_text.encode("utf-8")

    coverage: dict[str, int] | None = None
    coverage_run: dict[str, object] = {
        "status": "NOT_RUN_BASE_TOKEN_LANE_FAILED",
    }
    coverage_pass = False

    if base_pass:
        with tempfile.TemporaryDirectory(prefix="s3-token-full-coverage-") as directory:
            temp = Path(directory)
            candidate_source = temp / "s3c_stage1.wide-token-lane.s3"
            executable = temp / "s3c-stage1-wide-token-coverage"
            assembly = temp / "s3c-stage1-wide-token-coverage.s"
            candidate_source.write_bytes(candidate_bytes)

            build_stage1(
                executable,
                source=candidate_source,
                host_io=COVERAGE_HOST_IO,
                assembly_output=assembly,
            )
            self_run = _run_stage1(executable, candidate_bytes)
            coverage = _parse_coverage(self_run.stderr)
            expected_length = len(candidate_bytes)
            coverage_pass = bool(
                coverage is not None
                and self_run.returncode == 2
                and self_run.stdout == b""
                and coverage["length"] == expected_length
                and coverage["touched"] == expected_length
                and coverage["first_unread"] == -1
                and coverage["max_read"] == expected_length - 1
            )
            coverage_run = {
                "status": "PASS" if coverage_pass else "FAIL",
                "returncode": self_run.returncode,
                "stdout_bytes": len(self_run.stdout),
                "stderr_lines": self_run.stderr.decode(
                    "ascii", errors="replace"
                ).splitlines(),
                "coverage": coverage,
                "expected_length": expected_length,
                "candidate_sha256": _sha256(candidate_bytes),
            }

    full_pass = base_pass and coverage_pass
    result: dict[str, object] = {
        "schema": "s3.selfhost.packed-token-lane-native-full-coverage.v1",
        "platform": {
            "system": platform.system(),
            "machine": platform.machine(),
            "compiler": compiler,
            "python": sys.executable,
        },
        "canonical_source_mutated": False,
        "canonical_commit_allowed": False,
        "base_native_qualification": base,
        "base_token_lane_pass": base_pass,
        "coverage_instrumentation": {
            "host_io": str(COVERAGE_HOST_IO.relative_to(ROOT)),
            "changes_s3_candidate_source": False,
            "counts_source_reads_only": True,
        },
        "native_source_coverage": coverage_run,
        "qualification": {
            "token_lane_full_coverage": (
                "PASS_NATIVE_FULL_SOURCE_COVERAGE" if full_pass else "FAIL"
            ),
            "next": (
                str(base.get("qualification", {}).get("next"))
                if full_pass
                else "FIX_NATIVE_TOKEN_SOURCE_COVERAGE"
            ),
            "canonical_commit_allowed": False,
            "stage2": "NOT_STARTED",
            "stage3": "NOT_STARTED",
            "full_self_hosting": False,
        },
        "qualification_rule": (
            "PASS requires the ordinary native token-lane candidate PASS and a "
            "separate qualification-only host shim proving every source byte was "
            "requested through s3_stage1_read_byte with no unread gap."
        ),
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
    parser.add_argument("--base-report", type=Path, default=DEFAULT_BASE_REPORT)
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)

    result = qualify(
        report_path=args.report,
        base_report_path=args.base_report,
        run_tests=not args.skip_tests,
    )
    coverage = result["native_source_coverage"].get("coverage")
    print(f"REPORT={args.report.resolve()}")
    print(f"BASE_TOKEN_LANE_PASS={result['base_token_lane_pass']}")
    if isinstance(coverage, dict):
        print(f"SOURCE_LENGTH={coverage['length']}")
        print(f"SOURCE_BYTES_TOUCHED={coverage['touched']}")
        print(f"FIRST_UNREAD={coverage['first_unread']}")
        print(f"MAX_READ={coverage['max_read']}")
    else:
        print("SOURCE_LENGTH=NOT_AVAILABLE")
        print("SOURCE_BYTES_TOUCHED=NOT_AVAILABLE")
        print("FIRST_UNREAD=NOT_AVAILABLE")
        print("MAX_READ=NOT_AVAILABLE")
    qualification = result["qualification"]
    print(f"TOKEN_LANE_FULL_COVERAGE={qualification['token_lane_full_coverage']}")
    print(f"NEXT={qualification['next']}")
    print("CANONICAL_SOURCE_MUTATED=False")
    print("STAGE2=NOT_STARTED")
    print("STAGE3=NOT_STARTED")
    return 0 if qualification["token_lane_full_coverage"] == "PASS_NATIVE_FULL_SOURCE_COVERAGE" else 2


if __name__ == "__main__":
    raise SystemExit(main())
