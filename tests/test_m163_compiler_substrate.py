from __future__ import annotations

import pytest

from bootstrap.s3 import compile_source
from bootstrap.s3.compiler_substrate import (
    CapacityError,
    CompilerContext,
    InvalidIdError,
    OutputSink,
    ScopeError,
    SemanticEnvironment,
    SourceBundle,
    SourceSpan,
    StableArena,
    SymbolInterner,
)


def test_symbol_interner_assigns_direct_stable_ids_and_reuses_utf8_names() -> None:
    symbols = SymbolInterner()
    first = symbols.intern("café")
    second = symbols.intern("café")
    third = symbols.intern("cafe")
    assert (first, second, third) == (0, 0, 1)
    assert symbols.name(first) == "café"
    assert symbols.name(third) == "cafe"


def test_stable_arena_checkpoint_rolls_back_without_renumbering_live_ids() -> None:
    arena: StableArena[str] = StableArena()
    first = arena.append("first")
    checkpoint = arena.checkpoint()
    second = arena.append("second")
    arena.rollback(checkpoint)
    third = arena.append("third")
    assert first == 0
    assert second == 1
    assert third == 2
    assert arena.get(first) == "first"
    with pytest.raises(InvalidIdError):
        arena.get(second)


def test_semantic_environment_supports_nearest_shadowing_and_function_isolation() -> None:
    symbols = SymbolInterner()
    environment = SemanticEnvironment(symbols)
    global_decl = environment.declare("value", "global")
    function_scope = environment.enter_function(17)
    local_decl = environment.declare("value", "local")
    assert environment.lookup("value") == local_decl
    nested_scope = environment.enter_scope()
    nested_decl = environment.declare("value", "nested")
    assert environment.lookup("value") == nested_decl
    environment.leave_scope()
    assert environment.lookup("value") == local_decl
    environment.leave_scope()
    assert environment.lookup("value") == global_decl
    assert function_scope != 0
    with pytest.raises(ScopeError):
        environment.leave_scope()


def test_semantic_environment_rollback_removes_temporary_bindings() -> None:
    symbols = SymbolInterner()
    environment = SemanticEnvironment(symbols)
    outer = environment.declare("value", "global")
    checkpoint = environment.checkpoint()
    environment.enter_scope()
    temporary = environment.declare(
        "value",
        "local",
        storage_id=4,
        mutable=True,
        span=SourceSpan(0, 10, 15),
    )
    assert environment.lookup("value") == temporary
    environment.rollback(checkpoint)
    assert environment.lookup("value") == outer
    with pytest.raises(InvalidIdError):
        environment.declarations.get(temporary)


def test_source_bundle_order_newline_normalization_and_cursor_bounds() -> None:
    bundle = SourceBundle((
        ("z.s3", "z\r\nlast\r"),
        ("a.s3", "first\nlast"),
    ))
    assert [item.path for item in bundle.files] == ["a.s3", "z.s3"]
    view = bundle.view(1)
    cursor = view.cursor()
    assert view.read(cursor) == ord("z")
    cursor = view.advance(cursor, 2)
    assert view.read(cursor) == ord("l")
    assert view.length == len(b"z\nlast\n")
    with pytest.raises(IndexError):
        view.advance(cursor, 100)


def test_output_sink_is_bounded_and_transactional() -> None:
    sink = OutputSink(5)
    sink.append("ab")
    checkpoint = sink.checkpoint()
    sink.append(b"cd")
    sink.rollback(checkpoint)
    sink.append("e")
    assert sink.to_bytes() == b"abe"
    with pytest.raises(CapacityError):
        sink.append("123")


def test_compiler_context_checkpoints_arenas_and_output() -> None:
    context = CompilerContext(SourceBundle((("main.s3", "fn main"),)), output_capacity=16)
    context.add("Function", {"name": "main"})
    checkpoint = context.checkpoint()
    context.add("Instruction", {"opcode": "const"})
    context.register_type("Thing", 3)
    context.register_function("compile", 8)
    context.environment.declare("temporary", "local")
    context.sink.append("temporary")
    context.rollback(checkpoint)
    assert len(context.arenas["Instruction"]) == 0
    assert context.lookup_type("Thing") is None
    assert context.lookup_function("compile") is None
    assert context.environment.lookup("temporary") is None
    assert context.sink.to_bytes() == b""
    assert context.result().output == b""


