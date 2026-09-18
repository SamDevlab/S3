from __future__ import annotations

from dataclasses import replace
import platform
from pathlib import Path

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64 import NativeBackendError, NativeToolchain, generate_native_assembly
from bootstrap.s3.compiler_substrate import InvalidIdError
from bootstrap.s3.generic_ir import IRBuilder, IRProgram, IRRange, IROpcode, IRType
from bootstrap.s3.generic_syntax import (
    DeclarationPayload,
    FloatPayload,
    FunctionPayload,
    IntegerPayload,
    NodeKind,
    OperatorPayload,
    SymbolPayload,
    SyntaxArena,
    SyntaxSpan,
    SyntaxValidationError,
    TextPayload,
    TypePayload,
)
from bootstrap.s3.generic_verifier import verify_ir_program
from bootstrap.s3.diagnostics import DiagnosticCode, SemanticError


SPAN = SyntaxSpan(0, 0, 1)


def _syntax_fixture() -> SyntaxArena:
    arena = SyntaxArena(symbol_count=4, type_count=2)
    integer = arena.append_node(
        NodeKind.INTEGER_LITERAL,
        SPAN,
        payload=IntegerPayload(7),
    )
    identifier = arena.append_node(
        NodeKind.IDENTIFIER,
        SPAN,
        payload=SymbolPayload(1),
    )
    block = arena.append_node(NodeKind.BLOCK, SPAN, children=(integer, identifier))
    root = arena.append_node(NodeKind.PROGRAM, SPAN, children=(block,))
    arena.set_root(root)
    return arena


def _scalar_program(value: int = 7) -> tuple[IRProgram, int, int]:
    builder = IRBuilder()
    function_id = builder.begin_function(1, "main", (IRType.I64,))
    value_id = builder.allocate_value(IRType.I64)
    builder.begin_block(2)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=value)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    return builder.program, function_id, value_id


def test_syntax_arena_is_flat_deterministic_and_validated() -> None:
    first = _syntax_fixture()
    second = _syntax_fixture()
    first.validate()
    second.validate()
    assert first.structural_digest() == second.structural_digest()
    assert first.child_ids(first.root_id or -1) == (2,)
    assert first.child_ids(2) == (0, 1)


def test_syntax_node_ids_are_direct_and_rollback_does_not_renumber() -> None:
    arena = _syntax_fixture()
    checkpoint = arena.checkpoint()
    temporary = arena.append_node(
        NodeKind.STRING_LITERAL,
        SPAN,
        payload=TextPayload("temporary"),
    )
    arena.rollback(checkpoint)
    replacement = arena.append_node(
        NodeKind.FLOAT_LITERAL,
        SPAN,
        payload=FloatPayload(1.5),
    )
    assert temporary not in arena.nodes
    assert replacement > temporary
    arena.validate()
    assert arena.node(replacement).kind is NodeKind.FLOAT_LITERAL


def test_syntax_payload_authority_covers_expression_and_declaration_families() -> None:
    arena = SyntaxArena(symbol_count=4, type_count=3)
    values = (
        arena.append_node(NodeKind.INTEGER_LITERAL, SPAN, payload=IntegerPayload(1)),
        arena.append_node(NodeKind.STRING_LITERAL, SPAN, payload=TextPayload("x")),
        arena.append_node(NodeKind.IDENTIFIER, SPAN, payload=SymbolPayload(0)),
        arena.append_node(NodeKind.BINARY, SPAN, payload=OperatorPayload(1)),
        arena.append_node(NodeKind.VARIABLE_DECLARATION, SPAN, payload=DeclarationPayload(2, 1)),
        arena.append_node(NodeKind.GENERIC_TYPE, SPAN, payload=TypePayload(2)),
    )
    root = arena.append_node(NodeKind.PROGRAM, SPAN, children=values)
    arena.set_root(root)
    arena.validate()


