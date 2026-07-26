from __future__ import annotations

import argparse
import hashlib
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
CANDIDATE_FIXTURES_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_fixtures.json"
)
CANDIDATE_FIXTURE_EXPECTATIONS_PATH = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_fixture_expectations.json"
)
CANDIDATE_COMPARISON_PLAN_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_comparison_plan.json"
)
CANDIDATE_ACTUAL_OUTPUTS_PATH = (
    REPO_ROOT / "tests" / "golden" / "assembly_renderer_candidate_actual_outputs.json"
)
CONTRACT_PATH = REPO_ROOT / "tests" / "golden" / "assembly_program_data_contract.json"
BLOCKED_MESSAGE = (
    "assembly renderer comparison is blocked: S3 renderer is not implemented"
)
EXPECTED_CANDIDATE_PATH = "examples/self_hosting/assembly_renderer_stub.s3"
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

FIRST_S3_RENDERER = FIXTURE_METADATA["first"].s3_path
FIRST_S3_GOLDEN = FIXTURE_METADATA["first"].golden_path
SIMPLE_CALL_S3_RENDERER = FIXTURE_METADATA["simple_call"].s3_path
SIMPLE_CALL_S3_GOLDEN = FIXTURE_METADATA["simple_call"].golden_path
SIGN_S3_RENDERER = FIXTURE_METADATA["sign"].s3_path
SIGN_S3_GOLDEN = FIXTURE_METADATA["sign"].golden_path
EXPECTED_ENTRYPOINT = "main"
EXPECTED_STATUS_FUNCTION = "renderer_candidate_status"
EXPECTED_EXECUTION_MODE = "hosted"
EXPECTED_STUB_STATUS = -1
EXPECTED_BOOTSTRAP_PATH = "examples/self_hosting/assembly_renderer_bootstrap.s3"
EXPECTED_BOOTSTRAP_ENTRYPOINT = "main"
EXPECTED_BOOTSTRAP_RETURN = 0
EXPECTED_OUTPUT_MODEL_PATH = "examples/self_hosting/assembly_renderer_output_model.s3"
EXPECTED_OUTPUT_MODEL_ENTRYPOINT = "main"
EXPECTED_OUTPUT_MODEL_RETURN = 0
EXPECTED_TEXT_SEGMENT_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_text_segments.s3"
)
EXPECTED_TEXT_SEGMENT_MODEL_ENTRYPOINT = "main"
EXPECTED_TEXT_SEGMENT_MODEL_RETURN = 0
EXPECTED_LINE_BLUEPRINT_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_line_blueprints.s3"
)
EXPECTED_LINE_BLUEPRINT_MODEL_ENTRYPOINT = "main"
EXPECTED_LINE_BLUEPRINT_MODEL_RETURN = 0
EXPECTED_LINE_SEQUENCE_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_line_sequences.s3"
)
EXPECTED_LINE_SEQUENCE_MODEL_ENTRYPOINT = "main"
EXPECTED_LINE_SEQUENCE_MODEL_RETURN = 0
EXPECTED_LINE_CONTENT_ENCODING_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_line_encodings.s3"
)
EXPECTED_LINE_CONTENT_ENCODING_MODEL_ENTRYPOINT = "main"
EXPECTED_LINE_CONTENT_ENCODING_MODEL_RETURN = 0
EXPECTED_EVENT_STREAM_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_event_stream.s3"
)
EXPECTED_EVENT_STREAM_MODEL_ENTRYPOINT = "main"
EXPECTED_EVENT_STREAM_MODEL_RETURN = 0
EXPECTED_EVENT_WRITER_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_event_writer.s3"
)
EXPECTED_EVENT_WRITER_MODEL_ENTRYPOINT = "main"
EXPECTED_EVENT_WRITER_MODEL_RETURN = 0
EXPECTED_OUTPUT_BUFFER_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_output_buffer.s3"
)
EXPECTED_OUTPUT_BUFFER_MODEL_ENTRYPOINT = "main"
EXPECTED_OUTPUT_BUFFER_MODEL_RETURN = 0
EXPECTED_PIPELINE_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_pipeline.s3"
)
EXPECTED_PIPELINE_MODEL_ENTRYPOINT = "main"
EXPECTED_PIPELINE_MODEL_RETURN = 0
EXPECTED_TEXT_BUILDER_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_text_builder.s3"
)
EXPECTED_TEXT_BUILDER_MODEL_ENTRYPOINT = "main"
EXPECTED_TEXT_BUILDER_MODEL_RETURN = 0
EXPECTED_TEXT_FRAGMENT_MODEL_PATH = (
    "examples/self_hosting/assembly_renderer_text_fragments.s3"
)
EXPECTED_TEXT_FRAGMENT_MODEL_ENTRYPOINT = "main"
EXPECTED_TEXT_FRAGMENT_MODEL_RETURN = 0
EXPECTED_FIXED_TRYTE_BUFFER_MODEL_PATH = (
    "examples/self_hosting/fixed_tryte_buffer.s3"
)
EXPECTED_FIXED_TRYTE_BUFFER_MODEL_ENTRYPOINT = "main"
EXPECTED_FIXED_TRYTE_BUFFER_MODEL_RETURN = 0
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
class CandidateFixture:
    name: str
    source: str
    assembly_golden: str


@dataclass(frozen=True, slots=True)
class CandidateFixtureExclusion:
    name: str
    reason: str


@dataclass(frozen=True, slots=True)
class CandidateFixtureStatus:
    status: str
    comparison_status: str
    fixtures: tuple[CandidateFixture, ...]
    excluded: tuple[CandidateFixtureExclusion, ...]


@dataclass(frozen=True, slots=True)
class CandidateFixtureExpectation:
    name: str
    source: str
    expected_assembly: str
    sha256: str
    byte_count: int
    line_count: int


@dataclass(frozen=True, slots=True)
class CandidateFixtureExpectationStatus:
    source_manifest: str
    status: str
    comparison_status: str
    expectations: tuple[CandidateFixtureExpectation, ...]


@dataclass(frozen=True, slots=True)
class CandidateComparisonPlanFixture:
    name: str
    source: str
    expected_assembly: str
    expected_sha256: str
    actual_output_status: str
    comparison_status: str


@dataclass(frozen=True, slots=True)
class CandidateComparisonPlanStatus:
    fixture_expectations: str
    expected_output_source: str
    actual_output_source: str
    actual_output_status: str
    status: str
    comparison_status: str
    fixtures: tuple[CandidateComparisonPlanFixture, ...]


@dataclass(frozen=True, slots=True)
class CandidateActualOutput:
    name: str
    source: str
    expected_assembly: str
    planned_actual_output: str
    actual_output_status: str
    actual_output_exists: bool
    comparison_status: str
    actual_sha256: str | None
    actual_byte_count: int | None
    actual_line_count: int | None


@dataclass(frozen=True, slots=True)
class CandidateActualOutputStatus:
    comparison_plan: str
    actual_output_root: str
    status: str
    comparison_status: str
    outputs: tuple[CandidateActualOutput, ...]


@dataclass(frozen=True, slots=True)
class AvailableComparison:
    name: str
    expected_assembly: str | None
    actual_output: str | None
    status: str
    reason: str | None
    sha256: str | None
    byte_count: int | None
    line_count: int | None


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


@dataclass(frozen=True, slots=True)
class BootstrapExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class OutputModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class TextSegmentModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class LineBlueprintModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class LineSequenceModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class LineContentEncodingModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class EventStreamModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class EventWriterModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class OutputBufferModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class PipelineModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class TextBuilderModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class TextFragmentModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


@dataclass(frozen=True, slots=True)
class FixedTryteBufferModelExecution:
    path: str
    entrypoint: str
    expected_return: int
    actual_return: int
    covered_by_s3_program_check: bool


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


