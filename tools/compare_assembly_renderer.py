from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from tools.s3_program_check import find_program, run_hosted_check  # noqa: E402

MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_subset_manifest.json"
)
CANDIDATE_MANIFEST_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_manifest.json"
)
CONTRACT_PATH = REPO_ROOT / "tests" / "golden" / "assembly_program_data_contract.json"
BLOCKED_MESSAGE = (
    "assembly renderer comparison is blocked: S3 renderer is not implemented"
)
EXPECTED_CANDIDATE_PATH = "examples/self_hosting/assembly_renderer_stub.s3"
EXPECTED_ENTRYPOINT = "main"
EXPECTED_STATUS_FUNCTION = "renderer_candidate_status"
EXPECTED_EXECUTION_MODE = "hosted"
EXPECTED_STUB_STATUS = -1
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


BLOCKER_BY_FEATURE = {
    "strings": "string runtime support",
    "records_or_structs": "records/structs or equivalent tagged data",
    "enums_or_tagged_unions": "enums/sum types or safe tags",
    "deterministic_formatting_helpers": "deterministic formatting helpers",
}


@dataclass(frozen=True, slots=True)
class ReferenceFixture:
    example: str
    golden: str


@dataclass(frozen=True, slots=True)
class CandidateSymbol:
    symbol_id: int
    symbol: str
    function: str


@dataclass(frozen=True, slots=True)
class CandidateStatus:
    path: str
    status: str
    entrypoint: str
    status_function: str
    directive_count_function: str
    opcode_count_function: str
    smoke_function: str
    directive_id_functions: int
    opcode_id_functions: int
    directive_symbols: tuple[CandidateSymbol, ...]
    opcode_symbols: tuple[CandidateSymbol, ...]
    directive_first_id: int
    directive_last_id: int
    opcode_first_id: int
    opcode_last_id: int
    directive_support_predicate: str | None
    opcode_support_predicate: str | None
    execution_mode: str
    expected_status: int
    execution_meaning: str
    covered_by_s3_program_check: bool
    implements_renderer: bool
    comparison_status: str


def _repo_path(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def _load_json(path: Path, label: str) -> dict[str, object]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise ValueError(f"{label} missing: {_repo_path(path)}") from error

    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise ValueError(f"{label} JSON invalid: {_repo_path(path)}") from error

    if not isinstance(data, dict):
        raise ValueError(f"{label} root must be an object")
    return data


def _load_contract() -> dict[str, object]:
    return _load_json(CONTRACT_PATH, "contract")


def _load_manifest() -> dict[str, object]:
    return _load_json(MANIFEST_PATH, "manifest")


def _load_candidate_manifest() -> dict[str, object]:
    return _load_json(CANDIDATE_MANIFEST_PATH, "candidate manifest")


def _contract_strings(data: dict[str, object], key: str) -> tuple[str, ...]:
    values = data.get(key)
    if not isinstance(values, list):
        return ()
    return tuple(item for item in values if isinstance(item, str))


def _string_array(data: dict[str, object], key: str) -> tuple[str, ...]:
    values = data.get(key)
    if not isinstance(values, list) or not all(
        isinstance(item, str) for item in values
    ):
        raise ValueError(f"{key} must be a string array")
    return tuple(values)


def _blockers(features: tuple[str, ...]) -> tuple[str, ...]:
    blockers: list[str] = []
    for feature in features:
        blocker = BLOCKER_BY_FEATURE.get(feature)
        if blocker is not None:
            blockers.append(blocker)
    return tuple(blockers)


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


def _integer(data: dict[str, object], key: str) -> int:
    value = data.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _boolean(data: dict[str, object], key: str) -> bool:
    value = data.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be a boolean")
    return value


def _require_repo_file(path_text: str, label: str) -> None:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    if not (REPO_ROOT / path).is_file():
        raise ValueError(f"{label} missing: {path_text}")


def _directive_symbol_function_name(symbol: str) -> str:
    name = symbol[1:] if symbol.startswith(".") else symbol
    return f"renderer_directive_{name.replace('.', '_')}_id"


def _opcode_symbol_function_name(symbol: str) -> str:
    return f"renderer_opcode_{symbol.lower()}_id"


def _symbol_id_table(
    data: dict[str, object],
    key: str,
    expected_symbols: tuple[str, ...],
    expected_count: int,
    function_name_for_symbol: Callable[[str], str],
) -> tuple[CandidateSymbol, ...]:
    symbols = _object(data, key)
    if len(symbols) != expected_count:
        raise ValueError(f"candidate {key} symbol ID count must match capabilities")
    if set(symbols) != set(expected_symbols):
        raise ValueError(f"candidate {key} symbol IDs must match subset manifest")

    table: list[CandidateSymbol] = []
    for expected_id, symbol in enumerate(expected_symbols):
        entry = _object(symbols, symbol)
        function_name = _string(entry, "function")
        expected_function_name = function_name_for_symbol(symbol)
        if function_name != expected_function_name:
            raise ValueError(
                f"candidate {key} {symbol} function must be "
                f"{expected_function_name}"
            )
        symbol_id = _integer(entry, "id")
        if symbol_id != expected_id:
            raise ValueError(f"candidate {key} {symbol} ID must be {expected_id}")
        table.append(
            CandidateSymbol(
                symbol_id=symbol_id,
                symbol=symbol,
                function=function_name,
            )
        )

    return tuple(table)


def _manifest_fixtures(data: dict[str, object]) -> tuple[ReferenceFixture, ...]:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list):
        raise ValueError("manifest fixtures must be an array")

    parsed: list[ReferenceFixture] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"manifest fixture {index} must be an object")

        example = item.get("example")
        golden = item.get("golden")
        if not isinstance(example, str) or not example:
            raise ValueError(f"manifest fixture {index} example must be a string")
        if not isinstance(golden, str) or not golden:
            raise ValueError(f"manifest fixture {index} golden must be a string")

        parsed.append(ReferenceFixture(example=example, golden=golden))

    if not parsed:
        raise ValueError("manifest must list at least one fixture")
    return tuple(parsed)


