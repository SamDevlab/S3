from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "tests" / "golden" / "assembly_program_data_contract.json"
BLOCKED_MESSAGE = (
    "assembly renderer comparison is blocked: S3 renderer is not implemented"
)


BLOCKER_BY_FEATURE = {
    "strings": "string runtime support",
    "records_or_structs": "records/structs or equivalent tagged data",
    "enums_or_tagged_unions": "enums/sum types or safe tags",
    "deterministic_formatting_helpers": "deterministic formatting helpers",
}


def _load_contract() -> dict[str, object]:
    data = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    return data


def _contract_strings(data: dict[str, object], key: str) -> tuple[str, ...]:
    values = data.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, str))


def _blockers(features: tuple[str, ...]) -> tuple[str, ...]:
    blockers: list[str] = []
    for feature in features:
        blocker = BLOCKER_BY_FEATURE.get(feature)
        if blocker is not None:
            blockers.append(blocker)
    return tuple(blockers)


def status() -> int:
    contract = _load_contract()
    fixtures = _contract_strings(contract, "initial_fixtures")
    features = _contract_strings(contract, "required_language_features")

    print("S3 Assembly renderer comparison harness")
    print()
    print("python reference: available")
    print("s3 renderer: not implemented")
    print("string literals: front-end only, runtime not implemented")
    print("status: blocked")
    print()
    print("fixtures:")
    for fixture in fixtures:
        print(f"  {fixture}")
    print()
    print("blockers:")
    for blocker in _blockers(features):
        print(f"  {blocker}")
    return 0


def check() -> int:
    print(BLOCKED_MESSAGE)
    return 1


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare Python and future S3 Assembly renderer output"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return status()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