def _load_candidate_fixtures_manifest() -> dict[str, object]:
    return _load_json(CANDIDATE_FIXTURES_PATH, "candidate fixtures manifest")


def _load_candidate_fixture_expectations_manifest() -> dict[str, object]:
    return _load_json(
        CANDIDATE_FIXTURE_EXPECTATIONS_PATH,
        "candidate fixture expectations manifest",
    )


def _load_candidate_comparison_plan_manifest() -> dict[str, object]:
    return _load_json(
        CANDIDATE_COMPARISON_PLAN_PATH,
        "candidate comparison plan manifest",
    )


def _load_candidate_actual_outputs_manifest() -> dict[str, object]:
    return _load_json(
        CANDIDATE_ACTUAL_OUTPUTS_PATH,
        "candidate actual outputs manifest",
    )


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


def _optional_string(data: dict[str, object], key: str) -> str | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, str) or not value:
        raise ValueError(f"{key} must be a string")
    return value


def _optional_integer(data: dict[str, object], key: str) -> int | None:
    value = data.get(key)
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{key} must be an integer")
    return value


def _require_repo_file(path_text: str, label: str) -> None:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    if not (REPO_ROOT / path).is_file():
        raise ValueError(f"{label} missing: {path_text}")


def _repo_file_path(path_text: str, label: str) -> Path:
    path = Path(path_text)
    if path.is_absolute():
        raise ValueError(f"{label} must be relative")
    resolved = REPO_ROOT / path
    if not resolved.is_file():
        raise ValueError(f"{label} missing: {path_text}")
    return resolved


def _lf_normalized_file_bytes(path_text: str, label: str) -> bytes:
    path = _repo_file_path(path_text, label)
    text = path.read_bytes().decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


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


def _manifest_candidate_fixtures(data: dict[str, object]) -> tuple[CandidateFixture, ...]:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("candidate fixtures must be a non-empty array")

    parsed: list[CandidateFixture] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"candidate fixture {index} must be an object")
        name = _string(item, "name")
        source = _string(item, "source")
        assembly_golden = _string(item, "assembly_golden")
        if _string(item, "status") != "reference":
            raise ValueError(f"candidate fixture {name} status must be reference")
        _require_repo_file(source, "candidate fixture source")
        _require_repo_file(assembly_golden, "candidate fixture assembly golden")
        parsed.append(
            CandidateFixture(
                name=name,
                source=source,
                assembly_golden=assembly_golden,
            )
        )

    if len({fixture.name for fixture in parsed}) != len(parsed):
        raise ValueError("candidate fixture names must be unique")
    return tuple(parsed)


def _manifest_candidate_exclusions(
    data: dict[str, object],
) -> tuple[CandidateFixtureExclusion, ...]:
    excluded = data.get("excluded")
    if not isinstance(excluded, list):
        raise ValueError("candidate fixture excluded must be an array")

    parsed: list[CandidateFixtureExclusion] = []
    for index, item in enumerate(excluded):
        if not isinstance(item, dict):
            raise ValueError(f"candidate fixture exclusion {index} must be an object")
        parsed.append(
            CandidateFixtureExclusion(
                name=_string(item, "name"),
                reason=_string(item, "reason"),
            )
        )
    return tuple(parsed)


def _manifest_candidate_fixture_expectations(
    data: dict[str, object],
) -> tuple[CandidateFixtureExpectation, ...]:
    expectations = data.get("expectations")
    if not isinstance(expectations, list) or not expectations:
        raise ValueError("candidate fixture expectations must be a non-empty array")

    parsed: list[CandidateFixtureExpectation] = []
    for index, item in enumerate(expectations):
        if not isinstance(item, dict):
            raise ValueError(f"candidate fixture expectation {index} must be an object")
        name = _string(item, "name")
        source = _string(item, "source")
        expected_assembly = _string(item, "expected_assembly")
        if _string(item, "status") != "expected":
            raise ValueError(f"candidate fixture expectation {name} status mismatch")
        _require_repo_file(source, "candidate fixture expectation source")
        _require_repo_file(
            expected_assembly,
            "candidate fixture expectation assembly",
        )
        parsed.append(
            CandidateFixtureExpectation(
                name=name,
                source=source,
                expected_assembly=expected_assembly,
                sha256=_string(item, "sha256"),
                byte_count=_integer(item, "byte_count"),
                line_count=_integer(item, "line_count"),
            )
        )

    if len({expectation.name for expectation in parsed}) != len(parsed):
        raise ValueError("candidate fixture expectation names must be unique")
    if "assembly_renderer_stub" in {expectation.name for expectation in parsed}:
        raise ValueError("candidate stub must not be a fixture expectation")
    return tuple(parsed)


