from __future__ import annotations

import json
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "tests" / "golden" / "assembly_program_data_contract.json"
sys.path.insert(0, str(REPO_ROOT))

from tools.generate_assembly_renderer_subset_manifest import build_manifest  # noqa: E402


REQUIRED_KEYS = {
    "contract_version",
    "entities",
    "directives",
    "opcodes",
    "required_language_features",
    "initial_fixtures",
}


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _load_contract() -> tuple[dict[str, object], str]:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    return data, text


def _validate_contract(data: dict[str, object], text: str) -> None:
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        rendered = ", ".join(sorted(missing))
        raise ValueError(f"contract missing required key(s): {rendered}")

    if text != _canonical(data):
        raise ValueError("contract JSON is not canonical")

    manifest = build_manifest()
    manifest_opcodes = set(manifest["opcodes"])
    manifest_directives = set(manifest["directives"])
    manifest_fixtures = {
        item["example"]
        for item in manifest["fixtures"]
        if isinstance(item, dict) and isinstance(item.get("example"), str)
    }

    opcodes = data["opcodes"]
    directives = data["directives"]
    initial_fixtures = data["initial_fixtures"]

    if not isinstance(opcodes, dict):
        raise ValueError("contract opcodes must be an object")
    if not isinstance(directives, dict):
        raise ValueError("contract directives must be an object")
    if not isinstance(initial_fixtures, list):
        raise ValueError("contract initial_fixtures must be an array")

    missing_opcodes = manifest_opcodes - opcodes.keys()
    if missing_opcodes:
        rendered = ", ".join(sorted(missing_opcodes))
        raise ValueError(f"contract missing opcode(s): {rendered}")

    missing_directives = manifest_directives - directives.keys()
    if missing_directives:
        rendered = ", ".join(sorted(missing_directives))
        raise ValueError(f"contract missing directive(s): {rendered}")

    missing_fixtures = manifest_fixtures - set(initial_fixtures)
    if missing_fixtures:
        rendered = ", ".join(sorted(missing_fixtures))
        raise ValueError(f"contract missing fixture(s): {rendered}")


def main() -> int:
    try:
        data, text = _load_contract()
        _validate_contract(data, text)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly program data contract invalid: {error}")
        return 1

    print("assembly program data contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
