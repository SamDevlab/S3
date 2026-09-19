from __future__ import annotations

import pytest

from bootstrap.s3.compiler_substrate import SourceBundle
from bootstrap.s3.frontend_control_plane import (
    frontend_control_plane_ready_for_semantic,
    ingest_source_frontend,
)
from bootstrap.s3.frontend_registration import build_registration_plan
from bootstrap.s3.frontend_types import FrontendTypeError, resolve_frontend_types
from bootstrap.s3.source_frontend import parse_source_bundle_independent
from bootstrap.s3.whole_program import (
    PhaseKind,
    ProgramRegistry,
    SemanticState,
    TypeArena,
    TypeKind,
    WholeProgramContext,
)


def _resolve(source_files: tuple[tuple[str, str], ...]):
    frontend = parse_source_bundle_independent(SourceBundle(source_files))
    plan = build_registration_plan(frontend)
    registry = ProgramRegistry()
    registry.register(plan.modules)
    types = TypeArena()
    semantic = SemanticState(registry, types)
    result = resolve_frontend_types(frontend, plan, registry, types, semantic)
    return frontend, plan, registry, types, semantic, result


def test_frontend_type_phase_resolves_function_signature_primitives() -> None:
    _, _, registry, types, semantic, result = _resolve(
        (
            (
                "main.s3",
                """\
module main
fn add(left: i64, right: i64) -> i64:
    return left + right
fn main() -> i64:
    return add(1, 2)
""",
            ),
        )
    )

    assert len(result.function_signatures) == 2
    i64 = types.primitive(TypeKind.I64)
    add = next(
        signature
        for signature in result.function_signatures
        if len(signature.parameter_type_ids) == 2
    )
    assert add.parameter_type_ids == (i64, i64)
    assert add.result_type_ids == (i64,)
    assert len(tuple(semantic.signatures.items())) == 2
    assert len(tuple(registry.functions.items())) == 2


def test_frontend_type_phase_canonicalizes_arrays_references_and_closed_vectors() -> None:
    _, _, _, types, _, result = _resolve(
        (
            (
                "main.s3",
                """\
module main
fn use(values: i64[3], shared: &i64, items: i64_vector) -> i64:
    return 0
fn main() -> i64:
    return 0
""",
            ),
        )
    )

    signature = next(
        item for item in result.function_signatures if len(item.parameter_type_ids) == 3
    )
    array, reference, vector = (
        types.get(type_id) for type_id in signature.parameter_type_ids
    )
    assert array.kind is TypeKind.ARRAY
    assert array.array_length == 3
    assert reference.kind is TypeKind.REFERENCE
    assert reference.mutable is False
    assert vector.kind is TypeKind.VECTOR


def test_frontend_type_phase_resolves_local_and_imported_nominals() -> None:
    _, _, registry, types, _, result = _resolve(
        (
            (
                "types.s3",
                """\
module types
export record Point:
    x: i64
fn main() -> i64:
    return 0
""",
            ),
            (
                "main.s3",
                """\
module main
from types import Point
fn consume(value: Point) -> i64:
    return value.x
fn main() -> i64:
    return 0
""",
            ),
        )
    )

    consume = next(
        item for item in result.function_signatures if len(item.parameter_type_ids) == 1
    )
    parameter = types.get(consume.parameter_type_ids[0])
    assert parameter.kind is TypeKind.RECORD
    assert parameter.nominal_declaration_id is not None
    nominal = registry.nominal_types.get(int(parameter.nominal_declaration_id))
    assert nominal.kind is TypeKind.RECORD


def test_frontend_type_phase_builds_owner_sensitive_type_parameters_and_instantiations() -> None:
    _, _, _, types, _, result = _resolve(
        (
            (
                "generic.s3",
                """\
module generic
record Box<T: value>:
    value: T
fn identity<T: value>(value: T) -> T:
    return value
fn take(value: Box<i64>) -> i64:
    return value.value
fn main() -> i64:
    return 0
""",
            ),
        )
    )

    parameter_rows = result.type_parameters
    assert len(parameter_rows) == 2
    assert {row[0] for row in parameter_rows} == {"nominal", "function"}
    assert parameter_rows[0][3] != parameter_rows[1][3]

    instantiated = [
        info
        for _, info in types.types.items()
        if info.kind is TypeKind.INSTANTIATED
    ]
    assert len(instantiated) == 1
    assert tuple(instantiated[0].type_arguments) == (
        types.primitive(TypeKind.I64),
    )


def test_frontend_type_phase_resolves_record_and_enum_payload_types() -> None:
    _, _, _, types, _, result = _resolve(
        (
            (
                "types.s3",
                """\
module types
record Pair:
    left: i64
    right: &mut i64
enum Choice:
    None
    Some(value: i64)
fn main() -> i64:
    return 0
""",
            ),
        )
    )

    assert len(result.fields) == 2
    assert {types.get(row.type_id).kind for row in result.fields} == {
        TypeKind.I64,
        TypeKind.REFERENCE,
    }
    some = next(row for row in result.variants if row.type_ids)
    assert some.type_ids == (types.primitive(TypeKind.I64),)


def test_frontend_type_phase_rejects_unknown_nominal_and_rolls_back() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "main.s3",
                    """\
module main
fn bad(value: Missing) -> i64:
    return 0
fn main() -> i64:
    return 0
""",
                ),
            )
        )
    )
    primitive_count = len(tuple(context.types.types.items()))

    result = ingest_source_frontend(context)

    assert result.success is False
    assert "TYPE:FAILED" in result.phase_trace
    assert result.diagnostics
    assert result.diagnostics[0].code == "S3E_TYPE_UNKNOWN"
    assert len(tuple(context.types.types.items())) == primitive_count
    assert len(tuple(context.semantic.signatures.items())) == 0
    assert context.semantic.node_types == {}


def test_frontend_type_phase_rejects_generic_argument_arity() -> None:
    with pytest.raises(FrontendTypeError, match="expects 1 type arguments"):
        _resolve(
            (
                (
                    "main.s3",
                    """\
module main
record Box<T: value>:
    value: T
fn bad(value: Box<i64, i64>) -> i64:
    return 0
fn main() -> i64:
    return 0
""",
                ),
            )
        )


def test_control_plane_commits_type_and_stops_before_semantic() -> None:
    context = WholeProgramContext(
        SourceBundle(
            (
                (
                    "main.s3",
                    "module main\nfn main() -> i64:\n    return 0\n",
                ),
            )
        )
    )
    result = ingest_source_frontend(context)

    assert result.success
    assert result.type_resolution is not None
    assert result.next_phase is PhaseKind.SEMANTIC
    assert result.phase_trace == (
        "INPUT:COMMITTED",
        "SYNTAX:COMMITTED",
        "REGISTRATION:COMMITTED",
        "TYPE:COMMITTED",
    )
    assert frontend_control_plane_ready_for_semantic(result)