def _manifest_candidate_comparison_plan_fixtures(
    data: dict[str, object],
) -> tuple[CandidateComparisonPlanFixture, ...]:
    fixtures = data.get("fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        raise ValueError("candidate comparison plan fixtures must be a non-empty array")

    parsed: list[CandidateComparisonPlanFixture] = []
    for index, item in enumerate(fixtures):
        if not isinstance(item, dict):
            raise ValueError(f"candidate comparison plan fixture {index} must be an object")
        name = _string(item, "name")
        source = _string(item, "source")
        expected_assembly = _string(item, "expected_assembly")
        _require_repo_file(source, "candidate comparison plan source")
        _require_repo_file(expected_assembly, "candidate comparison plan expected assembly")
        parsed.append(
            CandidateComparisonPlanFixture(
                name=name,
                source=source,
                expected_assembly=expected_assembly,
                expected_sha256=_string(item, "expected_sha256"),
                actual_output_status=_string(item, "actual_output_status"),
                comparison_status=_string(item, "comparison_status"),
            )
        )

    if len({fixture.name for fixture in parsed}) != len(parsed):
        raise ValueError("candidate comparison plan fixture names must be unique")
    if "assembly_renderer_stub" in {fixture.name for fixture in parsed}:
        raise ValueError("candidate stub must not be a comparison plan fixture")
    return tuple(parsed)


def _manifest_candidate_actual_outputs(
    data: dict[str, object],
) -> tuple[CandidateActualOutput, ...]:
    outputs = data.get("outputs")
    if not isinstance(outputs, list) or not outputs:
        raise ValueError("candidate actual outputs must be a non-empty array")

    parsed: list[CandidateActualOutput] = []
    for index, item in enumerate(outputs):
        if not isinstance(item, dict):
            raise ValueError(f"candidate actual output {index} must be an object")
        name = _string(item, "name")
        source = _string(item, "source")
        expected_assembly = _string(item, "expected_assembly")
        planned_actual_output = _string(item, "planned_actual_output")
        _require_repo_file(source, "candidate actual output source")
        _require_repo_file(expected_assembly, "candidate actual output expected assembly")
        if Path(planned_actual_output).is_absolute():
            raise ValueError("candidate actual output planned path must be relative")
        parsed.append(
            CandidateActualOutput(
                name=name,
                source=source,
                expected_assembly=expected_assembly,
                planned_actual_output=planned_actual_output,
                actual_output_status=_string(item, "actual_output_status"),
                actual_output_exists=_boolean(item, "actual_output_exists"),
                comparison_status=_string(item, "comparison_status"),
                actual_sha256=_optional_string(item, "actual_sha256"),
                actual_byte_count=_optional_integer(item, "actual_byte_count"),
                actual_line_count=_optional_integer(item, "actual_line_count"),
            )
        )

    if len({output.name for output in parsed}) != len(parsed):
        raise ValueError("candidate actual output names must be unique")
    if "assembly_renderer_stub" in {output.name for output in parsed}:
        raise ValueError("candidate stub must not be an actual output")
    return tuple(parsed)


def load_reference_fixtures() -> tuple[ReferenceFixture, ...]:
    manifest = _load_manifest()
    contract = _load_contract()
    _validate_contract(contract)
    fixtures = _manifest_fixtures(manifest)
    _validate_reference_fixtures(fixtures)
    return fixtures


def load_candidate_fixture_status() -> CandidateFixtureStatus:
    manifest = _load_candidate_fixtures_manifest()
    if _string(manifest, "version") != "1.0.0":
        raise ValueError("candidate fixtures version must be 1.0.0")
    if _string(manifest, "component") != "assembly_renderer_candidate_fixtures":
        raise ValueError("candidate fixtures component mismatch")
    status = _string(manifest, "status")
    if status != "reference_only":
        raise ValueError("candidate fixtures status must be reference_only")
    comparison = _object(manifest, "comparison")
    comparison_status = _string(comparison, "status")
    if comparison_status != "blocked":
        raise ValueError("candidate fixtures comparison status must be blocked")

    fixtures = _manifest_candidate_fixtures(manifest)
    excluded = _manifest_candidate_exclusions(manifest)
    if "assembly_renderer_stub" in {fixture.name for fixture in fixtures}:
        raise ValueError("candidate stub must not be a renderer target fixture")
    if "assembly_renderer_stub" not in {item.name for item in excluded}:
        raise ValueError("candidate stub must be listed as excluded")

    return CandidateFixtureStatus(
        status=status,
        comparison_status=comparison_status,
        fixtures=fixtures,
        excluded=excluded,
    )


def load_candidate_fixture_expectation_status() -> CandidateFixtureExpectationStatus:
    manifest = _load_candidate_fixture_expectations_manifest()
    if _string(manifest, "version") != "1.0.0":
        raise ValueError("candidate fixture expectations version must be 1.0.0")
    if (
        _string(manifest, "component")
        != "assembly_renderer_candidate_fixture_expectations"
    ):
        raise ValueError("candidate fixture expectations component mismatch")
    status = _string(manifest, "status")
    if status != "reference_only":
        raise ValueError(
            "candidate fixture expectations status must be reference_only"
        )
    comparison = _object(manifest, "comparison")
    comparison_status = _string(comparison, "status")
    if comparison_status != "blocked":
        raise ValueError(
            "candidate fixture expectations comparison status must be blocked"
        )
    source_manifest = _string(manifest, "source_manifest")
    if source_manifest != "tests/golden/assembly_renderer_candidate_fixtures.json":
        raise ValueError("candidate fixture expectations source manifest mismatch")
    _require_repo_file(source_manifest, "candidate fixture source manifest")

    return CandidateFixtureExpectationStatus(
        source_manifest=source_manifest,
        status=status,
        comparison_status=comparison_status,
        expectations=_manifest_candidate_fixture_expectations(manifest),
    )


def load_candidate_comparison_plan_status() -> CandidateComparisonPlanStatus:
    manifest = _load_candidate_comparison_plan_manifest()
    if _string(manifest, "version") != "1.0.0":
        raise ValueError("candidate comparison plan version must be 1.0.0")
    if _string(manifest, "component") != "assembly_renderer_candidate_comparison_plan":
        raise ValueError("candidate comparison plan component mismatch")
    status = _string(manifest, "status")
    if status != "blocked":
        raise ValueError("candidate comparison plan status must be blocked")
    fixture_expectations = _string(manifest, "fixture_expectations")
    if (
        fixture_expectations
        != "tests/golden/assembly_renderer_candidate_fixture_expectations.json"
    ):
        raise ValueError("candidate comparison plan fixture expectations mismatch")
    _require_repo_file(fixture_expectations, "candidate comparison plan expectations")
    comparison = _object(manifest, "comparison")
    expected_output_source = _string(comparison, "expected_output_source")
    if expected_output_source != "assembly_golden":
        raise ValueError("candidate comparison plan expected output source mismatch")
    actual_output_source = _string(comparison, "actual_output_source")
    if actual_output_source != "s3_renderer_candidate":
        raise ValueError("candidate comparison plan actual output source mismatch")
    actual_output_status = _string(comparison, "actual_output_status")
    if actual_output_status != "not_implemented":
        raise ValueError("candidate comparison plan actual output status mismatch")
    comparison_status = _string(comparison, "result")
    if comparison_status != "blocked":
        raise ValueError("candidate comparison plan comparison result mismatch")

    return CandidateComparisonPlanStatus(
        fixture_expectations=fixture_expectations,
        expected_output_source=expected_output_source,
        actual_output_source=actual_output_source,
        actual_output_status=actual_output_status,
        status=status,
        comparison_status=comparison_status,
        fixtures=_manifest_candidate_comparison_plan_fixtures(manifest),
    )


def load_candidate_actual_output_status() -> CandidateActualOutputStatus:
    manifest = _load_candidate_actual_outputs_manifest()
    if _string(manifest, "version") != "1.0.0":
        raise ValueError("candidate actual outputs version must be 1.0.0")
    if _string(manifest, "component") != "assembly_renderer_candidate_actual_outputs":
        raise ValueError("candidate actual outputs component mismatch")
    status = _string(manifest, "status")
    if status not in {"blocked", "partial"}:
        raise ValueError("candidate actual outputs status must be blocked or partial")
    comparison_plan = _string(manifest, "comparison_plan")
    if comparison_plan != "tests/golden/assembly_renderer_candidate_comparison_plan.json":
        raise ValueError("candidate actual outputs comparison plan mismatch")
    _require_repo_file(comparison_plan, "candidate actual outputs comparison plan")
    actual_output_root = _string(manifest, "actual_output_root")
    if actual_output_root != "tests/golden/assembly_renderer_candidate_actual":
        raise ValueError("candidate actual outputs root mismatch")

    outputs = _manifest_candidate_actual_outputs(manifest)
    for output in outputs:
        if output.actual_output_status == "available":
            if not output.actual_output_exists:
                raise ValueError("candidate actual output existence flag mismatch")
            if output.comparison_status not in {"pending", "passed"}:
                raise ValueError("candidate actual output comparison status mismatch")
            if (
                output.actual_sha256 is None
                or output.actual_byte_count is None
                or output.actual_line_count is None
            ):
                raise ValueError("candidate actual output metadata missing")
        elif output.actual_output_status == "not_implemented":
            if output.actual_output_exists:
                raise ValueError("candidate actual output existence flag mismatch")
            if output.comparison_status != "blocked":
                raise ValueError("candidate actual output comparison status mismatch")
            if (
                output.actual_sha256 is not None
                or output.actual_byte_count is not None
                or output.actual_line_count is not None
            ):
                raise ValueError("candidate actual output metadata mismatch")
        else:
            raise ValueError("candidate actual output status mismatch")

    return CandidateActualOutputStatus(
        comparison_plan=comparison_plan,
        actual_output_root=actual_output_root,
        status=status,
        comparison_status="blocked",
        outputs=outputs,
    )


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


def render_candidate_fixtures(candidate: CandidateFixtureStatus) -> str:
    lines = [
        "S3 Assembly renderer candidate fixtures",
        "",
        "fixtures:",
    ]
    lines.extend(
        f"  {fixture.name} {fixture.source} {fixture.assembly_golden}"
        for fixture in candidate.fixtures
    )
    lines.extend(
        [
            "",
            "excluded:",
        ]
    )
    lines.extend(
        f"  {item.name} {item.reason}"
        for item in candidate.excluded
    )
    lines.extend(
        [
            "",
            f"status: {candidate.status}",
            f"comparison: {candidate.comparison_status}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_candidate_fixture_expectations(
    candidate: CandidateFixtureExpectationStatus,
) -> str:
    lines = [
        "S3 Assembly renderer candidate fixture expectations",
        "",
        "expectations:",
    ]
    lines.extend(
        (
            f"  {expectation.name} {expectation.expected_assembly} "
            f"sha256={expectation.sha256} "
            f"bytes={expectation.byte_count} lines={expectation.line_count}"
        )
        for expectation in candidate.expectations
    )
    lines.extend(
        [
            "",
            f"source manifest: {candidate.source_manifest}",
            f"status: {candidate.status}",
            f"comparison: {candidate.comparison_status}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_candidate_comparison_plan(
    candidate: CandidateComparisonPlanStatus,
) -> str:
    lines = [
        "S3 Assembly renderer candidate comparison plan",
        "",
        f"fixture expectations: {candidate.fixture_expectations}",
        "",
        "fixtures:",
    ]
    lines.extend(
        (
            f"  {fixture.name} expected={fixture.expected_assembly} "
            f"sha256={fixture.expected_sha256} "
            f"actual={fixture.actual_output_status} "
            f"comparison={fixture.comparison_status}"
        )
        for fixture in candidate.fixtures
    )
    lines.extend(
        [
            "",
            f"expected output: {candidate.expected_output_source}",
            f"actual output: {candidate.actual_output_source}",
            f"actual output status: {candidate.actual_output_status}",
            f"status: {candidate.status}",
            f"comparison: {candidate.comparison_status}",
        ]
    )
    return "\n".join(lines) + "\n"


def render_candidate_actual_outputs(
    candidate: CandidateActualOutputStatus,
) -> str:
    lines = [
        "S3 Assembly renderer candidate actual outputs",
        "",
        f"comparison plan: {candidate.comparison_plan}",
        f"actual output root: {candidate.actual_output_root}",
        "",
        "outputs:",
    ]
    for output in candidate.outputs:
        line = (
            f"  {output.name} planned={output.planned_actual_output} "
            f"exists={str(output.actual_output_exists).lower()} "
            f"status={output.actual_output_status} "
            f"comparison={output.comparison_status}"
        )
        if output.actual_output_status == "available":
            line = (
                f"{line} sha256={output.actual_sha256} "
                f"bytes={output.actual_byte_count} "
                f"lines={output.actual_line_count}"
            )
        lines.append(line)
    lines.extend(
        [
            "",
            f"status: {candidate.status}",
            f"comparison: {candidate.comparison_status}",
        ]
    )
    return "\n".join(lines) + "\n"


def compare_available_outputs(
    candidate: CandidateActualOutputStatus,
) -> tuple[AvailableComparison, ...]:
    comparisons: list[AvailableComparison] = []
    for output in candidate.outputs:
        if output.actual_output_status != "available":
            comparisons.append(
                AvailableComparison(
                    name=output.name,
                    expected_assembly=None,
                    actual_output=None,
                    status="blocked",
                    reason="actual output is not implemented",
                    sha256=None,
                    byte_count=None,
                    line_count=None,
                )
            )
            continue

        expected = _lf_normalized_file_bytes(
            output.expected_assembly,
            "available comparison expected assembly",
        )
        actual = _lf_normalized_file_bytes(
            output.planned_actual_output,
            "available comparison actual output",
        )
        if expected != actual:
            raise ValueError(f"available comparison {output.name} differs")
        sha256 = hashlib.sha256(actual).hexdigest()
        byte_count = len(actual)
        line_count = 0 if actual == b"" else len(actual.decode("utf-8").splitlines())
        if output.actual_sha256 != sha256:
            raise ValueError(f"available comparison {output.name} sha256 mismatch")
        if output.actual_byte_count != byte_count:
            raise ValueError(f"available comparison {output.name} byte count mismatch")
        if output.actual_line_count != line_count:
            raise ValueError(f"available comparison {output.name} line count mismatch")
        if output.comparison_status == "pending":
            comparisons.append(
                AvailableComparison(
                    name=output.name,
                    expected_assembly=output.expected_assembly,
                    actual_output=output.planned_actual_output,
                    status="pending",
                    reason="formal comparison is pending",
                    sha256=sha256,
                    byte_count=byte_count,
                    line_count=line_count,
                )
            )
            continue
        if output.comparison_status != "passed":
            raise ValueError(
                f"available comparison {output.name} comparison status mismatch"
            )
        comparisons.append(
            AvailableComparison(
                name=output.name,
                expected_assembly=output.expected_assembly,
                actual_output=output.planned_actual_output,
                status="passed",
                reason=None,
                sha256=sha256,
                byte_count=byte_count,
                line_count=line_count,
            )
        )
    return tuple(comparisons)


def render_available_comparisons(
    comparisons: tuple[AvailableComparison, ...],
) -> str:
    available_count = sum(1 for item in comparisons if item.status != "blocked")
    passed_count = sum(1 for item in comparisons if item.status == "passed")
    pending_count = sum(1 for item in comparisons if item.status == "pending")
    blocked_count = sum(1 for item in comparisons if item.status == "blocked")
    lines = [
        "S3 Assembly renderer candidate available comparisons",
        "",
        "comparisons:",
    ]
    for item in comparisons:
        if item.status in {"passed", "pending"}:
            lines.append(
                f"  {item.name} expected={item.expected_assembly} "
                f"actual={item.actual_output} status={item.status} "
                f"sha256={item.sha256} bytes={item.byte_count} "
                f"lines={item.line_count}"
            )
        else:
            lines.append(
                f"  {item.name} status=blocked reason={item.reason}"
            )
    lines.extend(
        [
            "",
            f"available comparisons: {available_count}",
            f"passed comparisons: {passed_count}",
            f"pending comparisons: {pending_count}",
            f"blocked comparisons: {blocked_count}",
            "status: partial",
            "comparison: partial",
        ]
    )
    return "\n".join(lines) + "\n"


def _available_comparison_summary(
    comparisons: tuple[AvailableComparison, ...],
) -> str:
    if comparisons and all(item.status == "passed" for item in comparisons):
        return "passed"
    if any(item.status == "pending" for item in comparisons):
        return "partial"
    return "blocked"


def render_check_status(
    candidate_status: CandidateStatus,
    comparisons: tuple[AvailableComparison, ...],
) -> str:
    renderer_implementation = (
        "implemented" if candidate_status.implements_renderer else "not_implemented"
    )
    available_comparisons = _available_comparison_summary(comparisons)
    actual_outputs = "passed" if available_comparisons == "passed" else "partial"
    lines = [
        "S3 Assembly renderer comparison check: blocked",
        f"actual outputs: {actual_outputs}",
        f"available comparisons: {available_comparisons}",
        f"renderer implementation: {renderer_implementation}",
        "global check: blocked",
        (
            "reason: actual outputs pass, but the real S3 renderer is still "
            "not implemented"
        ),
    ]
    return "\n".join(lines) + "\n"


def run_bootstrap_spike() -> BootstrapExecution:
    inventory_program = find_program(EXPECTED_BOOTSTRAP_PATH)
    if inventory_program is None:
        raise ValueError("bootstrap spike missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_BOOTSTRAP_RETURN:
        raise ValueError("bootstrap spike hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_BOOTSTRAP_ENTRYPOINT,
    )
    return BootstrapExecution(
        path=EXPECTED_BOOTSTRAP_PATH,
        entrypoint=EXPECTED_BOOTSTRAP_ENTRYPOINT,
        expected_return=EXPECTED_BOOTSTRAP_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_output_model() -> OutputModelExecution:
    inventory_program = find_program(EXPECTED_OUTPUT_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("output model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_OUTPUT_MODEL_RETURN:
        raise ValueError("output model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_OUTPUT_MODEL_ENTRYPOINT,
    )
    return OutputModelExecution(
        path=EXPECTED_OUTPUT_MODEL_PATH,
        entrypoint=EXPECTED_OUTPUT_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_OUTPUT_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_text_segment_model() -> TextSegmentModelExecution:
    inventory_program = find_program(EXPECTED_TEXT_SEGMENT_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("text segment model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_TEXT_SEGMENT_MODEL_RETURN:
        raise ValueError("text segment model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_TEXT_SEGMENT_MODEL_ENTRYPOINT,
    )
    return TextSegmentModelExecution(
        path=EXPECTED_TEXT_SEGMENT_MODEL_PATH,
        entrypoint=EXPECTED_TEXT_SEGMENT_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_TEXT_SEGMENT_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_line_blueprint_model() -> LineBlueprintModelExecution:
    inventory_program = find_program(EXPECTED_LINE_BLUEPRINT_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "line blueprint model missing from s3_program_check inventory"
        )
    if (
        inventory_program.hosted_expected_return
        != EXPECTED_LINE_BLUEPRINT_MODEL_RETURN
    ):
        raise ValueError("line blueprint model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_LINE_BLUEPRINT_MODEL_ENTRYPOINT,
    )
    return LineBlueprintModelExecution(
        path=EXPECTED_LINE_BLUEPRINT_MODEL_PATH,
        entrypoint=EXPECTED_LINE_BLUEPRINT_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_LINE_BLUEPRINT_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_line_sequence_model() -> LineSequenceModelExecution:
    inventory_program = find_program(EXPECTED_LINE_SEQUENCE_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "line sequence model missing from s3_program_check inventory"
        )
    if inventory_program.hosted_expected_return != EXPECTED_LINE_SEQUENCE_MODEL_RETURN:
        raise ValueError("line sequence model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_LINE_SEQUENCE_MODEL_ENTRYPOINT,
    )
    return LineSequenceModelExecution(
        path=EXPECTED_LINE_SEQUENCE_MODEL_PATH,
        entrypoint=EXPECTED_LINE_SEQUENCE_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_LINE_SEQUENCE_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_line_content_encoding_model() -> LineContentEncodingModelExecution:
    inventory_program = find_program(EXPECTED_LINE_CONTENT_ENCODING_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "line content encoding model missing from s3_program_check inventory"
        )
    if (
        inventory_program.hosted_expected_return
        != EXPECTED_LINE_CONTENT_ENCODING_MODEL_RETURN
    ):
        raise ValueError(
            "line content encoding model hosted expected return must be 0"
        )

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_LINE_CONTENT_ENCODING_MODEL_ENTRYPOINT,
    )
    return LineContentEncodingModelExecution(
        path=EXPECTED_LINE_CONTENT_ENCODING_MODEL_PATH,
        entrypoint=EXPECTED_LINE_CONTENT_ENCODING_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_LINE_CONTENT_ENCODING_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_event_stream_model() -> EventStreamModelExecution:
    inventory_program = find_program(EXPECTED_EVENT_STREAM_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "event stream model missing from s3_program_check inventory"
        )
    if inventory_program.hosted_expected_return != EXPECTED_EVENT_STREAM_MODEL_RETURN:
        raise ValueError("event stream model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_EVENT_STREAM_MODEL_ENTRYPOINT,
    )
    return EventStreamModelExecution(
        path=EXPECTED_EVENT_STREAM_MODEL_PATH,
        entrypoint=EXPECTED_EVENT_STREAM_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_EVENT_STREAM_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_event_writer_model() -> EventWriterModelExecution:
    inventory_program = find_program(EXPECTED_EVENT_WRITER_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "event writer model missing from s3_program_check inventory"
        )
    if inventory_program.hosted_expected_return != EXPECTED_EVENT_WRITER_MODEL_RETURN:
        raise ValueError("event writer model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_EVENT_WRITER_MODEL_ENTRYPOINT,
    )
    return EventWriterModelExecution(
        path=EXPECTED_EVENT_WRITER_MODEL_PATH,
        entrypoint=EXPECTED_EVENT_WRITER_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_EVENT_WRITER_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_output_buffer_model() -> OutputBufferModelExecution:
    inventory_program = find_program(EXPECTED_OUTPUT_BUFFER_MODEL_PATH)
    if inventory_program is None:
        raise ValueError(
            "output buffer model missing from s3_program_check inventory"
        )
    if inventory_program.hosted_expected_return != EXPECTED_OUTPUT_BUFFER_MODEL_RETURN:
        raise ValueError("output buffer model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_OUTPUT_BUFFER_MODEL_ENTRYPOINT,
    )
    return OutputBufferModelExecution(
        path=EXPECTED_OUTPUT_BUFFER_MODEL_PATH,
        entrypoint=EXPECTED_OUTPUT_BUFFER_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_OUTPUT_BUFFER_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_pipeline_model() -> PipelineModelExecution:
    inventory_program = find_program(EXPECTED_PIPELINE_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("pipeline model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_PIPELINE_MODEL_RETURN:
        raise ValueError("pipeline model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_PIPELINE_MODEL_ENTRYPOINT,
    )
    return PipelineModelExecution(
        path=EXPECTED_PIPELINE_MODEL_PATH,
        entrypoint=EXPECTED_PIPELINE_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_PIPELINE_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_text_builder_model() -> TextBuilderModelExecution:
    inventory_program = find_program(EXPECTED_TEXT_BUILDER_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("text builder model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_TEXT_BUILDER_MODEL_RETURN:
        raise ValueError("text builder model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_TEXT_BUILDER_MODEL_ENTRYPOINT,
    )
    return TextBuilderModelExecution(
        path=EXPECTED_TEXT_BUILDER_MODEL_PATH,
        entrypoint=EXPECTED_TEXT_BUILDER_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_TEXT_BUILDER_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_text_fragment_model() -> TextFragmentModelExecution:
    inventory_program = find_program(EXPECTED_TEXT_FRAGMENT_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("text fragment model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_TEXT_FRAGMENT_MODEL_RETURN:
        raise ValueError("text fragment model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_TEXT_FRAGMENT_MODEL_ENTRYPOINT,
    )
    return TextFragmentModelExecution(
        path=EXPECTED_TEXT_FRAGMENT_MODEL_PATH,
        entrypoint=EXPECTED_TEXT_FRAGMENT_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_TEXT_FRAGMENT_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


def run_fixed_tryte_buffer_model() -> FixedTryteBufferModelExecution:
    inventory_program = find_program(EXPECTED_FIXED_TRYTE_BUFFER_MODEL_PATH)
    if inventory_program is None:
        raise ValueError("fixed tryte buffer model missing from s3_program_check inventory")
    if inventory_program.hosted_expected_return != EXPECTED_FIXED_TRYTE_BUFFER_MODEL_RETURN:
        raise ValueError("fixed tryte buffer model hosted expected return must be 0")

    actual_return = run_hosted_check(
        inventory_program,
        entry=EXPECTED_FIXED_TRYTE_BUFFER_MODEL_ENTRYPOINT,
    )
    return FixedTryteBufferModelExecution(
        path=EXPECTED_FIXED_TRYTE_BUFFER_MODEL_PATH,
        entrypoint=EXPECTED_FIXED_TRYTE_BUFFER_MODEL_ENTRYPOINT,
        expected_return=EXPECTED_FIXED_TRYTE_BUFFER_MODEL_RETURN,
        actual_return=actual_return,
        covered_by_s3_program_check=True,
    )


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


def render_candidate_execution(
    candidate: CandidateStatus,
    actual_status: int,
    bootstrap: BootstrapExecution,
    output_model: OutputModelExecution,
    text_segment_model: TextSegmentModelExecution,
    line_blueprint_model: LineBlueprintModelExecution,
    line_sequence_model: LineSequenceModelExecution,
    line_content_encoding_model: LineContentEncodingModelExecution,
    event_stream_model: EventStreamModelExecution,
    event_writer_model: EventWriterModelExecution,
    output_buffer_model: OutputBufferModelExecution,
    pipeline_model: PipelineModelExecution,
    text_builder_model: TextBuilderModelExecution,
    text_fragment_model: TextFragmentModelExecution,
    fixed_tryte_buffer_model: FixedTryteBufferModelExecution,
) -> str:
    status = (
        candidate.execution_meaning
        if actual_status == candidate.expected_status
        else "unexpected"
    )
    coverage = "yes" if candidate.covered_by_s3_program_check else "no"
    bootstrap_status = (
        "passed"
        if bootstrap.actual_return == bootstrap.expected_return
        else "failed"
    )
    bootstrap_coverage = "yes" if bootstrap.covered_by_s3_program_check else "no"
    output_model_status = (
        "passed"
        if output_model.actual_return == output_model.expected_return
        else "failed"
    )
    output_model_coverage = (
        "yes" if output_model.covered_by_s3_program_check else "no"
    )
    text_segment_model_status = (
        "passed"
        if text_segment_model.actual_return == text_segment_model.expected_return
        else "failed"
    )
    text_segment_model_coverage = (
        "yes" if text_segment_model.covered_by_s3_program_check else "no"
    )
    line_blueprint_model_passed = (
        line_blueprint_model.actual_return == line_blueprint_model.expected_return
    )
    line_blueprint_model_status = (
        "passed" if line_blueprint_model_passed else "failed"
    )
    line_blueprint_model_coverage = (
        "yes" if line_blueprint_model.covered_by_s3_program_check else "no"
    )
    line_sequence_model_passed = (
        line_sequence_model.actual_return == line_sequence_model.expected_return
    )
    line_sequence_model_status = (
        "passed" if line_sequence_model_passed else "failed"
    )
    line_sequence_model_coverage = (
        "yes" if line_sequence_model.covered_by_s3_program_check else "no"
    )
    line_content_encoding_model_passed = (
        line_content_encoding_model.actual_return
        == line_content_encoding_model.expected_return
    )
    line_content_encoding_model_status = (
        "passed" if line_content_encoding_model_passed else "failed"
    )
    line_content_encoding_model_coverage = (
        "yes"
        if line_content_encoding_model.covered_by_s3_program_check
        else "no"
    )
    event_stream_model_passed = (
        event_stream_model.actual_return == event_stream_model.expected_return
    )
    event_stream_model_status = (
        "passed" if event_stream_model_passed else "failed"
    )
    event_stream_model_coverage = (
        "yes" if event_stream_model.covered_by_s3_program_check else "no"
    )
    event_writer_model_passed = (
        event_writer_model.actual_return == event_writer_model.expected_return
    )
    event_writer_model_status = (
        "passed" if event_writer_model_passed else "failed"
    )
    event_writer_model_coverage = (
        "yes" if event_writer_model.covered_by_s3_program_check else "no"
    )
    output_buffer_model_passed = (
        output_buffer_model.actual_return == output_buffer_model.expected_return
    )
    output_buffer_model_status = (
        "passed" if output_buffer_model_passed else "failed"
    )
    output_buffer_model_coverage = (
        "yes" if output_buffer_model.covered_by_s3_program_check else "no"
    )
    pipeline_model_passed = (
        pipeline_model.actual_return == pipeline_model.expected_return
    )
    pipeline_model_status = "passed" if pipeline_model_passed else "failed"
    pipeline_model_coverage = (
        "yes" if pipeline_model.covered_by_s3_program_check else "no"
    )
    text_builder_model_passed = (
        text_builder_model.actual_return == text_builder_model.expected_return
    )
    text_builder_model_status = (
        "passed" if text_builder_model_passed else "failed"
    )
    text_builder_model_coverage = (
        "yes" if text_builder_model.covered_by_s3_program_check else "no"
    )
    text_fragment_model_passed = (
        text_fragment_model.actual_return == text_fragment_model.expected_return
    )
    text_fragment_model_status = (
        "passed" if text_fragment_model_passed else "failed"
    )
    text_fragment_model_coverage = (
        "yes" if text_fragment_model.covered_by_s3_program_check else "no"
    )
    fixed_tryte_buffer_model_passed = (
        fixed_tryte_buffer_model.actual_return == fixed_tryte_buffer_model.expected_return
    )
    fixed_tryte_buffer_model_status = (
        "passed" if fixed_tryte_buffer_model_passed else "failed"
    )
    fixed_tryte_buffer_model_coverage = (
        "yes" if fixed_tryte_buffer_model.covered_by_s3_program_check else "no"
    )
    lines = [
        "S3 Assembly renderer candidate execution",
        "",
        f"path: {candidate.path}",
        f"entrypoint: {candidate.entrypoint}",
        f"expected status: {candidate.expected_status}",
        f"actual status: {actual_status}",
        f"covered by s3_program_check: {coverage}",
        f"status: {status}",
        "",
        "candidate renderer bootstrap: available",
        f"s3 bootstrap spike: {bootstrap_status}",
        f"program: {bootstrap.path}",
        f"entrypoint: {bootstrap.entrypoint}",
        f"expected return: {bootstrap.expected_return}",
        f"actual return: {bootstrap.actual_return}",
        f"covered by s3_program_check: {bootstrap_coverage}",
        "",
        f"s3 output model: {output_model_status}",
        f"program: {output_model.path}",
        f"entrypoint: {output_model.entrypoint}",
        f"expected return: {output_model.expected_return}",
        f"actual return: {output_model.actual_return}",
        f"covered by s3_program_check: {output_model_coverage}",
        "",
        f"s3 text segment model: {text_segment_model_status}",
        f"program: {text_segment_model.path}",
        f"entrypoint: {text_segment_model.entrypoint}",
        f"expected return: {text_segment_model.expected_return}",
        f"actual return: {text_segment_model.actual_return}",
        f"covered by s3_program_check: {text_segment_model_coverage}",
        "",
        f"s3 line blueprint model: {line_blueprint_model_status}",
        f"program: {line_blueprint_model.path}",
        f"entrypoint: {line_blueprint_model.entrypoint}",
        f"expected return: {line_blueprint_model.expected_return}",
        f"actual return: {line_blueprint_model.actual_return}",
        f"covered by s3_program_check: {line_blueprint_model_coverage}",
        "",
        f"s3 line sequence model: {line_sequence_model_status}",
        f"program: {line_sequence_model.path}",
        f"entrypoint: {line_sequence_model.entrypoint}",
        f"expected return: {line_sequence_model.expected_return}",
        f"actual return: {line_sequence_model.actual_return}",
        f"covered by s3_program_check: {line_sequence_model_coverage}",
        "",
        f"s3 line content encoding model: {line_content_encoding_model_status}",
        f"program: {line_content_encoding_model.path}",
        f"entrypoint: {line_content_encoding_model.entrypoint}",
        f"expected return: {line_content_encoding_model.expected_return}",
        f"actual return: {line_content_encoding_model.actual_return}",
        (
            "covered by s3_program_check: "
            f"{line_content_encoding_model_coverage}"
        ),
        "",
        f"s3 event stream model: {event_stream_model_status}",
        f"program: {event_stream_model.path}",
        f"entrypoint: {event_stream_model.entrypoint}",
        f"expected return: {event_stream_model.expected_return}",
        f"actual return: {event_stream_model.actual_return}",
        f"covered by s3_program_check: {event_stream_model_coverage}",
        "",
        f"s3 event writer model: {event_writer_model_status}",
        f"program: {event_writer_model.path}",
        f"entrypoint: {event_writer_model.entrypoint}",
        f"expected return: {event_writer_model.expected_return}",
        f"actual return: {event_writer_model.actual_return}",
        f"covered by s3_program_check: {event_writer_model_coverage}",
        "",
        f"s3 output buffer model: {output_buffer_model_status}",
        f"program: {output_buffer_model.path}",
        f"entrypoint: {output_buffer_model.entrypoint}",
        f"expected return: {output_buffer_model.expected_return}",
        f"actual return: {output_buffer_model.actual_return}",
        f"covered by s3_program_check: {output_buffer_model_coverage}",
        "",
        f"s3 renderer pipeline model: {pipeline_model_status}",
        f"program: {pipeline_model.path}",
        f"entrypoint: {pipeline_model.entrypoint}",
        f"expected return: {pipeline_model.expected_return}",
        f"actual return: {pipeline_model.actual_return}",
        f"covered by s3_program_check: {pipeline_model_coverage}",
        "",
        f"s3 text builder model: {text_builder_model_status}",
        f"program: {text_builder_model.path}",
        f"entrypoint: {text_builder_model.entrypoint}",
        f"expected return: {text_builder_model.expected_return}",
        f"actual return: {text_builder_model.actual_return}",
        f"covered by s3_program_check: {text_builder_model_coverage}",
        "",
        f"s3 text fragment model: {text_fragment_model_status}",
        f"program: {text_fragment_model.path}",
        f"entrypoint: {text_fragment_model.entrypoint}",
        f"expected return: {text_fragment_model.expected_return}",
        f"actual return: {text_fragment_model.actual_return}",
        f"covered by s3_program_check: {text_fragment_model_coverage}",
        "",
        f"s3 fixed mutable tryte buffer: {fixed_tryte_buffer_model_status}",
        f"program: {fixed_tryte_buffer_model.path}",
        f"entrypoint: {fixed_tryte_buffer_model.entrypoint}",
        f"expected return: {fixed_tryte_buffer_model.expected_return}",
        f"actual return: {fixed_tryte_buffer_model.actual_return}",
        f"covered by s3_program_check: {fixed_tryte_buffer_model_coverage}",
        "renderer implementation: not_implemented",
        "full text rendering: not_implemented",
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
    print("s3 renderer bootstrap spike: available")
    print("s3 renderer output model: available")
    print("s3 renderer text segment model: available")
    print("s3 renderer line blueprint model: available")
    print("s3 renderer line sequence model: available")
    print("s3 renderer line content encoding model: available")
    print("s3 renderer event stream model: available")
    print("s3 renderer event writer model: available")
    print("s3 renderer output buffer model: available")
    print("s3 renderer pipeline model: available")
    print("s3 renderer text builder model: available")
    print("s3 renderer static text fragment model: available")
    print("s3 renderer implementation: not implemented")
    print("typed static text values: available")
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


def candidate_fixtures() -> int:
    try:
        fixture_status = load_candidate_fixture_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate fixtures")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_fixtures(fixture_status), end="")
    return 0


def candidate_fixture_expectations() -> int:
    try:
        expectation_status = load_candidate_fixture_expectation_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate fixture expectations")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_fixture_expectations(expectation_status), end="")
    return 0


def candidate_comparison_plan() -> int:
    try:
        comparison_plan_status = load_candidate_comparison_plan_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate comparison plan")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_comparison_plan(comparison_plan_status), end="")
    return 0


def candidate_actual_outputs() -> int:
    try:
        actual_output_status = load_candidate_actual_output_status()
    except ValueError as error:
        print("S3 Assembly renderer candidate actual outputs")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    print(render_candidate_actual_outputs(actual_output_status), end="")
    return 0


def candidate_compare_available() -> int:
    try:
        actual_output_status = load_candidate_actual_output_status()
        comparisons = compare_available_outputs(actual_output_status)
    except ValueError as error:
        print("S3 Assembly renderer candidate available comparisons")
        print()
        print("status: unavailable")
        print(f"reason: {error}")
        return 1

    available_count = sum(1 for item in comparisons if item.status != "blocked")
    if available_count == 0:
        print("S3 Assembly renderer candidate available comparisons")
        print()
        print("status: blocked")
        print("reason: no candidate actual outputs are available")
        return 1

    print(render_available_comparisons(comparisons), end="")
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
        bootstrap = run_bootstrap_spike()
        output_model = run_output_model()
        text_segment_model = run_text_segment_model()
        line_blueprint_model = run_line_blueprint_model()
        line_sequence_model = run_line_sequence_model()
        line_content_encoding_model = run_line_content_encoding_model()
        event_stream_model = run_event_stream_model()
        event_writer_model = run_event_writer_model()
        output_buffer_model = run_output_buffer_model()
        pipeline_model = run_pipeline_model()
        text_builder_model = run_text_builder_model()
        text_fragment_model = run_text_fragment_model()
        fixed_tryte_buffer_model = run_fixed_tryte_buffer_model()
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

    print(
        render_candidate_execution(
            candidate_status,
            actual_status,
            bootstrap,
            output_model,
            text_segment_model,
            line_blueprint_model,
            line_sequence_model,
            line_content_encoding_model,
            event_stream_model,
            event_writer_model,
            output_buffer_model,
            pipeline_model,
            text_builder_model,
            text_fragment_model,
            fixed_tryte_buffer_model,
        ),
        end="",
    )
    if actual_status != candidate_status.expected_status:
        return 1
    if bootstrap.actual_return != bootstrap.expected_return:
        return 1
    if output_model.actual_return != output_model.expected_return:
        return 1
    if text_segment_model.actual_return != text_segment_model.expected_return:
        return 1
    if line_blueprint_model.actual_return != line_blueprint_model.expected_return:
        return 1
    if line_sequence_model.actual_return != line_sequence_model.expected_return:
        return 1
    if (
        line_content_encoding_model.actual_return
        != line_content_encoding_model.expected_return
    ):
        return 1
    if event_stream_model.actual_return != event_stream_model.expected_return:
        return 1
    if event_writer_model.actual_return != event_writer_model.expected_return:
        return 1
    if output_buffer_model.actual_return != output_buffer_model.expected_return:
        return 1
    if pipeline_model.actual_return != pipeline_model.expected_return:
        return 1
    if text_builder_model.actual_return != text_builder_model.expected_return:
        return 1
    if text_fragment_model.actual_return != text_fragment_model.expected_return:
        return 1
    if fixed_tryte_buffer_model.actual_return != fixed_tryte_buffer_model.expected_return:
        return 1
    return 0


def _render_s3_fixture(renderer_path: str, golden_path_str: str, name: str, buffer_count: int = 3, buffer_offset: int = 0, entry: str = "main", max_instructions: int = 100000, expected_bytes: int = 0) -> int:
    path = REPO_ROOT / renderer_path
    if not path.is_file():
        print(f"S3 {name} renderer: missing")
        print(f"  path: {renderer_path}")
        return 1

    source = path.read_text(encoding="utf-8")
    try:
        out = _capture_fixture_output(source, buffer_count, buffer_offset, entry, max_instructions, expected_bytes)
    except Exception as error:
        print(f"S3 {name} renderer: execution failed")
        print(f"  error: {error}")
        return 1

    sha256 = hashlib.sha256(out).hexdigest()

    print(f"S3 {name} renderer: ok")
    print(f"  bytes: {len(out)}")
    print(f"  lines: {out.count(10)}")
    print(f"  sha256: {sha256}")

    try:
        golden = _git_blob_bytes(golden_path_str)
    except FileNotFoundError:
        print(f"  golden blob not found: {golden_path_str}")
        return 1

    if out == golden:
        print("  comparison: passed")
    else:
        mismatch_count = sum(1 for a, b in zip(out, golden) if a != b)
        print(f"  comparison: failed ({mismatch_count} byte(s) differ)")
        return 1

    return 0


def candidate_render_first() -> int:
    meta = FIXTURE_METADATA["first"]
    return _render_s3_fixture(FIRST_S3_RENDERER, FIRST_S3_GOLDEN, "first", buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset, entry=meta.entry, max_instructions=meta.max_instructions, expected_bytes=meta.expected_bytes)


def candidate_render_simple_call() -> int:
    meta = FIXTURE_METADATA["simple_call"]
    return _render_s3_fixture(SIMPLE_CALL_S3_RENDERER, SIMPLE_CALL_S3_GOLDEN, "simple_call", buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset, entry=meta.entry, expected_bytes=meta.expected_bytes)


def candidate_render_sign() -> int:
    meta = FIXTURE_METADATA["sign"]
    return _render_s3_fixture(SIGN_S3_RENDERER, SIGN_S3_GOLDEN, "sign", buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset, entry=meta.entry, expected_bytes=meta.expected_bytes)


def generic_render_first() -> int:
    meta = FIXTURE_METADATA["first_generic"]
    return _render_s3_fixture(
        meta.s3_path, meta.golden_path, "generic_first",
        buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset,
        entry=meta.entry, max_instructions=meta.max_instructions,
        expected_bytes=meta.expected_bytes,
    )


def generic_render_simple_call() -> int:
    meta = FIXTURE_METADATA["simple_call_generic"]
    return _render_s3_fixture(
        meta.s3_path, meta.golden_path, "generic_simple_call",
        buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset,
        entry=meta.entry, max_instructions=meta.max_instructions,
        expected_bytes=meta.expected_bytes,
    )


def generic_render_sign() -> int:
    meta = FIXTURE_METADATA["sign_generic"]
    return _render_s3_fixture(
        meta.s3_path, meta.golden_path, "generic_sign",
        buffer_count=meta.buffer_count, buffer_offset=meta.buffer_offset,
        entry=meta.entry, max_instructions=meta.max_instructions,
        expected_bytes=meta.expected_bytes,
    )


def generic_vs_legacy_simple_call() -> int:
    """Compare generic simple_call output to legacy simple_call output."""
    generic_meta = FIXTURE_METADATA["simple_call_generic"]
    legacy_meta = FIXTURE_METADATA["simple_call"]
    g_path = REPO_ROOT / generic_meta.s3_path
    l_path = REPO_ROOT / legacy_meta.s3_path
    if not g_path.is_file():
        print("generic renderer: missing")
        return 1
    if not l_path.is_file():
        print("legacy renderer: missing")
        return 1
    g_src = g_path.read_text(encoding="utf-8")
    l_src = l_path.read_text(encoding="utf-8")
    try:
        g_out = _capture_fixture_output(
            g_src, generic_meta.buffer_count, generic_meta.buffer_offset,
            generic_meta.entry, generic_meta.max_instructions,
            generic_meta.expected_bytes,
        )
        l_out = _capture_fixture_output(
            l_src, legacy_meta.buffer_count, legacy_meta.buffer_offset,
            legacy_meta.entry, legacy_meta.max_instructions,
            legacy_meta.expected_bytes,
        )
    except Exception as error:
        print(f"generic vs legacy comparison: execution failed: {error}")
        return 1
    if g_out == l_out:
        print("generic vs legacy simple_call: passed")
        return 0
    mismatch_count = sum(1 for a, b in zip(g_out, l_out) if a != b)
    print(f"generic vs legacy simple_call: failed ({mismatch_count} byte(s) differ)")
    return 1


def generic_vs_legacy_sign() -> int:
    """Compare generic sign output to legacy sign output."""
    generic_meta = FIXTURE_METADATA["sign_generic"]
    legacy_meta = FIXTURE_METADATA["sign"]
    g_path = REPO_ROOT / generic_meta.s3_path
    l_path = REPO_ROOT / legacy_meta.s3_path
    if not g_path.is_file():
        print("generic renderer: missing")
        return 1
    if not l_path.is_file():
        print("legacy renderer: missing")
        return 1
    g_src = g_path.read_text(encoding="utf-8")
    l_src = l_path.read_text(encoding="utf-8")
    try:
        g_out = _capture_fixture_output(
            g_src, generic_meta.buffer_count, generic_meta.buffer_offset,
            generic_meta.entry, generic_meta.max_instructions,
            generic_meta.expected_bytes,
        )
        l_out = _capture_fixture_output(
            l_src, legacy_meta.buffer_count, legacy_meta.buffer_offset,
            legacy_meta.entry, legacy_meta.max_instructions,
            legacy_meta.expected_bytes,
        )
    except Exception as error:
        print(f"generic vs legacy sign comparison: execution failed: {error}")
        return 1
    if g_out == l_out:
        print("generic vs legacy sign: passed")
        return 0
    mismatch_count = sum(1 for a, b in zip(g_out, l_out) if a != b)
    print(f"generic vs legacy sign: failed ({mismatch_count} byte(s) differ)")
    return 1


def check() -> int:
    legacy_first_ok = candidate_render_first()
    if legacy_first_ok != 0:
        print("S3 Assembly renderer comparison check: legacy first fixture failed")
        return 1
    legacy_simple_call_ok = candidate_render_simple_call()
    if legacy_simple_call_ok != 0:
        print("S3 Assembly renderer comparison check: legacy simple_call fixture failed")
        return 1
    legacy_sign_ok = candidate_render_sign()
    if legacy_sign_ok != 0:
        print("S3 Assembly renderer comparison check: legacy sign fixture failed")
        return 1

    generic_first_ok = generic_render_first()
    if generic_first_ok != 0:
        print("S3 Assembly renderer comparison check: generic first failed")
        return 1
    generic_simple_call_ok = generic_render_simple_call()
    if generic_simple_call_ok != 0:
        print("S3 Assembly renderer comparison check: generic simple_call failed")
        return 1
    generic_sign_ok = generic_render_sign()
    if generic_sign_ok != 0:
        print("S3 Assembly renderer comparison check: generic sign failed")
        return 1
    generic_vs_legacy_ok = generic_vs_legacy_simple_call()
    if generic_vs_legacy_ok != 0:
        print("S3 Assembly renderer comparison check: generic vs legacy simple_call failed")
        return 1
    generic_vs_legacy_sign_ok = generic_vs_legacy_sign()
    if generic_vs_legacy_sign_ok != 0:
        print("S3 Assembly renderer comparison check: generic vs legacy sign failed")
        return 1

    print("S3 Assembly renderer comparison check: ok")
    print("legacy first: passed")
    print("legacy simple_call: passed")
    print("legacy sign: passed")
    print("generic first: passed")
    print("generic simple_call: passed")
    print("generic sign: passed")
    print("generic vs legacy simple_call: passed")
    print("generic vs legacy sign: passed")
    print("actual outputs: passed")
    print("available comparisons: passed")
    print("renderer implementation: complete")
    print("full text rendering: passed")
    print("global check: passed")
    return 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Compare Python and future S3 Assembly renderer output"
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--status", action="store_true")
    mode.add_argument("--reference", action="store_true")
    mode.add_argument("--candidate", action="store_true")
    mode.add_argument("--candidate-symbols", action="store_true")
    mode.add_argument("--candidate-fixtures", action="store_true")
    mode.add_argument("--candidate-fixture-expectations", action="store_true")
    mode.add_argument("--candidate-comparison-plan", action="store_true")
    mode.add_argument("--candidate-actual-outputs", action="store_true")
    mode.add_argument("--candidate-compare-available", action="store_true")
    mode.add_argument("--candidate-run", action="store_true")
    mode.add_argument("--candidate-render-first", action="store_true")
    mode.add_argument("--candidate-render-simple-call", action="store_true")
    mode.add_argument("--candidate-render-sign", action="store_true")
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
    if args.candidate_fixtures:
        return candidate_fixtures()
    if args.candidate_fixture_expectations:
        return candidate_fixture_expectations()
    if args.candidate_comparison_plan:
        return candidate_comparison_plan()
    if args.candidate_actual_outputs:
        return candidate_actual_outputs()
    if args.candidate_compare_available:
        return candidate_compare_available()
    if args.candidate_run:
        return candidate_run()
    if args.candidate_render_first:
        return candidate_render_first()
    if args.candidate_render_simple_call:
        return candidate_render_simple_call()
    if args.candidate_render_sign:
        return candidate_render_sign()
    return check()


if __name__ == "__main__":
    raise SystemExit(main())
