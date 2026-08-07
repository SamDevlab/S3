"""CLI entry point for persisted s3bench repeatability analysis."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from benchmarks.s3bench.repeatability import (  # noqa: E402
    RepeatabilityError,
    analyze_root,
    publish_reports,
    render_analysis_markdown,
)


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze repeatability of persisted s3bench runs")
    parser.add_argument("root", type=Path)
    parser.add_argument("--output-json", type=Path, required=True)
    parser.add_argument("--output-markdown", type=Path, required=True)
    parser.add_argument("--expected-runs", type=int, default=3)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = create_parser().parse_args(argv)
    try:
        document = analyze_root(args.root, expected_runs=args.expected_runs)
        json_text = json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False) + "\n"
        markdown_text = render_analysis_markdown(document)
        warnings = publish_reports(json_text, markdown_text, args.output_json, args.output_markdown)
    except (OSError, RepeatabilityError) as error:
        print(f"s3bench analyze error: {error}", file=sys.stderr)
        return 2
    for warning in warnings:
        print(f"s3bench analyze warning: {warning}", file=sys.stderr)
    print(json.dumps(document, indent=2, sort_keys=True, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