def test_compiler_context_exposes_all_direct_id_domains_and_result_metadata() -> None:
    context = CompilerContext(SourceBundle((("main.s3", "source"),)))
    ids = {name: context.add(name, (name, 0)) for name in context.arenas}
    assert ids == {name: 0 for name in context.arenas}
    context.register_type("Thing", ids["Type"])
    context.register_function("compile", ids["Function"])
    declaration = context.environment.declare(
        "value", "local", type_id=ids["Type"], storage_id=ids["Storage"], mutable=True
    )
    result = context.result()
    assert context.lookup_type("Thing") == ids["Type"]
    assert context.lookup_function("compile") == ids["Function"]
    assert context.environment.declarations.get(declaration).storage_id == ids["Storage"]
    assert context.environment.declarations.get(declaration).mutable is True
    assert result.success is True
    assert result.output_length == 0


def test_s3_substrate_components_are_representable() -> None:
    component_paths = (
        "selfhost/substrate/text_map.s3",
        "selfhost/substrate/symbol_table.s3",
        "selfhost/substrate/arena.s3",
        "selfhost/substrate/semantic_environment.s3",
        "selfhost/substrate/source_transport.s3",
        "selfhost/substrate/output_sink.s3",
        "selfhost/substrate/compiler_context.s3",
    )
    from pathlib import Path

    repository = Path(__file__).parents[1]
    for relative_path in component_paths:
        source = (repository / relative_path).read_text(encoding="utf-8")
        assert compile_source(source + "\nfn main() -> i64:\n    return 0\n").assembly.functions


@pytest.mark.parametrize("case", range(128))
def test_deterministic_substrate_case(case: int) -> None:
    mode = case % 8
    files = tuple(
        (
            f"unit/{case:03d}/{index}.s3",
            f"value-{case}-{index}" + ("\r\n" if mode % 2 else "\n"),
        )
        for index in range(1 + mode % 3)
    )
    left = SourceBundle(files)
    right = SourceBundle(files)
    assert left.digest() == right.digest()
    symbols = SymbolInterner()
    first = symbols.intern(f"symbol-{mode}-{case}")
    assert symbols.intern(f"symbol-{mode}-{case}") == first == 0
    assert symbols.intern(f"other-{case}") == 1
    assert symbols.name(first) == f"symbol-{mode}-{case}"
    arena: StableArena[tuple[int, int]] = StableArena(capacity=8)
    for index in range(1 + mode % 4):
        assert arena.append((case, index)) == index
    checkpoint = arena.checkpoint()
    temporary = arena.append((case, 99))
    arena.rollback(checkpoint)
    assert temporary not in arena
    environment = SemanticEnvironment(symbols)
    root = environment.declare(f"root-{case}", "global")
    for depth in range(mode % 3):
        environment.enter_scope()
        shadow = environment.declare(f"root-{case}", f"local-{depth}")
        assert environment.lookup(f"root-{case}") == shadow
    while environment.current_scope != 0:
        environment.leave_scope()
    assert environment.lookup(f"root-{case}") == root
    sink = OutputSink(32)
    sink.append(f"case={case}")
    sink_checkpoint = sink.checkpoint()
    sink.append(bytes([mode]))
    sink.rollback(sink_checkpoint)
    assert sink.to_bytes() == f"case={case}".encode()


@pytest.mark.parametrize("round_number", range(3))
def test_substrate_soak_round(round_number: int) -> None:
    context = CompilerContext(SourceBundle((("main.s3", "soak"),)))
    for index in range(128):
        context.add("Node", ("soak", index))
        context.symbols.intern(f"name-{index}")
    assert len(context.arenas["Node"]) == 128
    assert context.symbols.length == 128
    assert context.symbols.name(0) == "name-0"
    assert context.sources.digest() == SourceBundle((("main.s3", "soak"),)).digest()
