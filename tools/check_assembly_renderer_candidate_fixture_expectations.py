from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_fixture_expectations.json"
)
SOURCE_MANIFEST = "tests/golden/assembly_renderer_candidate_fixtures.json"
EXCLUDED_STUB = "assembly_renderer_stub"
WINDOWS_ABSOLUTE_PATH_PATTERN = re.compile(r"[A-Za-z]:\\")
TIMESTAMP_PATTERN = re.compile(r"\b20[0-9]{2}-[0-9]{2}-[0-9]{2}\b")


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _object(data: dict[str, object], key: str) -> dict[str, object]:
    value = data.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"{key} must be an object")
    return value


def _integer(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
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
        raise ValueError("source fixture manifest fixtures must be a non-empty array")
    parsed: list[dict[str, object]] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"source fixture {index} must be an object")
        parsed.append(item)
    return parsed


def _expected_assembly_metadata(path_text: str) -> tuple[str, int, int]:
    path = _relative_repo_file(path_text, "expected assembly")
    text = path.read_bytes().decode("utf-8")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    if not text.endswith("\n"):
        raise ValueError(f"expected assembly missing final newline: {path_text}")
    if WINDOWS_ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError(f"expected assembly contains Windows absolute path: {path_text}")
    if TIMESTAMP_PATTERN.search(text):
        raise ValueError(f"expected assembly contains timestamp-like text: {path_text}")
    data = text.encode("utf-8")
    return hashlib.sha256(data).hexdigest(), len(data), len(text.splitlines())


def _validate_expectations(
    data: dict[str, object],
    source_manifest_data: dict[str, object],
) -> None:
    expectations = data.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        raise ValueError("expectations must be a non-empty array")
    fixtures = _fixture_rows(source_manifest_data)
    if len(expectations) != len(fixtures):
        raise ValueError("expectations must match source fixture count")

    seen: set[str] = set()
    for index, fixture in enumerate(fixtures):
        item = expectations[index]
        if not isinstance(item, dict):
            raise ValueError(f"expectation {index} must be an object")

        fixture_name = _string(fixture, "name")
        name = _string(item, "name")
        if name in seen:
            raise ValueError(f"expectation name repeated: {name}")
        seen.add(name)
        if name != fixture_name:
            raise ValueError("expectations must follow the source fixture order")
        if name == EXCLUDED_STUB:
            raise ValueError("assembly_renderer_stub must not be expected")

        source = _string(item, "source")
        if source != _string(fixture, "source"):
            raise ValueError(f"expectation {name} source mismatch")
        expected_assembly = _string(item, "expected_assembly")
        if expected_assembly != _string(fixture, "assembly_golden"):
            raise ValueError(f"expectation {name} expected assembly mismatch")
        if _string(item, "status") != "expected":
            raise ValueError(f"expectation {name} status must be expected")

        _relative_repo_file(source, "expectation source")
        actual_sha256, actual_byte_count, actual_line_count = (
            _expected_assembly_metadata(expected_assembly)
        )
        if _string(item, "sha256") != actual_sha256:
            raise ValueError(f"expectation {name} sha256 mismatch")
        if _integer(item, "byte_count") != actual_byte_count:
            raise ValueError(f"expectation {name} byte_count mismatch")
        if _integer(item, "line_count") != actual_line_count:
            raise ValueError(f"expectation {name} line_count mismatch")

    if EXCLUDED_STUB in seen:
        raise ValueError("assembly_renderer_stub must not be expected")


def _validate_manifest(data: dict[str, object], text: str) -> None:
    if text != _canonical(data):
        raise ValueError("fixture expectations JSON is not canonical")
    if _string(data, "version") != "1.0.0":
        raise ValueError("fixture expectations version must be 1.0.0")
    if _string(data, "component") != "assembly_renderer_candidate_fixture_expectations":
        raise ValueError("fixture expectations component mismatch")
    if _string(data, "status") != "reference_only":
        raise ValueError("fixture expectations status must be reference_only")

    comparison = _object(data, "comparison")
    if _string(comparison, "status") != "blocked":
        raise ValueError("fixture expectations comparison status must be blocked")
    if "S3 renderer is not implemented" not in _string(comparison, "reason"):
        raise ValueError("fixture expectations comparison reason mismatch")

    source_manifest = _string(data, "source_manifest")
    if source_manifest != SOURCE_MANIFEST:
        raise ValueError(f"source_manifest must be {SOURCE_MANIFEST}")
    source_manifest_path = _relative_repo_file(source_manifest, "source manifest")
    source_manifest_data, _ = _read_json(source_manifest_path, "source manifest")
    _validate_expectations(data, source_manifest_data)


def main() -> int:
    try:
        data, text = _read_json(MANIFEST_PATH, "fixture expectations manifest")
        _validate_manifest(data, text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly renderer candidate fixture expectations invalid: {error}")
        return 1

    print("assembly renderer candidate fixture expectations: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
