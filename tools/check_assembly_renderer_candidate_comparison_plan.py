from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_comparison_plan.json"
)
FIXTURE_EXPECTATIONS = (
    "tests/golden/assembly_renderer_candidate_fixture_expectations.json"
)
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


def _relative_repo_file(path_text: str, label: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    resolved = REPO_ROOT / path
    if not resolved.is_file():
        raise ValueError(f"{label} missing: {path_text}")
    return resolved


def _read_json(path: Path, label: str) -> tuple[dict[str, object], str]:
    text = path.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object")
    return data, text


def _fixture_rows(data: dict[str, object]) -> list[dict[str, object]]:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("comparison plan fixtures must be a non-empty array")
    parsed: list[dict[str, object]] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"comparison fixture {index} must be an object")
        parsed.append(item)
    return parsed


def _expectation_rows(data: dict[str, object]) -> list[dict[str, object]]:
    expectations = data.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        raise ValueError("fixture expectations must be a non-empty array")
    parsed: list[dict[str, object]] = []
    for index, item in enumerate(expectations):
        if not isinstance(item, dict):
            raise ValueError(f"fixture expectation {index} must be an object")
        parsed.append(item)
    return parsed


def _expected_assembly_sha256(path_text: str) -> str:
    path = _relative_repo_file(path_text, "expected assembly")
    text = path.read_bytes().decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        raise ValueError(f"expected assembly missing final newline: {path_text}")
    if WINDOWS_ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError(f"expected assembly contains Windows absolute path: {path_text}")
    if TIMESTAMP_PATTERN.search(text):
        raise ValueError(f"expected assembly contains timestamp-like text: {path_text}")
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _validate_comparison(data: dict[str, object]) -> None:
    comparison = _object(data, "comparison")
    if _string(comparison, "expected_output_source") != "assembly_golden":
        raise ValueError("comparison expected output source must be assembly_golden")
    if _string(comparison, "actual_output_source") != "s3_renderer_candidate":
        raise ValueError("comparison actual output source must be s3_renderer_candidate")
    if _string(comparison, "actual_output_status") != "not_implemented":
        raise ValueError("comparison actual output status must be not_implemented")
    if _string(comparison, "result") != "blocked":
        raise ValueError("comparison result must be blocked")


def _validate_fixtures(
    data: dict[str, object],
    expectation_data: dict[str, object],
) -> None:
    fixtures = _fixture_rows(data)
    expectations = _expectation_rows(expectation_data)
    if len(fixtures) != len(expectations):
        raise ValueError("comparison fixtures must match expectation count")

    seen: set[str] = set()
    for index, expectation in enumerate(expectations):
        item = fixtures[index]
        disallowed = DISALLOWED_ACTUAL_OUTPUT_FIELDS.intersection(item)
        if disallowed:
            first = sorted(disallowed)[0]
            raise ValueError(f"comparison fixture must not contain {first}")

        expected_name = _string(expectation, "name")
        name = _string(item, "name")
        if name in seen:
            raise ValueError(f"comparison fixture repeated: {name}")
        seen.add(name)
        if name != expected_name:
            raise ValueError("comparison fixtures must follow expectation order")
        if name == EXCLUDED_STUB:
            raise ValueError("assembly_renderer_stub must not be compared")

        source = _string(item, "source")
        if source != _string(expectation, "source"):
            raise ValueError(f"comparison fixture {name} source mismatch")
        expected_assembly = _string(item, "expected_assembly")
        if expected_assembly != _string(expectation, "expected_assembly"):
            raise ValueError(f"comparison fixture {name} expected assembly mismatch")
        expected_sha256 = _string(item, "expected_sha256")
        if expected_sha256 != _string(expectation, "sha256"):
            raise ValueError(f"comparison fixture {name} expected sha256 mismatch")
        actual_output_status = _string(item, "actual_output_status")
        comparison_status = _string(item, "comparison_status")
        if actual_output_status not in {"available", "not_implemented"}:
            raise ValueError(f"comparison fixture {name} actual output status mismatch")
        if actual_output_status == "available" and comparison_status not in {
            "pending",
            "passed",
        }:
            raise ValueError(f"comparison fixture {name} comparison status mismatch")
        if actual_output_status == "not_implemented" and comparison_status != "blocked":
            raise ValueError(f"comparison fixture {name} comparison status mismatch")
        reason = _string(item, "reason")
        if actual_output_status == "not_implemented" and NOT_IMPLEMENTED_REASON not in reason:
            raise ValueError(f"comparison fixture {name} reason mismatch")
        if actual_output_status == "available" and not reason:
            raise ValueError(f"comparison fixture {name} reason mismatch")

        _relative_repo_file(source, "comparison fixture source")
        if expected_sha256 != _expected_assembly_sha256(expected_assembly):
            raise ValueError(f"comparison fixture {name} expected sha256 file mismatch")

    if EXCLUDED_STUB in seen:
        raise ValueError("assembly_renderer_stub must not be compared")


def _validate_manifest(data: dict[str, object], text: str) -> None:
    if text != _canonical(data):
        raise ValueError("comparison plan JSON is not canonical")
    if _string(data, "version") != "1.0.0":
        raise ValueError("comparison plan version must be 1.0.0")
    if _string(data, "component") != "assembly_renderer_candidate_comparison_plan":
        raise ValueError("comparison plan component mismatch")
    if _string(data, "status") != "blocked":
        raise ValueError("comparison plan status must be blocked")
    if NOT_IMPLEMENTED_REASON not in _string(data, "reason"):
        raise ValueError("comparison plan reason mismatch")
    fixture_expectations = _string(data, "fixture_expectations")
    if fixture_expectations != FIXTURE_EXPECTATIONS:
        raise ValueError(f"fixture_expectations must be {FIXTURE_EXPECTATIONS}")
    expectations_path = _relative_repo_file(fixture_expectations, "fixture expectations")
    expectation_data, _ = _read_json(expectations_path, "fixture expectations")

    _validate_comparison(data)
    _validate_fixtures(data, expectation_data)


def main() -> int:
    try:
        data, text = _read_json(MANIFEST_PATH, "comparison plan manifest")
        _validate_manifest(data, text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly renderer candidate comparison plan invalid: {error}")
        return 1

    print("assembly renderer candidate comparison plan: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