def test_syntax_function_payload_rejects_dangling_return_type() -> None:
    arena = SyntaxArena(symbol_count=1, type_count=1)
    function = arena.append_node(
        NodeKind.FUNCTION,
        SPAN,
        payload=FunctionPayload(
            symbol_id=0,
            return_type_id=1,
            parameter_first=0,
            parameter_count=0,
            body_id=-1,
        ),
    )
    arena.set_root(function)
    with pytest.raises(SyntaxValidationError, match="invalid function payload"):
        arena.validate()


def test_composite_vector_aggregate_field_boundary_is_explicitly_blocked() -> None:
    source = """\
record Item:
    value: i64
record Arena:
    values: vector<Item>
fn main() -> i64:
    return 0
"""
    with pytest.raises(SemanticError) as error:
        compile_source(source)
    assert error.value.diagnostic_code is DiagnosticCode.SEMANTIC_INVALID_ARGUMENT_TYPE
    assert "composite vectors cannot be stored inside aggregate fields" in str(error.value)


@pytest.mark.parametrize("case", range(8))
def test_syntax_negative_corpus_fails_closed(case: int) -> None:
    arena = _syntax_fixture()
    root = arena.root_id
    assert root is not None
    if case == 0:
        arena.children._items[0] = 999  # intentional malformed fixture
    elif case == 1:
        arena.nodes._items[root] = replace(arena.node(root), child_count=99)
    elif case == 2:
        arena.nodes._items[0] = replace(arena.node(0), payload_kind=arena.node(root).payload_kind, payload_id=-1)
    elif case == 3:
        arena.nodes._items[0] = replace(arena.node(0), span=SyntaxSpan(0, 4, 1))
    elif case == 4:
        arena.root_id = 999
    elif case == 5:
        arena.payloads[arena.node(1).payload_kind]._items[0] = SymbolPayload(999)
    elif case == 6:
        arena.nodes._items[2] = replace(arena.node(2), first_child=99)
    else:
        arena.nodes._items[0] = replace(arena.node(0), kind="not-a-node-kind")
    with pytest.raises(SyntaxValidationError):
        arena.validate()


def test_syntax_checkpoint_restores_payload_and_child_cursors() -> None:
    arena = _syntax_fixture()
    checkpoint = arena.checkpoint()
    temporary = arena.append_node(
        NodeKind.BINARY,
        SPAN,
        payload=OperatorPayload(3),
        children=(0, 1),
    )
    assert temporary in arena.nodes
    arena.rollback(checkpoint)
    arena.validate()
    with pytest.raises(InvalidIdError):
        arena.node(temporary)


@pytest.mark.parametrize("node_count", (32, 128, 512, 2048))
def test_syntax_scaling_probes_are_deterministic(node_count: int) -> None:
    def build() -> SyntaxArena:
        arena = SyntaxArena(symbol_count=1, type_count=1)
        literals = tuple(
            arena.append_node(
                NodeKind.INTEGER_LITERAL,
                SyntaxSpan(0, offset, offset + 1),
                payload=IntegerPayload(offset),
            )
            for offset in range(node_count)
        )
        root = arena.append_node(
            NodeKind.PROGRAM,
            SyntaxSpan(0, 0, node_count),
            children=literals,
        )
        arena.set_root(root)
        arena.validate()
        return arena

    first = build()
    second = build()
    assert len(tuple(first.nodes.items())) == node_count + 1
    assert first.structural_digest() == second.structural_digest()


def _linear_ir(instruction_count: int) -> IRProgram:
    builder = IRBuilder()
    builder.begin_function(1, "linear", (IRType.I64,))
    values = tuple(builder.allocate_value(IRType.I64) for _ in range(instruction_count - 1))
    builder.begin_block(2)
    for value_id, immediate in zip(values, range(instruction_count - 1)):
        builder.append_instruction(
            IROpcode.CONST,
            result_ids=(value_id,),
            immediate=immediate,
        )
    builder.append_instruction(IROpcode.RETURN, operand_ids=(values[-1],))
    builder.finish_block()
    builder.finish_function()
    return builder.program


