from __future__ import annotations

import pytest

from bootstrap.s3.compiler_substrate import SourceBundle
from bootstrap.s3.frontend_registration import build_registration_plan
from bootstrap.s3.source_frontend import parse_source_bundle_independent
from bootstrap.s3.whole_program import ProgramRegistry, RegistrationError, TypeKind


def _registered(source_files: tuple[tuple[str, str], ...]):
    frontend = parse_source_bundle_independent(SourceBundle(source_files))
    plan = build_registration_plan(frontend)
    registry = ProgramRegistry()
    modules = registry.register(plan.modules)
    return frontend, plan, registry, modules


def test_frontend_registration_projects_modules_functions_types_imports_exports() -> None:
    _, plan, registry, modules = _registered(
        (
            (
                "a.s3",
                """\
module a
export record Box:
    value: i64
export fn value() -> i64:
    return 1
fn main() -> i64:
    return value()
""",
            ),
            (
                "b.s3",
                """\
module b
from a import value
record Local:
    value: i64
fn main() -> i64:
    return value()
""",
            ),
        )
    )

    assert len(modules) == 2
    assert len(tuple(registry.functions.items())) == 4
    assert len(tuple(registry.nominal_types.items())) == 2
    assert len(tuple(registry.imports.items())) == 1
    assert len(tuple(registry.exports.items())) == 2

    nominal_records = tuple(record for _, record in registry.nominal_types.items())
    assert {record.kind for record in nominal_records} == {TypeKind.RECORD}
    assert all(record.field_range.count == 1 for record in nominal_records)

    assert plan.synthetic_symbol_first == len(plan.symbol_names)


def test_nominal_field_ranges_are_scoped_per_type_not_per_module() -> None:
    _, _, registry, _ = _registered(
        (
            (
                "types.s3",
                """\
module types
record Left:
    value: i64
record Right:
    value: i64
fn main() -> i64:
    return 0
""",
            ),
        )
    )

    records = tuple(record for _, record in registry.nominal_types.items())
    assert len(records) == 2
    assert records[0].field_range.count == 1
    assert records[1].field_range.count == 1
    assert records[0].field_range.first != records[1].field_range.first


def test_frontend_registration_uses_deterministic_synthetic_module_for_unnamed_file() -> None:
    frontend = parse_source_bundle_independent(
        SourceBundle(
            (
                (
                    "main.s3",
                    "fn main() -> i64:\n    return 0\n",
                ),
            )
        )
    )
    plan = build_registration_plan(frontend)
    assert len(plan.modules) == 1
    module = plan.modules[0]
    assert plan.symbol_names[module.module_symbol_id] == "main"


def test_duplicate_record_fields_fail_closed_at_registration() -> None:
    frontend = parse_source_bundle_independent(
        SourceBundle(
            (
                (
                    "dup.s3",
                    """\
module dup
record Bad:
    value: i64
    value: i64
fn main() -> i64:
    return 0
""",
                ),
            )
        )
    )
    plan = build_registration_plan(frontend)
    with pytest.raises(RegistrationError, match="duplicate record field"):
        ProgramRegistry().register(plan.modules)


def test_duplicate_enum_variants_fail_closed_at_registration() -> None:
    frontend = parse_source_bundle_independent(
        SourceBundle(
            (
                (
                    "dup_enum.s3",
                    """\
module dup_enum
enum Bad:
    Same
    Same
fn main() -> i64:
    return 0
""",
                ),
            )
        )
    )
    plan = build_registration_plan(frontend)
    with pytest.raises(RegistrationError, match="duplicate enum variant"):
        ProgramRegistry().register(plan.modules)