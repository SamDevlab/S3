

def test_type_arena_rejects_dangling_element_and_argument_ids() -> None:
    arena = TypeArena()
    with pytest.raises(TypeArenaError, match="unknown element"):
        arena.intern(TypeSpec(TypeKind.VECTOR, element_type_id=999))
    with pytest.raises(TypeArenaError, match="type arguments"):
        arena.intern(
            TypeSpec(
                TypeKind.INSTANTIATED,
                module_id=0,
                nominal_declaration_id=0,
                type_arguments=(999,),
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


def test_compile_program_runs_real_frontend_and_type_then_fails_closed_at_semantic_phase() -> None:
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
    assert result.diagnostics[0].code == "S3E_SEMANTIC_PHASE_UNAVAILABLE"
    assert result.phase_trace[:5] == (
        "INPUT:COMMITTED",
        "SYNTAX:COMMITTED",
        "REGISTRATION:COMMITTED",
        "TYPE:COMMITTED",
        "SEMANTIC:FAILED",
    )
    assert "LOWERING:SKIPPED" in result.phase_trace


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