def _validate_contract(data: dict[str, object]) -> None:
    entities = data.get("entities")
    if not isinstance(entities, dict) or "AssemblyProgram" not in entities:
        raise ValueError("contract missing AssemblyProgram entity")


def _validate_reference_fixtures(fixtures: tuple[ReferenceFixture, ...]) -> None:
    for fixture in fixtures:
        example_path = REPO_ROOT / fixture.example
        if not example_path.is_file():
            raise ValueError(f"fixture missing: {fixture.example}")

        golden_path = REPO_ROOT / fixture.golden
        if not golden_path.is_file():
            raise ValueError(f"golden missing: {fixture.golden}")

        try:
            golden_bytes = golden_path.read_bytes()
        except OSError as error:
            raise ValueError(f"golden unreadable: {fixture.golden}") from error

        if not golden_bytes:
            raise ValueError(f"golden empty: {fixture.golden}")
        if not golden_bytes.endswith(b"\n"):
            raise ValueError(f"golden missing final newline: {fixture.golden}")


def load_reference_fixtures() -> tuple[ReferenceFixture, ...]:
    manifest = _load_manifest()
    contract = _load_contract()
    _validate_contract(contract)
    fixtures = _manifest_fixtures(manifest)
    _validate_reference_fixtures(fixtures)
    return fixtures