@pytest.mark.parametrize("instruction_count", (32, 128, 512, 2048))
def test_ir_instruction_scaling_probes_are_deterministic(instruction_count: int) -> None:
    first = _linear_ir(instruction_count)
    second = _linear_ir(instruction_count)
    assert len(tuple(first.instructions.items())) == instruction_count
    assert first.structural_digest() == second.structural_digest()
    assert verify_ir_program(first).success is True


def _block_chain(block_count: int) -> IRProgram:
    builder = IRBuilder()
    builder.begin_function(1, "chain", (IRType.I64,))
    entry = builder.begin_block(10)
    blocks = (entry,) + tuple(builder.reserve_block(10 + index) for index in range(1, block_count))
    for index, block_id in enumerate(blocks[:-1]):
        if index:
            builder.open_block(block_id)
        builder.append_instruction(IROpcode.JUMP, target_block_ids=(blocks[index + 1],))
        builder.finish_block()
    builder.open_block(blocks[-1])
    value_id = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=0)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    return builder.program


@pytest.mark.parametrize("block_count", (4, 16, 64, 128))
def test_ir_block_scaling_probes_are_deterministic(block_count: int) -> None:
    first = _block_chain(block_count)
    second = _block_chain(block_count)
    assert len(tuple(first.blocks.items())) == block_count
    assert first.structural_digest() == second.structural_digest()
    result = verify_ir_program(first)
    assert result.success is True
    assert len(result.reachable_blocks) == block_count


def test_generic_ir_program_has_one_authoritative_arena_per_entity() -> None:
    program, function_id, value_id = _scalar_program()
    function = program.functions.get(function_id)
    assert program.values.get(value_id).function_id == function_id
    assert function.entry_block_id is not None
    assert program.blocks.get(function.entry_block_id).function_id == function_id
    assert len(tuple(program.instructions.items())) == 2
    result = verify_ir_program(program)
    assert result.success is True
    assert result.reachable_blocks == (0,)
    assert result.dominators == ((0, (0,)),)


def test_generic_ir_verifier_is_immutable_and_repeatable() -> None:
    program, _, _ = _scalar_program(11)
    before = program.structural_digest()
    first = verify_ir_program(program)
    middle = program.structural_digest()
    second = verify_ir_program(program)
    after = program.structural_digest()
    assert first == second
    assert before == middle == after


def test_ir_builder_transaction_rolls_back_all_ranges_and_can_continue() -> None:
    builder = IRBuilder()
    builder.begin_function(1, "main", (IRType.I64,))
    checkpoint = builder.checkpoint()
    builder.begin_block(2)
    temporary = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(temporary,), immediate=9)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(temporary,))
    builder.finish_block()
    builder.rollback(checkpoint)
    function = builder.program.functions.get(0)
    assert function.block_range.count == 0
    assert function.value_range.count == 0
    builder.begin_block(3)
    value_id = builder.allocate_value(IRType.I64)
    builder.append_instruction(IROpcode.CONST, result_ids=(value_id,), immediate=13)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(value_id,))
    builder.finish_block()
    builder.finish_function()
    assert value_id > temporary
    assert verify_ir_program(builder.program).success is True


