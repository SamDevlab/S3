from __future__ import annotations

from dataclasses import replace
import json
import platform
from pathlib import Path
import subprocess
import sys

import pytest

from bootstrap.s3 import compile_program, compile_source, run_source
from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.compiler_substrate import OutputSink, SourceBundle
from bootstrap.s3.generic_ir import IRBuilder, IROpcode, IRType
from bootstrap.s3.generic_syntax import DeclarationPayload, FunctionPayload, NodeKind, SyntaxArena, SyntaxSpan
from bootstrap.s3.whole_program import (
    ExportSpec,
    FieldSpec,
    FunctionSpec,
    ImportSpec,
    ModuleSpec,
    NominalTypeSpec,
    PhaseKind,
    PhaseOrchestrator,
    PreparedProgramArtifacts,
    ProgramRegistry,
    RegistrationError,
    SemanticSeed,
    SemanticState,
    TypeArena,
    TypeArenaError,
    TypeKind,
    TypeSpec,
    WholeProgramContext,
)


def _syntax() -> SyntaxArena:
    arena = SyntaxArena(symbol_count=8, type_count=8)
    function = arena.append_node(
        NodeKind.FUNCTION,
        SyntaxSpan(0, 0, 3),
        payload=FunctionPayload(symbol_id=1, return_type_id=2, body_id=-1),
    )
    record = arena.append_node(
        NodeKind.RECORD_DECLARATION,
        SyntaxSpan(0, 4, 10),
        payload=DeclarationPayload(symbol_id=2, type_id=-1),
    )
    root = arena.append_node(
        NodeKind.PROGRAM,
        SyntaxSpan(0, 0, 10),
        children=(function, record),
    )
    arena.set_root(root)
    arena.validate()
    return arena


def _modules() -> tuple[ModuleSpec, ...]:
    return (
        ModuleSpec(
            module_symbol_id=10,
            source_file_id=0,
            root_node_id=2,
            functions=(FunctionSpec(1, 0, ordinal=0, exported=True),),
            nominal_types=(NominalTypeSpec(2, 1, TypeKind.RECORD, fields=(FieldSpec(3, 2),)),),
            exports=(ExportSpec(1), ExportSpec(2, "type")),
        ),
        ModuleSpec(
            module_symbol_id=20,
            source_file_id=1,
            root_node_id=2,
            functions=(FunctionSpec(4, 0, ordinal=0),),
            imports=(ImportSpec(10, 1, alias_symbol_id=5),),
        ),
    )


def _ir() -> object:
    builder = IRBuilder()
    builder.begin_function(1, "entry", (IRType.I64,))
    value = builder.allocate_value(IRType.I64)
    builder.begin_block(1)
    builder.append_instruction(IROpcode.CONST, result_ids=(value,), immediate=7)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value,))
    builder.finish_block()
    builder.finish_function()
    return builder.program


def test_program_registry_is_deterministic_and_explicitly_indexed() -> None:
    left = ProgramRegistry()
    right = ProgramRegistry()
    left.register(_modules())
    right.register(tuple(reversed(_modules())))
    assert left.structural_digest() == right.structural_digest()
    assert tuple(left.modules.items()) == tuple(right.modules.items())
    assert tuple(left.functions.items()) == tuple(right.functions.items())
    assert tuple(left.nominal_types.items()) == tuple(right.nominal_types.items())
    assert left.modules.get(0).function_range.count == 1
    assert left.modules.get(0).nominal_type_range.count == 1
    assert left.functions.get(0).parameter_range.count == 0


def test_registration_failure_rolls_back_all_tables() -> None:
    registry = ProgramRegistry()
    registry.register((_modules()[0],))
    before = registry.structural_digest()
    with pytest.raises(RegistrationError):
        registry.register((_modules()[0],))
    assert registry.structural_digest() == before
    assert len(tuple(registry.modules.items())) == 1
    assert len(tuple(registry.functions.items())) == 1


