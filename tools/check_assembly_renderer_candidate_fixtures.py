from __future__ import annotations

import json
import re
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_fixtures.json"
)
EXPECTED_FIXTURES = (
    (
        "first",
        "examples/first.s3",
        "tests/golden/inspect/first.assembly.txt",
    ),
    (
        "simple_call",
        "examples/simple_call.s3",
        "tests/golden/inspect/simple_call.assembly.txt",
    ),
    (
        "sign",
        "examples/sign.s3",
        "tests/golden/inspect/sign.assembly.txt",
    ),
)
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


def _read_manifest() -> tuple[dict[str, object], str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("fixture manifest root must be an object")
    return data, text


def _validate_assembly_golden(path_text: str) -> None:
    path = _relative_repo_file(path_text, "assembly golden")
    text = path.read_text(encoding="utf-8")
    if not text.endswith("\n"):
        raise ValueError(f"assembly golden missing final newline: {path_text}")
    if WINDOWS_ABSOLUTE_PATH_PATTERN.search(text):
        raise ValueError(f"assembly golden contains Windows absolute path: {path_text}")
    if TIMESTAMP_PATTERN.search(text):
        raise ValueError(f"assembly golden contains timestamp-like text: {path_text}")


def _validate_fixtures(data: dict[str, object]) -> None:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("fixtures must be a non-empty array")
    if len(fixtures) != len(EXPECTED_FIXTURES):
        raise ValueError("fixtures must contain the expected reference fixtures")

    seen: set[str] = set()
    for index, expected in enumerate(EXPECTED_FIXTURES):
        item = fixtures[index]
        if not isinstance(item, dict):
            raise ValueError(f"fixture {index} must be an object")
        expected_name, expected_source, expected_golden = expected
        name = _string(item, "name")
        if name in seen:
            raise ValueError(f"fixture name repeated: {name}")
        seen.add(name)
        if name != expected_name:
            raise ValueError("fixtures must follow the canonical order")
        source = _string(item, "source")
        if source != expected_source:
            raise ValueError(f"fixture {name} source mismatch")
        assembly_golden = _string(item, "assembly_golden")
        if assembly_golden != expected_golden:
            raise ValueError(f"fixture {name} assembly golden mismatch")
        if _string(item, "status") != "reference":
            raise ValueError(f"fixture {name} status must be reference")

        _relative_repo_file(source, "fixture source")
        _validate_assembly_golden(assembly_golden)

    if EXCLUDED_STUB in seen:
        raise ValueError("assembly_renderer_stub must not be a renderer target fixture")


def _validate_excluded(data: dict[str, object]) -> None:
    excluded = data.get("excluded")
    if not isinstance(excluded, list):
        raise ValueError("excluded must be an array")
    for item in excluded:
        if not isinstance(item, dict):
            raise ValueError("excluded item must be an object")
        if _string(item, "name") == EXCLUDED_STUB:
            if not _string(item, "reason"):
                raise ValueError("assembly_renderer_stub exclusion reason must be set")
            return
    raise ValueError("assembly_renderer_stub must be listed in excluded")


def _validate_manifest(data: dict[str, object], text: str) -> None:
    if text != _canonical(data):
        raise ValueError("fixture manifest JSON is not canonical")
    if _string(data, "version") != "1.0.0":
        raise ValueError("fixture manifest version must be 1.0.0")
    if _string(data, "component") != "assembly_renderer_candidate_fixtures":
        raise ValueError("fixture manifest component mismatch")
    if _string(data, "status") != "reference_only":
        raise ValueError("fixture manifest status must be reference_only")

    comparison = _object(data, "comparison")
    if _string(comparison, "status") != "blocked":
        raise ValueError("fixture manifest comparison status must be blocked")
    if "S3 renderer is not implemented" not in _string(comparison, "reason"):
        raise ValueError("fixture manifest comparison reason mismatch")

    _validate_fixtures(data)
    _validate_excluded(data)


def main() -> int:
    try:
        data, text = _read_manifest()
        _validate_manifest(data, text)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"assembly renderer candidate fixtures invalid: {error}")
        return 1

    print("assembly renderer candidate fixtures: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
