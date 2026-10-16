from __future__ import annotations

import argparse
import json
import sys

from .lab import discover_applications, run_application


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="s3-application-lab")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("list", help="discover and summarize application manifests")
    run = commands.add_parser("run", help="validate, compile, and execute applications")
    run.add_argument("name", nargs="?", help="application name (default: all)")
    run.add_argument(
        "--mode",
        choices=("compile-only", "hosted", "native", "ffi"),
        default="hosted",
    )
    args = parser.parse_args(argv)

    if args.command == "list":
        print(json.dumps(discover_applications(), indent=2, sort_keys=True))
        return 0

    applications = discover_applications()
    selected = [item for item in applications if args.name is None or item["name"] == args.name]
    if args.name is not None and not selected:
        parser.error(f"unknown application: {args.name}")
    reports = [run_application(item["path"], mode=args.mode) for item in selected]
    print(json.dumps(reports, indent=2, sort_keys=True))
    return 0 if all(item["status"] == "PASS" for item in reports) else 1


if __name__ == "__main__":
    sys.exit(main())
