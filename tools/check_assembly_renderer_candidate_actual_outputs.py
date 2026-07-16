from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual_outputs.json"
)
COMPARISON_PLAN = "tests/golden/assembly_renderer_candidate_comparison_plan.json"
ACTUAL_OUTPUT_ROOT = "tests/golden/assembly_renderer_candidate_actual"
EXCLUDED_STUB = "assembly_renderer_stub"
NOT_IMPLEMENTED_REASON = "S3 renderer is not implemented"
DISALLOWED_ACTUAL_OUTPUT_FIELDS = {
    "actual_assembly",
    "actual_file",
    "actual_output",
    "actual_output_file",
    "actual_output_path",
    "actual_path",
}
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"[A-Za-z]:\\")
TIMESTAMP_PATTERN = re.compile(r"\b20[0-9]{2}-[0-9]{2}-[0-9]{2}\b")


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _object(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _string(data: dict[str, object], key: str) -> str:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a string")
    return value


def _boolean(data: dict[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _integer(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{key} must be an integer")
    return value


def _relative_repo_file(path_text: str, label: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    resolved = REPO_ROOT / path
    if not resolved.is_file():
        raise ValueError(f"{label} missing: {path_text}")
    return resolved


def _relative_repo_path(path_text: str, label: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    if WINDOWS_ABSOLUTE_PATH_PATTERN.search(path_text):
        raise ValueError(f"{label} must not contain a Windows absolute path")
    if ".." in path.parts:
        raise ValueError(f"{label} must not contain ..")
    return path


def _read_json(path: Path, label: str) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object")
    return data, text


def _comparison_plan_rows(data: dict[str, object]) -> list[dict[str, object]]:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("comparison plan fixtures must be a non-empty array")
    parsed: list[dict[str, object]] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"comparison plan fixture {index} must be an object")
        parsed.append(item)
    return parsed


def _output_rows(data: dict[str, object]) -> list[dict[str, object]]:
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("outputs must be a non-empty array")
    parsed: list[dict[str, object]] = []
    for index, item in enumerate(outputs):
        if not isinstance(item, dict):
            raise ValueError(f"actual output {index} must be an object")
        parsed.append(item)
    return parsed


def _validate_planned_actual_output(path_text: str, root_text: str, name: str) -> None:
    path = _relative_repo_path(path_text, f"actual output {name} planned path")
    root = _relative_repo_path(root_text, "actual output root")
    if path.parts[: len(root.parts)] != root.parts:
        raise ValueError(f"actual output {name} planned path must be under root")
    return None


def _lf_normalized_bytes(path: Path, label: str) -> bytes:
    text = path.read_bytes().decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if WINDOWS_ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError(f"{label} contains Windows absolute path")
    if TIMESTAMP_PATTERN.search(text):
        raise ValueError(f"{label} contains timestamp-like text")
    return text.encode("utf-8")


def _validate_not_implemented_output(
    item: dict[str, object],
    actual_output_root: str,
    name: str,
) -> None:
    if _boolean(item, "actual_output_exists") is not False:
        raise ValueError(f"actual output {name} existence flag must be false")
    if _string(item, "comparison_status") != "blocked":
        raise ValueError(f"actual output {name} comparison status mismatch")
    if NOT_IMPLEMENTED_REASON not in _string(item, "reason"):
        raise ValueError(f"actual output {name} reason mismatch")
    for field in ("actual_sha256", "actual_byte_count", "actual_line_count"):
        if field in item:
            raise ValueError(f"actual output {name} must not contain {field}")

    planned_actual_output = _string(item, "planned_actual_output")
    _validate_planned_actual_output(planned_actual_output, actual_output_root, name)
    planned_path = REPO_ROOT / _relative_repo_path(
        planned_actual_output,
        f"actual output {name} planned path",
    )
    if planned_path.exists():
        raise ValueError(f"actual output {name} already exists: {planned_actual_output}")


def _validate_available_output(
    item: dict[str, object],
    actual_output_root: str,
    name: str,
    expected_assembly: str,
) -> None:
    if _boolean(item, "actual_output_exists") is not True:
        raise ValueError(f"actual output {name} existence flag must be true")
    if _string(item, "comparison_status") != "pending":
        raise ValueError(f"actual output {name} comparison status mismatch")

    planned_actual_output = _string(item, "planned_actual_output")
    _validate_planned_actual_output(planned_actual_output, actual_output_root, name)
    planned_path = REPO_ROOT / _relative_repo_path(
        planned_actual_output,
        f"actual output {name} planned path",
    )
    if not planned_path.is_file():
        raise ValueError(f"actual output {name} missing: {planned_actual_output}")

    actual_bytes = _lf_normalized_bytes(planned_path, f"actual output {name}")
    expected_bytes = _lf_normalized_bytes(
        REPO_ROOT / expected_assembly,
        f"expected assembly {name}",
    )
    if actual_bytes != expected_bytes:
        raise ValueError(f"actual output {name} does not match expected assembly")

    actual_sha256 = hashlib.sha256(actual_bytes).hexdigest()
    actual_line_count = 0 if actual_bytes == b"" else len(
        actual_bytes.decode("utf-8").splitlines()
    )
    if _string(item, "actual_sha256") != actual_sha256:
        raise ValueError(f"actual output {name} sha256 mismatch")
    if _integer(item, "actual_byte_count") != len(actual_bytes):
        raise ValueError(f"actual output {name} byte count mismatch")
    if _integer(item, "actual_line_count") != actual_line_count:
        raise ValueError(f"actual output {name} line count mismatch")


def _validate_outputs(
    data: dict[str, object],
    comparison_plan_data: dict[str, object],
) -> None:
    outputs = _output_rows(data)
    comparison_fixtures = _comparison_plan_rows(comparison_plan_data)
    if len(outputs) != len(comparison_fixtures):
        raise ValueError("actual outputs must match comparison plan fixture count")

    actual_output_root = _string(data, "actual_output_root")
    seen: set[str] = set()
    for index, comparison_fixture in enumerate(comparison_fixtures):
        item = outputs[index]
        disallowed = DISALLOWED_ACTUAL_OUTPUT_FIELDS.intersection(item)
        if disallowed:
            first = sorted(disallowed)[0]
            raise ValueError(f"actual output must not contain {first}")

        name = _string(item, "name")
        if name in seen:
            raise ValueError(f"actual output repeated: {name}")
        seen.add(name)
        if name == EXCLUDED_STUB:
            raise ValueError("assembly_renderer_stub must not be an actual output")
        if name != _string(comparison_fixture, "name"):
            raise ValueError("actual outputs must follow comparison plan order")

        source = _string(item, "source")
        if source != _string(comparison_fixture, "source"):
            raise ValueError(f"actual output {name} source mismatch")
        expected_assembly = _string(item, "expected_assembly")
        if expected_assembly != _string(comparison_fixture, "expected_assembly"):
            raise ValueError(f"actual output {name} expected assembly mismatch")
        actual_output_status = _string(item, "actual_output_status")
        if actual_output_status != _string(comparison_fixture, "actual_output_status"):
            raise ValueError(f"actual output {name} status mismatch")
        if _string(item, "comparison_status") != _string(
            comparison_fixture,
            "comparison_status",
        ):
            raise ValueError(f"actual output {name} comparison status mismatch")

        _relative_repo_file(source, "actual output source")
        _relative_repo_file(expected_assembly, "actual output expected assembly")
        if actual_output_status == "available":
            _validate_available_output(item, actual_output_root, name, expected_assembly)
        elif actual_output_status == "not_implemented":
            _validate_not_implemented_output(item, actual_output_root, name)
        else:
            raise ValueError(f"actual output {name} status mismatch")

    if EXCLUDED_STUB in seen:
        raise ValueError("assembly_renderer_stub must not be an actual output")


def _validate_manifest(data: dict[str, object], text: str) -> None:
    if text != _canonical(data):
        raise ValueError("actual outputs JSON is not canonical")
    if _string(data, "version") != "1.0.0":
        raise ValueError("actual outputs version must be 1.0.0")
    if _string(data, "component") != "assembly_renderer_candidate_actual_outputs":
        raise ValueError("actual outputs component mismatch")
    if _string(data, "status") not in {"blocked", "partial"}:
        raise ValueError("actual outputs status must be blocked or partial")
    if "S3 renderer is not implemented" not in _string(data, "reason"):
        raise ValueError("actual outputs reason mismatch")

    comparison_plan = _string(data, "comparison_plan")
    if comparison_plan != COMPARISON_PLAN:
        raise ValueError(f"comparison_plan must be {COMPARISON_PLAN}")
    comparison_plan_path = _relative_repo_file(comparison_plan, "comparison plan")

    actual_output_root = _string(data, "actual_output_root")
    if actual_output_root != ACTUAL_OUTPUT_ROOT:
        raise ValueError(f"actual_output_root must be {ACTUAL_OUTPUT_ROOT}")
    _relative_repo_path(actual_output_root, "actual output root")

    comparison_plan_data, _ = _read_json(comparison_plan_path, "comparison plan")
    _validate_outputs(data, comparison_plan_data)


def main() -> int:
    try:
        data, text = _read_json(MANIFEST_PATH, "actual outputs manifest")
        _validate_manifest(data, text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly renderer candidate actual outputs invalid: {error}")
        return 1

    print("assembly renderer candidate actual outputs: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