def test_type_arena_canonicalizes_structural_and_nominal_types_transactionally() -> None:
    arena = TypeArena()
    i64 = arena.primitive(TypeKind.I64)
    array = arena.intern(TypeSpec(TypeKind.ARRAY, element_type_id=i64, array_length=4))
    assert arena.intern(TypeSpec(TypeKind.ARRAY, element_type_id=i64, array_length=4)) == array
    checkpoint = arena.checkpoint()
    reference = arena.intern(TypeSpec(TypeKind.REFERENCE, element_type_id=array, mutable=True))
    assert arena.get(reference).element_type_id == array
    arena.rollback(checkpoint)
    with pytest.raises(Exception):
        arena.get(reference)
    assert arena.intern(TypeSpec(TypeKind.ARRAY, element_type_id=i64, array_length=4)) == array


def test_type_arena_rejects_invalid_structural_identity() -> None:
    with pytest.raises(TypeArenaError):
        TypeArena().intern(TypeSpec(TypeKind.ARRAY, element_type_id=999, array_length=-1))


def test_type_parameter_identity_distinguishes_function_and_nominal_owners() -> None:
    arena = TypeArena()
    function_parameter = arena.intern(
        TypeSpec(
            TypeKind.TYPE_PARAMETER,
            owner_id=0,
            parameter_ordinal=0,
            owner_kind="function",
            name="T",
        )
    )
    nominal_parameter = arena.intern(
        TypeSpec(
            TypeKind.TYPE_PARAMETER,
            owner_id=0,
            parameter_ordinal=0,
            owner_kind="nominal",
            name="T",
        )
    )
    assert function_parameter != nominal_parameter
    assert arena.get(function_parameter).owner_kind == "function"
    assert arena.get(nominal_parameter).owner_kind == "nominal"


def test_type_parameter_rejects_missing_owner_kind() -> None:
    with pytest.raises(TypeArenaError, match="owner kind"):
        TypeArena().intern(
            TypeSpec(
                TypeKind.TYPE_PARAMETER,
                owner_id=0,
                parameter_ordinal=0,
                name="T",
            )
        )


def test_semantic_state_keeps_explicit_associations_and_rolls_back() -> None:
    registry = ProgramRegistry()
    registry.register((_modules()[0],))
    types = TypeArena()
    semantic = SemanticState(registry, types)
    scope = semantic.new_scope()
    declaration = semantic.declare(3, scope, types.primitive(TypeKind.I64), mutable=True)
    checkpoint = semantic.checkpoint()
    semantic.associate_node_type(41, types.primitive(TypeKind.I64))
    semantic.associate_call(42, 0)
    assert semantic.node_types[41] == types.primitive(TypeKind.I64)
    assert semantic.call_targets[42] == 0
    semantic.rollback(checkpoint)
    assert 41 not in semantic.node_types
    assert 42 not in semantic.call_targets
    assert semantic.declarations.get(declaration).mutable is True


def test_phase_state_machine_rejects_invalid_order_and_records_trace() -> None:
    from bootstrap.s3.whole_program import DiagnosticArena, PhaseTransitionError

    phases = PhaseOrchestrator(DiagnosticArena())
    with pytest.raises(PhaseTransitionError):
        phases.begin(PhaseKind.TYPE)
    phases.begin(PhaseKind.INPUT)
    phases.commit()
    phases.begin(PhaseKind.SYNTAX)
    phases.skip("prepared syntax is supplied by the caller")
    assert phases.trace() == ("INPUT:COMMITTED", "SYNTAX:SKIPPED")


