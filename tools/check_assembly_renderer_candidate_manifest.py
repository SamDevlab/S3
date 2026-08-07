from __future__ import annotations

import json
import re
import sys
from collections.abc import Callable
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.s3_program_check import find_program  # noqa: E402

MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_manifest.json"
)
SUBSET_MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_subset_manifest.json"
)
REQUIRED_KEYS = {
    "candidate_manifest_version",
    "candidate_api",
    "candidate_capabilities",
    "candidate_execution",
    "candidate_symbol_ids",
    "candidate_symbol_ranges",
    "candidate_smoke",
    "component",
    "s3_candidate",
    "program_inventory",
    "python_reference",
    "comparison",
    "blockers",
}
EXPECTED_CANDIDATE_PATH = "examples/self_hosting/assembly_renderer_generic_text.s3"
EXPECTED_SUBSET_MANIFEST = "tests/golden/assembly_renderer_subset_manifest.json"
EXPECTED_DATA_CONTRACT = "tests/golden/assembly_program_data_contract.json"
EXPECTED_ENTRYPOINT = "main"
EXPECTED_STATUS_FUNCTION = "renderer_candidate_status"
EXPECTED_EXECUTION_MODE = "hosted"
EXPECTED_STUB_STATUS = -1
EXPECTED_READY_STATUS = 1
EXPECTED_DIRECTIVE_COUNT_FUNCTION = "renderer_supported_directive_count"
EXPECTED_OPCODE_COUNT_FUNCTION = "renderer_supported_opcode_count"
EXPECTED_DIRECTIVE_FIRST_FUNCTION = "renderer_first_directive_id"
EXPECTED_DIRECTIVE_LAST_FUNCTION = "renderer_last_directive_id"
EXPECTED_OPCODE_FIRST_FUNCTION = "renderer_first_opcode_id"
EXPECTED_OPCODE_LAST_FUNCTION = "renderer_last_opcode_id"
EXPECTED_DIRECTIVE_PREDICATE_FUNCTION = "renderer_supports_directive_id"
EXPECTED_OPCODE_PREDICATE_FUNCTION = "renderer_supports_opcode_id"
EXPECTED_SMOKE_FUNCTION = "renderer_candidate_capability_smoke"
EXPECTED_SMOKE_KINDS = {"hosted_reachability", "hosted_assertion"}
EXPECTED_SMOKE_CALLS = (
    "renderer_supported_directive_count",
    "renderer_supported_opcode_count",
    "renderer_first_directive_id",
    "renderer_last_directive_id",
    "renderer_first_opcode_id",
    "renderer_last_opcode_id",
    "renderer_supports_directive_id",
    "renderer_supports_opcode_id",
    "renderer_directive_end_id",
    "renderer_directive_s3asm_id",
    "renderer_opcode_tadd_id",
    "renderer_opcode_tret_id",
)


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _load_manifest() -> tuple[dict[str, object], str]:
    text = MANIFEST_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("candidate manifest root must be an object")
    return data, text