def test_ir_multi_result_call_and_cfg_are_generic() -> None:
    builder = IRBuilder()
    pair_id = builder.begin_function(1, "pair", (IRType.I64, IRType.TRIT))
    first = builder.allocate_value(IRType.I64)
    second = builder.allocate_value(IRType.TRIT)
    builder.begin_block(2)
    builder.append_instruction(IROpcode.CONST, result_ids=(first,), immediate=4)
    builder.append_instruction(IROpcode.CONST, result_ids=(second,), immediate=1)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(first, second))
    builder.finish_block()
    builder.finish_function()

    builder.begin_function(3, "caller", (IRType.I64,))
    result = builder.allocate_value(IRType.I64)
    result_flag = builder.allocate_value(IRType.TRIT)
    builder.begin_block(4)
    builder.append_instruction(
        IROpcode.CALL,
        result_ids=(result, result_flag),
        callee_function_id=pair_id,
    )
    builder.append_instruction(IROpcode.RETURN, operand_ids=(result,))
    builder.finish_block()
    builder.finish_function()
    verification = verify_ir_program(builder.program)
    assert verification.success is True


def test_ir_cfg_and_dominance_use_block_ids_not_labels() -> None:
    builder = IRBuilder()
    builder.begin_function(1, "branching", (IRType.I64,))
    condition = builder.allocate_value(IRType.TRIT)
    result = builder.allocate_value(IRType.I64)
    entry = builder.begin_block(10)
    left = builder.reserve_block(11)
    right = builder.reserve_block(12)
    join = builder.reserve_block(13)
    builder.append_instruction(IROpcode.CONST, result_ids=(condition,), immediate=0)
    builder.append_instruction(IROpcode.BRANCH3, operand_ids=(condition,), target_block_ids=(left, join, right))
    builder.finish_block()
    builder.open_block(left)
    builder.append_instruction(IROpcode.JUMP, target_block_ids=(join,))
    builder.finish_block()
    builder.open_block(right)
    builder.append_instruction(IROpcode.JUMP, target_block_ids=(join,))
    builder.finish_block()
    builder.open_block(join)
    builder.append_instruction(IROpcode.CONST, result_ids=(result,), immediate=1)
    builder.append_instruction(IROpcode.RETURN, operand_ids=(result,))
    builder.finish_block()
    builder.finish_function()
    verification = verify_ir_program(builder.program)
    assert verification.success is True
    assert set(verification.reachable_blocks) == {entry, left, right, join}
    dominators = dict(verification.dominators)
    assert dominators[join] == (entry, join)


@pytest.mark.parametrize("case", range(8))
def test_ir_negative_verification_corpus_fails_closed(case: int) -> None:
    program, _, value_id = _scalar_program()
    block = program.blocks.get(0)
    instruction = program.instructions.get(1)
    if case == 0:
        program.operands.append(999)
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(1, 1))
    elif case == 1:
        program.instructions._items[0] = replace(program.instructions.get(0), opcode="unknown")
    elif case == 2:
        block.terminator_id = 999
    elif case == 3:
        block.instruction_range = IRRange(0, 1)
    elif case == 4:
        program.instructions._items[1] = replace(instruction, opcode=IROpcode.JUMP, target_range=IRRange(0, 0))
    elif case == 5:
        program.values._items[value_id] = replace(program.values.get(value_id), type="bad")
    elif case == 6:
        program.functions._items[0] = replace(program.functions.get(0), entry_block_id=99)
    else:
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(0, 0))
    result = verify_ir_program(program)
    assert result.success is False
    assert result.diagnostic_code


@pytest.mark.parametrize("case", range(256))
def test_deterministic_generic_differential_corpus(case: int) -> None:
    if case < 96:
        program, _, _ = _scalar_program(case - 48)
        result = verify_ir_program(program)
        assert result.success is True
    elif case < 224:
        program, _, _ = _scalar_program(case)
        program.operands.append(10_000 + case)
        instruction = program.instructions.get(1)
        program.instructions._items[1] = replace(instruction, operand_range=IRRange(1, 1))
        result = verify_ir_program(program)
        assert result.success is False
        assert result.diagnostic_code == "unknown_operand"
    else:
        arena = SyntaxArena(symbol_count=2, type_count=1)
        literal = arena.append_node(
            NodeKind.INTEGER_LITERAL,
            SyntaxSpan(0, case, case + 1),
            payload=IntegerPayload(case),
        )
        root = arena.append_node(NodeKind.PROGRAM, SyntaxSpan(0, 0, case + 1), children=(literal,))
        arena.set_root(root)
        arena.validate()
        assert arena.structural_digest() == _syntax_digest_for_case(case)