def load_candidate_status() -> CandidateStatus:
    manifest = _load_candidate_manifest()
    subset_manifest_data = _load_manifest()
    directives = _string_array(subset_manifest_data, "directives")
    opcodes = _string_array(subset_manifest_data, "opcodes")
    candidate_api = _object(manifest, "candidate_api")
    candidate_capabilities = _object(manifest, "candidate_capabilities")
    candidate_execution = _object(manifest, "candidate_execution")
    candidate_smoke = _object(manifest, "candidate_smoke")
    candidate_symbol_ids = _object(manifest, "candidate_symbol_ids")
    candidate_symbol_ranges = _object(manifest, "candidate_symbol_ranges")
    s3_candidate = _object(manifest, "s3_candidate")
    program_inventory = _object(manifest, "program_inventory")
    python_reference = _object(manifest, "python_reference")
    comparison = _object(manifest, "comparison")

    entrypoint = _string(candidate_api, "entrypoint")
    if entrypoint != EXPECTED_ENTRYPOINT:
        raise ValueError(f"candidate API entrypoint must be {EXPECTED_ENTRYPOINT}")
    status_function = _string(candidate_api, "status_function")
    if status_function != EXPECTED_STATUS_FUNCTION:
        raise ValueError(
            f"candidate API status_function must be {EXPECTED_STATUS_FUNCTION}"
        )
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
    expected_directive_count = _integer(
        candidate_capabilities, "expected_directive_count"
    )
    if expected_directive_count != len(directives):
        raise ValueError("candidate directive count must match subset manifest")
    expected_opcode_count = _integer(candidate_capabilities, "expected_opcode_count")
    if expected_opcode_count != len(opcodes):
        raise ValueError("candidate opcode count must match subset manifest")
    smoke_function = _string(candidate_smoke, "function")
    if smoke_function != EXPECTED_SMOKE_FUNCTION:
        raise ValueError(
            f"candidate smoke function must be {EXPECTED_SMOKE_FUNCTION}"
        )
    if _integer(candidate_smoke, "expected_return") != EXPECTED_STUB_STATUS:
        raise ValueError("candidate smoke expected return must be -1")
    smoke_kind = _string(candidate_smoke, "kind")
    if smoke_kind not in EXPECTED_SMOKE_KINDS:
        raise ValueError(
            "candidate smoke kind must be hosted_reachability or hosted_assertion"
        )
    directive_ranges = _object(candidate_symbol_ranges, "directives")
    directive_first_function = _string(directive_ranges, "first_function")
    if directive_first_function != EXPECTED_DIRECTIVE_FIRST_FUNCTION:
        raise ValueError("candidate directive first range function mismatch")
    directive_first_id = _integer(directive_ranges, "first_id")
    if directive_first_id != 0:
        raise ValueError("candidate directive first ID must be 0")
    directive_last_function = _string(directive_ranges, "last_function")
    if directive_last_function != EXPECTED_DIRECTIVE_LAST_FUNCTION:
        raise ValueError("candidate directive last range function mismatch")
    directive_last_id = _integer(directive_ranges, "last_id")
    if directive_last_id != expected_directive_count - 1:
        raise ValueError("candidate directive last ID must match subset manifest")

    opcode_ranges = _object(candidate_symbol_ranges, "opcodes")
    opcode_first_function = _string(opcode_ranges, "first_function")
    if opcode_first_function != EXPECTED_OPCODE_FIRST_FUNCTION:
        raise ValueError("candidate opcode first range function mismatch")
    opcode_first_id = _integer(opcode_ranges, "first_id")
    if opcode_first_id != 0:
        raise ValueError("candidate opcode first ID must be 0")
    opcode_last_function = _string(opcode_ranges, "last_function")
    if opcode_last_function != EXPECTED_OPCODE_LAST_FUNCTION:
        raise ValueError("candidate opcode last range function mismatch")
    opcode_last_id = _integer(opcode_ranges, "last_id")
    if opcode_last_id != expected_opcode_count - 1:
        raise ValueError("candidate opcode last ID must match subset manifest")

    directive_support_predicate: str | None = None
    opcode_support_predicate: str | None = None
    predicate_value = manifest.get("candidate_symbol_predicates")
    if predicate_value is not None:
        if not isinstance(predicate_value, dict):
            raise ValueError("candidate symbol predicates must be an object")
        directive_support_predicate = _string(predicate_value, "directive_function")
        if directive_support_predicate != EXPECTED_DIRECTIVE_PREDICATE_FUNCTION:
            raise ValueError("candidate directive support predicate mismatch")
        opcode_support_predicate = _string(predicate_value, "opcode_function")
        if opcode_support_predicate != EXPECTED_OPCODE_PREDICATE_FUNCTION:
            raise ValueError("candidate opcode support predicate mismatch")
        if _integer(predicate_value, "supported_return") != 1:
            raise ValueError("candidate support predicate supported return must be 1")
        if _integer(predicate_value, "unsupported_return") != EXPECTED_STUB_STATUS:
            raise ValueError(
                "candidate support predicate unsupported return must be -1"
            )
    directive_symbols = _symbol_id_table(
        candidate_symbol_ids,
        "directives",
        directives,
        expected_directive_count,
        _directive_symbol_function_name,
    )
    opcode_symbols = _symbol_id_table(
        candidate_symbol_ids,
        "opcodes",
        opcodes,
        expected_opcode_count,
        _opcode_symbol_function_name,
    )

    candidate_path = _string(s3_candidate, "path")
    if candidate_path != EXPECTED_CANDIDATE_PATH:
        raise ValueError(f"candidate path must be {EXPECTED_CANDIDATE_PATH}")
    _require_repo_file(candidate_path, "candidate path")

    if _string(s3_candidate, "api_status") != "stub":
        raise ValueError("candidate api_status must be stub")

    execution_mode = _string(candidate_execution, "mode")
    if execution_mode != EXPECTED_EXECUTION_MODE:
        raise ValueError("candidate execution mode must be hosted")
    execution_entrypoint = _string(candidate_execution, "entrypoint")
    if execution_entrypoint != EXPECTED_ENTRYPOINT:
        raise ValueError(
            f"candidate execution entrypoint must be {EXPECTED_ENTRYPOINT}"
        )
    expected_status = _integer(candidate_execution, "expected_status")
    if expected_status != EXPECTED_STUB_STATUS:
        raise ValueError("candidate execution expected_status must be -1")
    execution_meaning = _string(candidate_execution, "meaning")
    if execution_meaning != "stub":
        raise ValueError("candidate execution meaning must be stub")

    subset_manifest = _string(python_reference, "subset_manifest")
    _require_repo_file(subset_manifest, "subset manifest")
    data_contract = _string(python_reference, "data_contract")
    _require_repo_file(data_contract, "data contract")

    implements_renderer = s3_candidate.get("implements_renderer")
    if implements_renderer is not False:
        raise ValueError("candidate implements_renderer must be false")

    inventory_path = _string(program_inventory, "path")
    if inventory_path != candidate_path:
        raise ValueError("program inventory path must match candidate path")
    if _integer(program_inventory, "hosted_expected_return") != expected_status:
        raise ValueError("program inventory hosted expected return must match")
    covered_by_s3_program_check = _boolean(
        program_inventory, "covered_by_s3_program_check"
    )
    if not covered_by_s3_program_check:
        raise ValueError("candidate must be covered by s3_program_check")

    inventory_program = find_program(candidate_path)
    if inventory_program is None:
        raise ValueError("candidate missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != expected_status:
        raise ValueError("s3_program_check hosted expected return must match")

    comparison_status = _string(comparison, "status")
    if comparison_status != "blocked":
        raise ValueError("candidate comparison status must be blocked")

    return CandidateStatus(
        path=candidate_path,
        status=_string(s3_candidate, "status"),
        entrypoint=entrypoint,
        status_function=status_function,
        directive_count_function=directive_count_function,
        opcode_count_function=opcode_count_function,
        smoke_function=smoke_function,
        directive_id_functions=len(directive_symbols),
        opcode_id_functions=len(opcode_symbols),
        directive_symbols=directive_symbols,
        opcode_symbols=opcode_symbols,
        directive_first_id=directive_first_id,
        directive_last_id=directive_last_id,
        opcode_first_id=opcode_first_id,
        opcode_last_id=opcode_last_id,
        directive_support_predicate=directive_support_predicate,
        opcode_support_predicate=opcode_support_predicate,
        execution_mode=execution_mode,
        expected_status=expected_status,
        execution_meaning=execution_meaning,
        covered_by_s3_program_check=covered_by_s3_program_check,
        implements_renderer=implements_renderer,
        comparison_status=comparison_status,
    )


def render_candidate_status(candidate: CandidateStatus) -> str:
    implements = "yes" if candidate.implements_renderer else "no"
    lines = [
        "S3 Assembly renderer candidate",
        "",
        f"status: {candidate.status}",
        f"path: {candidate.path}",
        f"entrypoint: {candidate.entrypoint}",
        f"status function: {candidate.status_function}",
        f"directive count function: {candidate.directive_count_function}",
        f"opcode count function: {candidate.opcode_count_function}",
        f"capability smoke function: {candidate.smoke_function}",
        f"directive id functions: {candidate.directive_id_functions}",
        f"opcode id functions: {candidate.opcode_id_functions}",
        (
            "directive id range: "
            f"{candidate.directive_first_id}..{candidate.directive_last_id}"
        ),
        f"opcode id range: {candidate.opcode_first_id}..{candidate.opcode_last_id}",
        f"implements renderer: {implements}",
        f"comparison: {candidate.comparison_status}",
    ]
    if candidate.directive_support_predicate is not None:
        lines.insert(
            -2,
            "directive support predicate: "
            f"{candidate.directive_support_predicate}",
        )
    if candidate.opcode_support_predicate is not None:
        lines.insert(
            -2,
            f"opcode support predicate: {candidate.opcode_support_predicate}",
        )
    return "\n".join(lines) + "\n"


def render_candidate_symbols(candidate: CandidateStatus) -> str:
    lines = [
        "S3 Assembly renderer candidate symbols",
        "",
        "directives:",
    ]
    lines.extend(
        f"  {entry.symbol_id} {entry.symbol} {entry.function}"
        for entry in candidate.directive_symbols
    )
    lines.extend(
        [
            "",
            "opcodes:",
        ]
    )
    lines.extend(
        f"  {entry.symbol_id} {entry.symbol} {entry.function}"
        for entry in candidate.opcode_symbols
    )
    lines.extend(
        [
            "",
            (
                "directive id range: "
                f"{candidate.directive_first_id}..{candidate.directive_last_id}"
            ),
            f"opcode id range: {candidate.opcode_first_id}..{candidate.opcode_last_id}",
            f"status: {candidate.status}",
            f"comparison: {candidate.comparison_status}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_reference_status(fixtures: tuple[ReferenceFixture, ...]) -> str:
    lines = [
        "S3 Assembly renderer Python reference",
        "",
        "status: available",
        "",
        "fixtures:",
    ]
    lines.extend(f"  {fixture.example} -> {fixture.golden}" for fixture in fixtures)
    return "\n".join(lines) + "\n"


def render_candidate_execution(candidate: CandidateStatus, actual_status: int) -> str:
    status = (
        candidate.execution_meaning
        if actual_status == candidate.expected_status
        else "unexpected"
    )
    coverage = "yes" if candidate.covered_by_s3_program_check else "no"
    lines = [
        "S3 Assembly renderer candidate execution",
        "",
        f"path: {candidate.path}",
        f"entrypoint: {candidate.entrypoint}",
        f"expected status: {candidate.expected_status}",
        f"actual status: {actual_status}",
        f"covered by s3_program_check: {coverage}",
        f"status: {status}",
    ]
    return "\n".join(lines) + "\n"


def status() -> int:
    contract = _load_contract()
    fixtures = _contract_strings(contract, "initial_fixtures")
    features = _contract_strings(contract, "required_language_features")

    print("S3 Assembly renderer comparison harness")
    print()
    print("python reference: available")
    print("s3 renderer stub: available")
    print("s3 renderer implementation: not implemented")
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


def reference() -> int:
    try:
        fixtures = load_reference_fixtures()
    except ValueError as error:
        print("S3 Assembly renderer Python reference")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_reference_status(fixtures), end="")
    return 0


def candidate() -> int:
    try:
        candidate_status = load_candidate_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_status(candidate_status), end="")
    return 0


def candidate_symbols() -> int:
    try:
        candidate_status = load_candidate_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate symbols")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_symbols(candidate_status), end="")
    return 0


def candidate_run() -> int:
    try:
        candidate_status = load_candidate_status()
        inventory_program = find_program(candidate_status.path)
        if inventory_program is None:
            raise ValueError("candidate missing from s3_program_check inventory")
        actual_status = run_hosted_check(
            inventory_program,
            entry=candidate_status.entrypoint,
        )
    except (OSError, ValueError) as error:
        print("S3 Assembly renderer candidate execution")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1
    except Exception as error:
        print("S3 Assembly renderer candidate execution")
        print()
        print("status: failed")
        print(f"reason: {error}")
        return 1

    print(render_candidate_execution(candidate_status, actual_status), end="")
    if actual_status != candidate_status.expected_status:
        return 1
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
    mode.add_argument("--reference", action="store_true")
    mode.add_argument("--candidate", action="store_true")
    mode.add_argument("--candidate-symbols", action="store_true")
    mode.add_argument("--candidate-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    if args.status:
        return status()
    if args.reference:
        return reference()
    if args.candidate:
        return candidate()
    if args.candidate_symbols:
        return candidate_symbols()
    if args.candidate_run:
        return candidate_run()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
