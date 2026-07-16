from __future__ import annotations

import json
import re
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.s3_program_check import find_program  # noqa: E402

MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_manifest.json"
)
REQUIRED_KEYS = {
    "candidate_manifest_version",
    "candidate_api",
    "candidate_execution",
    "component",
    "s3_candidate",
    "program_inventory",
    "python_reference",
    "comparison",
    "blockers",
}
EXPECTED_CANDIDATE_PATH = "examples/self_hosting/assembly_renderer_stub.s3"
EXPECTED_SUBSET_MANIFEST = "tests/golden/assembly_renderer_subset_manifest.json"
EXPECTED_DATA_CONTRACT = "tests/golden/assembly_program_data_contract.json"
EXPECTED_ENTRYPOINT = "main"
EXPECTED_STATUS_FUNCTION = "renderer_candidate_status"
EXPECTED_EXECUTION_MODE = "hosted"
EXPECTED_STUB_STATUS = -1


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _load_manifest() -> tuple[dict[str, object], str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("candidate manifest root must be an object")
    return data, text


def _object(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"candidate manifest {key} must be an object")
    return value


def _string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"candidate manifest {key} must be a string")
    return value


def _integer(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"candidate manifest {key} must be an integer")
    return value


def _boolean(data: dict[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"candidate manifest {key} must be a boolean")
    return value


def _validate_repo_file(path_text: str, label: str) -> None:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    if not (REPO_ROOT / path).is_file():
        raise ValueError(f"{label} missing: {path_text}")


def _validate_stub_api(path_text: str) -> None:
    source = (REPO_ROOT / path_text).read_text(encoding="utf-8")
    status_pattern = (
        rf"(?m)^fn\s+{re.escape(EXPECTED_STATUS_FUNCTION)}"
        r"\s*\(\)\s*->\s*trit\s*:"
    )
    if re.search(status_pattern, source) is None:
        raise ValueError("candidate stub missing status function")
    if re.search(r"(?m)^fn\s+main\s*\(\)\s*->\s*trit\s*:", source) is None:
        raise ValueError("candidate stub missing main entrypoint")


def _validate_manifest(data: dict[str, object], text: str) -> None:
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        rendered = ", ".join(sorted(missing))
        raise ValueError(f"candidate manifest missing required key(s): {rendered}")

    if text != _canonical(data):
        raise ValueError("candidate manifest JSON is not canonical")

    if data["component"] != "assembly_renderer_subset":
        raise ValueError("candidate manifest component must be assembly_renderer_subset")

    blockers = data["blockers"]
    if not isinstance(blockers, list) or not all(
        isinstance(item, str) and item for item in blockers
    ):
        raise ValueError("candidate manifest blockers must be a string array")

    candidate_api = _object(data, "candidate_api")
    if _string(candidate_api, "entrypoint") != EXPECTED_ENTRYPOINT:
        raise ValueError(f"candidate API entrypoint must be {EXPECTED_ENTRYPOINT}")
    if _string(candidate_api, "status_function") != EXPECTED_STATUS_FUNCTION:
        raise ValueError(
            f"candidate API status_function must be {EXPECTED_STATUS_FUNCTION}"
        )
    status_return = _object(candidate_api, "status_return")
    if status_return.get("stub") != EXPECTED_STUB_STATUS:
        raise ValueError("candidate API stub return must be -1")
    if status_return.get("ready") != 1:
        raise ValueError("candidate API ready return must be 1")

    candidate_execution = _object(data, "candidate_execution")
    if _string(candidate_execution, "mode") != EXPECTED_EXECUTION_MODE:
        raise ValueError("candidate execution mode must be hosted")
    if _string(candidate_execution, "entrypoint") != EXPECTED_ENTRYPOINT:
        raise ValueError(
            f"candidate execution entrypoint must be {EXPECTED_ENTRYPOINT}"
        )
    if _integer(candidate_execution, "expected_status") != EXPECTED_STUB_STATUS:
        raise ValueError("candidate execution expected_status must be -1")
    if _string(candidate_execution, "meaning") != "stub":
        raise ValueError("candidate execution meaning must be stub")

    s3_candidate = _object(data, "s3_candidate")
    candidate_path = _string(s3_candidate, "path")
    if candidate_path != EXPECTED_CANDIDATE_PATH:
        raise ValueError(f"candidate path must be {EXPECTED_CANDIDATE_PATH}")
    if _string(s3_candidate, "api_status") != "stub":
        raise ValueError("candidate api_status must be stub")
    if _string(s3_candidate, "status") != "stub":
        raise ValueError("candidate status must be stub")
    if _string(s3_candidate, "expected") != "compiles":
        raise ValueError("candidate expected must be compiles")
    if s3_candidate.get("implements_renderer") is not False:
        raise ValueError("candidate implements_renderer must be false")
    _validate_repo_file(candidate_path, "candidate path")
    _validate_stub_api(candidate_path)

    program_inventory = _object(data, "program_inventory")
    inventory_path = _string(program_inventory, "path")
    if inventory_path != EXPECTED_CANDIDATE_PATH:
        raise ValueError(f"program inventory path must be {EXPECTED_CANDIDATE_PATH}")
    if inventory_path != candidate_path:
        raise ValueError("program inventory path must match candidate path")
    if _integer(program_inventory, "hosted_expected_return") != EXPECTED_STUB_STATUS:
        raise ValueError("program inventory hosted_expected_return must be -1")
    if not _boolean(program_inventory, "covered_by_s3_program_check"):
        raise ValueError("program inventory must be covered by s3_program_check")

    inventory_program = find_program(inventory_path)
    if inventory_program is None:
        raise ValueError("s3_program_check inventory missing candidate stub")
    if inventory_program.hosted_expected_return != EXPECTED_STUB_STATUS:
        raise ValueError("s3_program_check hosted expected return must be -1")

    python_reference = _object(data, "python_reference")
    if _string(python_reference, "status") != "available":
        raise ValueError("python reference status must be available")
    subset_manifest = _string(python_reference, "subset_manifest")
    if subset_manifest != EXPECTED_SUBSET_MANIFEST:
        raise ValueError(f"subset manifest must be {EXPECTED_SUBSET_MANIFEST}")
    _validate_repo_file(subset_manifest, "subset manifest")
    data_contract = _string(python_reference, "data_contract")
    if data_contract != EXPECTED_DATA_CONTRACT:
        raise ValueError(f"data contract must be {EXPECTED_DATA_CONTRACT}")
    _validate_repo_file(data_contract, "data contract")

    comparison = _object(data, "comparison")
    if _string(comparison, "status") != "blocked":
        raise ValueError("comparison status must be blocked")


def main() -> int:
    try:
        data, text = _load_manifest()
        _validate_manifest(data, text)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly renderer candidate manifest invalid: {error}")
        return 1

    print("assembly renderer candidate manifest: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