def _load_subset_manifest() -> dict[str, object]:
    data = json.loads(SUBSET_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("subset manifest root must be an object")
    return data


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


def _function_body(source: str, function_name: str, return_type: str) -> str:
    pattern = (
        rf"(?ms)^fn\s+{re.escape(function_name)}"
        r"\s*\(\)\s*->\s*"
        rf"{re.escape(return_type)}\s*:\n"
        r"(?P<body>.*?)(?=^fn\s+|\Z)"
    )
    match = re.search(pattern, source)
    if match is None:
        raise ValueError(f"candidate stub missing {function_name} function")
    return match.group("body")


def _validate_stub_smoke(source: str) -> None:
    smoke_body = _function_body(source, EXPECTED_SMOKE_FUNCTION, "trit")
    for function_name in EXPECTED_SMOKE_CALLS:
        call_pattern = rf"\b{re.escape(function_name)}\s*\("
        if re.search(call_pattern, smoke_body) is None:
            raise ValueError(
                f"candidate smoke must call {function_name}"
            )


def _validate_stub_capability(
    source: str,
    function_name: str,
    expected_return: int,
    label: str,
) -> None:
    pattern = (
        rf"(?ms)^fn\s+{re.escape(function_name)}"
        r"\s*\(\)\s*->\s*tryte\s*:\s*"
        rf"(?:#.*\n\s*)*return\s+{expected_return}\b"
    )
    if re.search(pattern, source) is None:
        raise ValueError(
            f"candidate stub missing {label} capability return {expected_return}"
        )


def _validate_stub_function(
    source: str,
    function_name: str,
    parameter_text: str,
    return_type: str,
) -> None:
    pattern = (
        rf"(?m)^fn\s+{re.escape(function_name)}"
        r"\s*\(\s*"
        rf"{re.escape(parameter_text)}"
        r"\s*\)\s*->\s*"
        rf"{re.escape(return_type)}\s*:"
    )
    if re.search(pattern, source) is None:
        raise ValueError(f"candidate stub missing {function_name} function")


def _directive_symbol_function_name(symbol: str) -> str:
    name = symbol[1:] if symbol.startswith(".") else symbol
    return f"renderer_directive_{name.replace('.', '_')}_id"


def _opcode_symbol_function_name(symbol: str) -> str:
    return f"renderer_opcode_{symbol.lower()}_id"


def _validate_symbol_ids(
    data: dict[str, object],
    key: str,
    expected_symbols: list[str],
    expected_count: int,
    function_name_for_symbol: Callable[[str], str],
    candidate_source: str,
) -> None:
    if len(set(expected_symbols)) != len(expected_symbols):
        raise ValueError(f"subset manifest {key} must not contain duplicates")

    symbols = _object(data, key)
    if len(symbols) != expected_count:
        raise ValueError(
            f"candidate {key} symbol ID count must match candidate capabilities"
        )

    actual_symbol_set = set(symbols)
    expected_symbol_set = set(expected_symbols)
    if actual_symbol_set != expected_symbol_set:
        missing = [symbol for symbol in expected_symbols if symbol not in symbols]
        extra = sorted(actual_symbol_set - expected_symbol_set)
        details: list[str] = []
        if missing:
            details.append(f"missing: {', '.join(missing)}")
        if extra:
            details.append(f"extra: {', '.join(extra)}")
        rendered = "; ".join(details)
        raise ValueError(
            f"candidate {key} symbol IDs must match subset manifest ({rendered})"
        )

    for expected_id, symbol in enumerate(expected_symbols):
        entry = _object(symbols, symbol)
        expected_function_name = function_name_for_symbol(symbol)
        function_name = _string(entry, "function")
        if function_name != expected_function_name:
            raise ValueError(
                f"candidate {key} {symbol} function must be "
                f"{expected_function_name}"
            )

        symbol_id = _integer(entry, "id")
        if symbol_id != expected_id:
            raise ValueError(
                f"candidate {key} {symbol} ID must be {expected_id}"
            )

        _validate_stub_capability(
            candidate_source,
            function_name,
            expected_id,
            f"{key} {symbol} ID",
        )


def _validate_symbol_ranges(
    data: dict[str, object],
    directive_count: int,
    opcode_count: int,
    candidate_source: str,
) -> None:
    ranges = _object(data, "candidate_symbol_ranges")
    directive_ranges = _object(ranges, "directives")
    opcode_ranges = _object(ranges, "opcodes")
    expected_ranges = (
        (
            directive_ranges,
            EXPECTED_DIRECTIVE_FIRST_FUNCTION,
            0,
            EXPECTED_DIRECTIVE_LAST_FUNCTION,
            directive_count - 1,
            "directive",
        ),
        (
            opcode_ranges,
            EXPECTED_OPCODE_FIRST_FUNCTION,
            0,
            EXPECTED_OPCODE_LAST_FUNCTION,
            opcode_count - 1,
            "opcode",
        ),
    )

    for (
        range_data,
        first_function,
        first_id,
        last_function,
        last_id,
        label,
    ) in expected_ranges:
        if _string(range_data, "first_function") != first_function:
            raise ValueError(f"candidate {label} first range function mismatch")
        if _integer(range_data, "first_id") != first_id:
            raise ValueError(f"candidate {label} first ID must be {first_id}")
        if _string(range_data, "last_function") != last_function:
            raise ValueError(f"candidate {label} last range function mismatch")
        if _integer(range_data, "last_id") != last_id:
            raise ValueError(f"candidate {label} last ID must be {last_id}")

        _validate_stub_capability(
            candidate_source,
            first_function,
            first_id,
            f"{label} first ID range",
        )
        _validate_stub_capability(
            candidate_source,
            last_function,
            last_id,
            f"{label} last ID range",
        )


def _validate_symbol_predicates(
    data: dict[str, object],
    candidate_source: str,
) -> None:
    value = data.get("candidate_symbol_predicates")
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError("candidate manifest candidate_symbol_predicates must be an object")

    directive_function = _string(value, "directive_function")
    if directive_function != EXPECTED_DIRECTIVE_PREDICATE_FUNCTION:
        raise ValueError(
            "candidate directive support predicate must be "
            f"{EXPECTED_DIRECTIVE_PREDICATE_FUNCTION}"
        )
    opcode_function = _string(value, "opcode_function")
    if opcode_function != EXPECTED_OPCODE_PREDICATE_FUNCTION:
        raise ValueError(
            "candidate opcode support predicate must be "
            f"{EXPECTED_OPCODE_PREDICATE_FUNCTION}"
        )
    if _integer(value, "supported_return") != 1:
        raise ValueError("candidate support predicate supported_return must be 1")
    if _integer(value, "unsupported_return") != EXPECTED_STUB_STATUS:
        raise ValueError("candidate support predicate unsupported_return must be -1")

    _validate_stub_function(candidate_source, directive_function, "id: tryte", "trit")
    _validate_stub_function(candidate_source, opcode_function, "id: tryte", "trit")


def _required_string_array(data: dict[str, object], key: str) -> list[str]:
    value = data.get(key)
    if not isinstance(value, list) or not all(
        isinstance(item, str) for item in value
    ):
        raise ValueError(f"subset manifest {key} must be a string array")
    return value


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
    candidate_capabilities = _object(data, "candidate_capabilities")
    candidate_smoke = _object(data, "candidate_smoke")
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

    directive_count_function = _string(
        candidate_capabilities, "directive_count_function"
    )
    if directive_count_function != EXPECTED_DIRECTIVE_COUNT_FUNCTION:
        raise ValueError(
            "candidate directive count function must be "
            f"{EXPECTED_DIRECTIVE_COUNT_FUNCTION}"
        )
    opcode_count_function = _string(candidate_capabilities, "opcode_count_function")
    if opcode_count_function != EXPECTED_OPCODE_COUNT_FUNCTION:
        raise ValueError(
            "candidate opcode count function must be "
            f"{EXPECTED_OPCODE_COUNT_FUNCTION}"
        )

    subset_data = _load_subset_manifest()
    directives = _required_string_array(subset_data, "directives")
    opcodes = _required_string_array(subset_data, "opcodes")
    directive_count = len(directives)
    opcode_count = len(opcodes)
    if _integer(candidate_capabilities, "expected_directive_count") != directive_count:
        raise ValueError("candidate directive count must match subset manifest")
    if _integer(candidate_capabilities, "expected_opcode_count") != opcode_count:
        raise ValueError("candidate opcode count must match subset manifest")

    smoke_function = _string(candidate_smoke, "function")
    if smoke_function != EXPECTED_SMOKE_FUNCTION:
        raise ValueError(
            f"candidate smoke function must be {EXPECTED_SMOKE_FUNCTION}"
        )
    if _integer(candidate_smoke, "expected_return") != EXPECTED_READY_STATUS:
        raise ValueError("candidate smoke expected_return must be 1")
    smoke_kind = _string(candidate_smoke, "kind")
    if smoke_kind not in EXPECTED_SMOKE_KINDS:
        raise ValueError(
            "candidate smoke kind must be hosted_reachability or "
            "hosted_assertion"
        )

    candidate_execution = _object(data, "candidate_execution")
    if _string(candidate_execution, "mode") != EXPECTED_EXECUTION_MODE:
        raise ValueError("candidate execution mode must be hosted")
    if _string(candidate_execution, "entrypoint") != EXPECTED_ENTRYPOINT:
        raise ValueError(
            f"candidate execution entrypoint must be {EXPECTED_ENTRYPOINT}"
        )
    if _integer(candidate_execution, "expected_status") != EXPECTED_READY_STATUS:
        raise ValueError("candidate execution expected_status must be 1")
    if _string(candidate_execution, "meaning") != "implemented":
        raise ValueError("candidate execution meaning must be implemented")

    s3_candidate = _object(data, "s3_candidate")
    candidate_path = _string(s3_candidate, "path")
    if candidate_path != EXPECTED_CANDIDATE_PATH:
        raise ValueError(f"candidate path must be {EXPECTED_CANDIDATE_PATH}")
    if _string(s3_candidate, "api_status") != "ready":
        raise ValueError("candidate api_status must be ready")
    if _string(s3_candidate, "status") != "ready":
        raise ValueError("candidate status must be ready")
    if _string(s3_candidate, "expected") != "compiles":
        raise ValueError("candidate expected must be compiles")
    if s3_candidate.get("implements_renderer") is not True:
        raise ValueError("candidate implements_renderer must be true")
    _validate_repo_file(candidate_path, "candidate path")
    _validate_stub_api(candidate_path)
    candidate_source = (REPO_ROOT / candidate_path).read_text(encoding="utf-8")
    _validate_stub_capability(
        candidate_source,
        directive_count_function,
        directive_count,
        "directive count",
    )
    _validate_stub_capability(
        candidate_source,
        opcode_count_function,
        opcode_count,
        "opcode count",
    )
    _validate_symbol_ranges(
        data,
        directive_count,
        opcode_count,
        candidate_source,
    )
    _validate_symbol_predicates(data, candidate_source)
    _validate_stub_smoke(candidate_source)
    candidate_symbol_ids = _object(data, "candidate_symbol_ids")
    _validate_symbol_ids(
        candidate_symbol_ids,
        "directives",
        directives,
        directive_count,
        _directive_symbol_function_name,
        candidate_source,
    )
    _validate_symbol_ids(
        candidate_symbol_ids,
        "opcodes",
        opcodes,
        opcode_count,
        _opcode_symbol_function_name,
        candidate_source,
    )

    program_inventory = _object(data, "program_inventory")
    inventory_path = _string(program_inventory, "path")
    if inventory_path != EXPECTED_CANDIDATE_PATH:
        raise ValueError(f"program inventory path must be {EXPECTED_CANDIDATE_PATH}")
    if inventory_path != candidate_path:
        raise ValueError("program inventory path must match candidate path")
    if _integer(program_inventory, "hosted_expected_return") != EXPECTED_READY_STATUS:
        raise ValueError("program inventory hosted_expected_return must be 1")
    if not _boolean(program_inventory, "covered_by_s3_program_check"):
        raise ValueError("program inventory must be covered by s3_program_check")

    inventory_program = find_program(inventory_path)
    if inventory_program is None:
        raise ValueError("s3_program_check inventory missing candidate stub")
    if inventory_program.hosted_expected_return != EXPECTED_READY_STATUS:
        raise ValueError("s3_program_check hosted expected return must be 1")

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
    if _string(comparison, "status") != "passed":
        raise ValueError("comparison status must be passed")


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