def test_composition_root_orchestrates_prepared_artifacts_without_fake_frontend() -> None:
    sources = SourceBundle((("b.s3", "b"), ("a.s3", "a")))
    sink = OutputSink(64)
    artifacts = PreparedProgramArtifacts(
        syntax=_syntax(),
        modules=_modules(),
        type_specs=(TypeSpec(TypeKind.ARRAY, element_type_id=2, array_length=3),),
        ir=_ir(),
        output=b"TEST_ARTIFACT_OUTPUT",
    )
    result = compile_program(sources, sink, prepared_artifacts=artifacts)
    assert result.success is True
    assert result.test_artifact_input is True
    assert result.output == b"TEST_ARTIFACT_OUTPUT"
    assert result.diagnostics == ()
    assert result.phase_trace == (
        "INPUT:COMMITTED", "SYNTAX:COMMITTED", "REGISTRATION:COMMITTED",
        "TYPE:COMMITTED", "SEMANTIC:COMMITTED", "LOWERING:SKIPPED",
        "VERIFICATION:COMMITTED", "EMITTER:SKIPPED", "OUTPUT:COMMITTED",
        "FINALIZE:COMMITTED",
    )
    assert result.structural_digest


def test_compile_program_runs_real_frontend_then_fails_closed_at_type_phase() -> None:
    result = compile_program(
        SourceBundle(
            (
                (
                    "main.s3",
                    "module main\nfn main() -> i64:\n    return 0\n",
                ),
            )
        ),
        OutputSink(32),
    )
    assert result.success is False
    assert result.test_artifact_input is False
    assert result.output == b""
    assert result.diagnostics[0].code == "S3E_TYPE_PHASE_UNAVAILABLE"
    assert result.phase_trace[:4] == (
        "INPUT:COMMITTED",
        "SYNTAX:COMMITTED",
        "REGISTRATION:COMMITTED",
        "TYPE:FAILED",
    )
    assert "SEMANTIC:SKIPPED" in result.phase_trace