def _syntax_digest_for_case(case: int) -> str:
    arena = SyntaxArena(symbol_count=2, type_count=1)
    literal = arena.append_node(
        NodeKind.INTEGER_LITERAL,
        SyntaxSpan(0, case, case + 1),
        payload=IntegerPayload(case),
    )
    root = arena.append_node(NodeKind.PROGRAM, SyntaxSpan(0, 0, case + 1), children=(literal,))
    arena.set_root(root)
    return arena.structural_digest()


def test_selfhost_shapes_compile_without_composite_aggregate_fields() -> None:
    repository = Path(__file__).parents[1]
    for relative in (
        "selfhost/substrate/syntax_arena.s3",
        "selfhost/substrate/generic_ir_program.s3",
        "selfhost/substrate/verifier_kernel.s3",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        compilation = compile_source(source + "\nfn main() -> i64:\n    return 0\n")
        assert compilation.assembly.functions


@pytest.mark.s3_native
def test_selfhost_shapes_have_linux_native_qualification(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("generic substrate native qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))
    repository = Path(__file__).parents[1]
    for relative in (
        "selfhost/substrate/syntax_arena.s3",
        "selfhost/substrate/generic_ir_program.s3",
        "selfhost/substrate/verifier_kernel.s3",
    ):
        source = (repository / relative).read_text(encoding="utf-8")
        assembly = compile_source(
            source + "\nfn main() -> i64:\n    return 0\n"
        ).assembly
        executable = toolchain.build(
            generate_native_assembly(assembly),
            tmp_path / Path(relative).stem,
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stdout == "program returned: 0\n"
        assert completed.stderr == ""


@pytest.mark.s3_native
def test_native_verifier_differential_matrix_is_immutable_and_repeatable(tmp_path: Path) -> None:
    if platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"}:
        pytest.skip("native verifier qualification requires Linux x86-64")
    try:
        toolchain = NativeToolchain.detect()
    except NativeBackendError as error:
        pytest.skip(str(error))

    repository = Path(__file__).parents[1]
    verifier = (repository / "selfhost/substrate/verifier_kernel.s3").read_text(encoding="utf-8")
    valid_cases = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 23, 24, 25, 26, 27, 28, 29}
    observed: dict[int, int] = {}

    for case in range(32):
        source = verifier + f"\nfn main() -> i64:\n    return verifier_case({case})\n"
        hosted = run_source(source)
        if case in valid_cases:
            assert hosted // 1_000_000_000 == 1, (case, hosted)
        else:
            assert hosted // 1_000_000_000 == 0, (case, hosted)
        assert (hosted % 1_000_000_000) // 100_000_000 == 1, (case, hosted)

        assembly = compile_source(source).assembly
        executable = toolchain.build(
            generate_native_assembly(assembly),
            tmp_path / f"verifier-case-{case}",
        )
        completed = toolchain.run(executable)
        assert completed.returncode == 0
        assert completed.stderr == ""
        prefix = "program returned: "
        assert completed.stdout.startswith(prefix)
        native = int(completed.stdout[len(prefix):].strip())
        observed[case] = native
        assert native == hosted, (case, hosted, native)

    for case in (0, 3, 10, 17, 21, 30):
        for _ in range(3):
            source = verifier + f"\nfn main() -> i64:\n    return verifier_case({case})\n"
            executable = toolchain.build(
                generate_native_assembly(compile_source(source).assembly),
                tmp_path / f"verifier-repeat-{case}",
            )
            completed = toolchain.run(executable)
            assert completed.returncode == 0
            assert int(completed.stdout.removeprefix("program returned: ").strip()) == observed[case]
