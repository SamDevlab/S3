"""CLI entry point for executing S3 Reliability Lab v2 R3 campaigns."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# ``python tools/reliability_campaign_v2.py`` sets sys.path[0] to ``tools/``
# rather than the repository root. The R3 evidence procedure intentionally
# supports that direct-script form, so make the checkout root importable before
# importing the ``tools`` package. Module execution (``python -m ...``) is
# unaffected.
if __package__ in {None, ""}:
    _REPO_ROOT = Path(__file__).resolve().parent.parent
    _repo_root_text = str(_REPO_ROOT)
    if _repo_root_text not in sys.path:
        sys.path.insert(0, _repo_root_text)

from tools.reliability_contract_v2 import canonical_json_document
from tools.reliability_differential_v2 import run_campaign, write_campaign_report


def _current_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        check=False,
        capture_output=True,
        text=True,
        shell=False,
        timeout=10.0,
    )
    head = completed.stdout.strip()
    if completed.returncode != 0:
        raise RuntimeError("could not resolve repository HEAD")
    if len(head) != 40 or any(ch not in "0123456789abcdef" for ch in head):
        raise RuntimeError("repository HEAD is not a lowercase 40-hex commit")
    return head


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a bounded deterministic S3 Reliability Lab v2 R3 campaign"
    )
    parser.add_argument("--id", required=True, dest="campaign_id")
    parser.add_argument("--seed", required=True, type=int, dest="campaign_seed")
    parser.add_argument("--cases", required=True, type=int, dest="case_count")
    parser.add_argument("--native-cases", type=int, default=0)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--replay-root", required=True, type=Path)
    parser.add_argument(
        "--expect-head",
        help="fail closed unless the checkout HEAD exactly matches this commit",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    head = _current_head()
    if args.expect_head is not None and args.expect_head != head:
        print(
            json.dumps(
                {
                    "error": "HEAD_MISMATCH",
                    "actual_head": head,
                    "expected_head": args.expect_head,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            file=sys.stderr,
        )
        return 2

    args.replay_root.mkdir(parents=True, exist_ok=True)
    report = run_campaign(
        args.campaign_id,
        args.campaign_seed,
        head,
        case_count=args.case_count,
        native_case_count=args.native_cases,
        replay_root=args.replay_root,
    )
    write_campaign_report(args.report, report)

    counts = dict(report["counts"])
    summary = {
        "schema": "s3.reliability.differential-campaign-summary.v1",
        "campaign_id": report["campaign_id"],
        "compiler_head": report["compiler_head"],
        "case_count": report["case_count"],
        "native_case_count": report["native_case_count"],
        "counts": counts,
        "report": args.report.as_posix(),
        "replay_root": args.replay_root.as_posix(),
    }
    sys.stdout.buffer.write(canonical_json_document(summary))
    sys.stdout.buffer.flush()

    return 0 if set(counts) <= {"PASS"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