def test_s3_whole_program_components_are_ordinary_representability_artifacts() -> None:
    repository = Path(__file__).parents[1]
    for relative in (
        "selfhost/substrate/program_registry.s3",
        "selfhost/substrate/type_arena.s3",
        "selfhost/substrate/phase_orchestrator.s3",
        "selfhost/substrate/diagnostic_arena.s3",
        "selfhost/substrate/whole_program_context.s3",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        assert compile_source(source + "\nfn main() -> i64:\n    return 0\n").assembly.functions


def test_malformed_ir_is_rejected_and_output_is_not_published() -> None:
    sources = SourceBundle((("main.s3", "prepared"),))
    ir = _ir()
    instruction = ir.instructions.get(1)
    ir.instructions._items[1] = replace(instruction, operand_range=replace(instruction.operand_range, first=999))
    result = WholeProgramContext(sources, output_capacity=64).compose(
        PreparedProgramArtifacts(_syntax(), (_modules()[0],), ir=ir, output=b"must-not-publish")
    )
    assert result.success is False
    assert result.output == b""
    assert result.diagnostics[0].code == "invalid_sequence_range"


def test_output_capacity_failure_rolls_back_sink() -> None:
    result = WholeProgramContext(SourceBundle((("main.s3", "prepared"),)), output_capacity=3).compose(
        PreparedProgramArtifacts(_syntax(), (_modules()[0],), ir=_ir(), output=b"too-large")
    )
    assert result.success is False
    assert result.output == b""
    assert result.diagnostics[0].code == "S3E_OUTPUT_CAPACITY"


def test_same_logical_composition_has_stable_digest_across_sessions() -> None:
    source = SourceBundle((("main.s3", "prepared"),))
    artifacts = PreparedProgramArtifacts(_syntax(), (_modules()[0],), ir=_ir(), output=b"stable")
    first = WholeProgramContext(source).compose(artifacts)
    second = WholeProgramContext(source).compose(artifacts)
    assert first.structural_digest == second.structural_digest
    assert first.phase_trace == second.phase_trace


@pytest.mark.parametrize("case", range(256))
def test_composition_corpus_is_generic_and_deterministic(case: int) -> None:
    category = case // 64
    module = ModuleSpec(
        module_symbol_id=case + 100,
        source_file_id=case,
        root_node_id=case,
        functions=(FunctionSpec(case + 1, case, ordinal=0),),
    )
    context = WholeProgramContext(SourceBundle(((f"{case:03d}.s3", "prepared"),)))
    types = ()
    semantic = None
    failure = None
    if category == 1:
        types = (
            TypeSpec(TypeKind.ARRAY, element_type_id=2, array_length=1 + case % 16),
            TypeSpec(TypeKind.REFERENCE, element_type_id=2, mutable=bool(case % 2)),
        )
    elif category == 2:
        semantic = SemanticSeed(node_types=((case, 2),), calls=((case, 0),))
    elif category == 3:
        failure = PhaseKind.TYPE if case % 2 == 0 else PhaseKind.SEMANTIC
    result = context.compose(
        PreparedProgramArtifacts(
            _syntax(), (module,), type_specs=types,
            semantic=semantic or SemanticSeed(),
            ir=_ir(), output=f"case={case}".encode(),
        ),
        failure_phase=failure,
    )
    assert result.success is (category != 3)
    assert bool(result.diagnostics) is (category == 3)


def test_composition_soak_is_repeatable_in_three_clean_processes() -> None:
    code = """
from bootstrap.s3.compiler_substrate import SourceBundle
from bootstrap.s3.whole_program import ModuleSpec, FunctionSpec, ProgramRegistry, TypeArena, TypeKind, TypeSpec
registry = ProgramRegistry()
registry.register((ModuleSpec(10, 0, 0, functions=(FunctionSpec(1, 0),)),))
arena = TypeArena()
array = arena.intern(TypeSpec(TypeKind.ARRAY, element_type_id=2, array_length=4))
print(registry.structural_digest() + ':' + arena.structural_digest() + ':' + str(array))
"""
    outputs = []
    for _ in range(3):
        completed = subprocess.run(
            [sys.executable, "-c", code],
            check=True,
            capture_output=True,
            text=True,
        )
        outputs.append(completed.stdout)
    assert outputs[0] == outputs[1] == outputs[2]


@pytest.mark.s3_native
def test_native_whole_program_control_plane_projection(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("whole-program projection requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    repository = Path(__file__).parents[1]
    source = (repository / "selfhost/substrate/whole_program_context.s3").read_text(encoding="utf-8")
    assembly = compile_source(
        source + "\nfn main() -> i64:\n    return whole_program_control_plane_anchor()\n"
    ).assembly
    executable = toolchain.build(generate_native_assembly(assembly), tmp_path / "whole-program-control-plane")
    completed = toolchain.run(executable)
    assert completed.returncode == 0
    assert completed.stdout == "program returned: 10\n"
    assert completed.stderr == ""


@pytest.mark.s3_native
def test_native_control_plane_and_hosted_differential_matrix(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("whole-program native differential requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    repository = Path(__file__).parents[1]
    components = (
        ("program_registry.s3", "program_registry_case"),
        ("type_arena.s3", "type_arena_case"),
        ("phase_orchestrator.s3", "phase_orchestrator_case"),
        ("diagnostic_arena.s3", "diagnostic_arena_case"),
    )
    observed: list[int] = []
    for component_index, (filename, function) in enumerate(components):
        source = (repository / "selfhost/substrate" / filename).read_text(encoding="utf-8")
        for case in range(16):
            candidate = source + f"\nfn main() -> i64:\n    return {function}({case})\n"
            hosted = run_source(candidate)
            executable = toolchain.build(
                generate_native_assembly(compile_source(candidate).assembly),
                tmp_path / f"control-{component_index}-{case}",
            )
            completed = toolchain.run(executable)
            assert completed.returncode == 0
            assert completed.stderr == ""
            native = int(completed.stdout.removeprefix("program returned: ").strip())
            assert native == hosted
            observed.append(native)
    assert len(observed) == 64