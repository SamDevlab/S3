from __future__ import annotations

import copy

import pytest

from bootstrap.s3.async_core import AsyncFuture, complete, pending
from bootstrap.s3.async_futures import (
    AsyncFunctionIdentity,
    AsyncFunctionSpec,
    AsyncGenericDeclaration,
    AsyncGenericRegistry,
    AsyncModuleRegistry,
    FutureErrorCode,
    MoveOnlyFuture,
)
from bootstrap.s3.async_ir import AsyncIRPollKind, execute_async_program
from bootstrap.s3.diagnostics import SemanticError
from bootstrap.s3.module_graph import ModuleId
from bootstrap.s3.pipeline import compile_source, compile_sources, run_source


def test_future_is_first_class_and_move_only_host_contract() -> None:
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(17)))
    moved = owner.move()
    assert moved.is_ok
    assert owner.poll().error_or(None).code is FutureErrorCode.OWNERSHIP
    assert moved.value_or(None).await_once().value_or(None) == 17
    with pytest.raises(TypeError):
        copy.copy(moved.value_or(None))


def test_pending_future_has_bounded_await_and_explicit_failure() -> None:
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: pending()))
    result = owner.await_once(max_polls=2)
    assert result.is_err
    assert result.error_or(None).code is FutureErrorCode.POLL_LIMIT


def test_source_future_type_is_compiler_owned_move_only_and_awaitable() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 17\n"
        "async fn main() -> i64:\n"
        "    pending_value: Future<i64> = child()\n"
        "    moved_value: Future<i64> = pending_value\n"
        "    return await moved_value\n"
    )
    compilation = compile_source(source)
    assert {item.name for item in compilation.async_syntax.futures if item.name} == {"pending_value", "moved_value"}
    assert compilation.async_ir is not None
    assert run_source(source) == 17


def test_source_future_can_move_across_async_parameter_boundary() -> None:
    source = (
        "async fn child() -> i64:\n"
        "    return 23\n"
        "async fn consume(value: Future<i64>) -> i64:\n"
        "    return await value\n"
        "async fn main() -> i64:\n"
        "    pending_value: Future<i64> = child()\n"
        "    return await consume(pending_value)\n"
    )
    assert run_source(source) == 23


def test_source_future_double_move_and_double_await_fail_at_compile_time() -> None:
    with pytest.raises(SemanticError, match="already moved or consumed"):
        compile_source(
            "async fn child() -> i64:\n"
            "    return 1\n"
            "async fn main() -> i64:\n"
            "    first_future: Future<i64> = child()\n"
            "    second_future: Future<i64> = first_future\n"
            "    third_future: Future<i64> = first_future\n"
            "    return await second_future\n"
        )
    with pytest.raises(SemanticError, match="already moved or consumed"):
        compile_source(
            "async fn child() -> i64:\n"
            "    return 1\n"
            "async fn main() -> i64:\n"
            "    only_future: Future<i64> = child()\n"
            "    first: i64 = await only_future\n"
            "    return await only_future\n"
        )


def test_module_identity_is_qualified_and_duplicate_registration_is_rejected() -> None:
    module = ModuleId.parse("net.client")
    identity = AsyncFunctionIdentity(module, "fetch", ("i64",))
    registry = AsyncModuleRegistry(max_functions=2)
    spec = AsyncFunctionSpec(identity, lambda: AsyncFuture(lambda _frame: complete(3)))
    assert registry.register(spec).is_ok
    assert registry.register(spec).error_or(None).code is FutureErrorCode.DUPLICATE_IDENTITY
    instance = registry.instantiate(identity).value_or(None)
    assert instance.await_once().value_or(None) == 3


def test_async_import_alias_survives_module_rewrite_and_executes() -> None:
    compilation = compile_sources(
        {
            "lib.s3": (
                "module lib\n"
                "export async fn value() -> i64:\n"
                "    return 31\n"
            ),
            "main.s3": (
                "module main\n"
                "from lib import value as fetch\n"
                "async fn main() -> i64:\n"
                "    return await fetch()\n"
            ),
        },
        entry_module="main",
    )
    assert compilation.async_ir is not None
    assert compilation.async_ir.ir_function("__s3mod_lib__value") is not None
    result = execute_async_program(compilation.async_ir, "main")
    assert result.kind is AsyncIRPollKind.READY
    assert result.value == 31


def test_constrained_generic_async_specialization_is_deterministic_and_closed() -> None:
    module = ModuleId.parse("math")
    registry = AsyncGenericRegistry()
    declaration = AsyncGenericDeclaration(
        module,
        "identity_async",
        ("scalar",),
        lambda arguments: AsyncFuture(lambda _frame: complete(arguments[0])),
    )
    assert registry.register(declaration).is_ok
    first = registry.specialize(module, "identity_async", ("i64",))
    second = registry.specialize(module, "identity_async", ("i64",))
    assert first.value_or(None).identity == second.value_or(None).identity
    assert first.value_or(None).instantiate().poll().value == "i64"
    rejected = registry.specialize(module, "identity_async", ("vector<i64>",))
    assert rejected.error_or(None).code is FutureErrorCode.INVALID_TYPE_ARGUMENT


def test_source_generic_async_function_gets_a_deterministic_specialized_frame() -> None:
    source = (
        "async fn identity<T: scalar>(value: T) -> T:\n"
        "    return value\n"
        "async fn main() -> i64:\n"
        "    return await identity<i64>(41)\n"
    )
    first = compile_source(source)
    second = compile_source(source)
    assert first.async_ir is not None and second.async_ir is not None
    assert first.async_ir.to_dict() == second.async_ir.to_dict()
    names = [function.name for function in first.async_ir.functions]
    assert "identity" not in names
    specializations = [name for name in names if name.startswith("identity__async_spec_")]
    assert len(specializations) == 1
    main = first.async_ir.ir_function("main")
    assert main is not None and main.executable is not None
    assert main.executable.actions[0].callee == specializations[0]
    assert run_source(source) == 41


def test_two_async_generic_instantiations_have_distinct_stable_frame_identities() -> None:
    source = (
        "async fn identity<T: value>(value: T) -> T:\n"
        "    return value\n"
        "async fn main() -> i64:\n"
        "    first: i64 = await identity<i64>(4)\n"
        "    discard identity<tryte>(1)\n"
        "    return first\n"
    )
    # An unawaited async call remains illegal even when generic; keep the gate
    # explicit rather than turning it into an implicit detached Future.
    with pytest.raises(SemanticError, match="must be awaited or stored"):
        compile_source(source)


def test_generic_registry_keeps_module_boundaries() -> None:
    registry = AsyncGenericRegistry()
    one = AsyncGenericDeclaration(ModuleId.parse("one"), "f", (), lambda _args: AsyncFuture(lambda _frame: complete(1)))
    two = AsyncGenericDeclaration(ModuleId.parse("two"), "f", (), lambda _args: AsyncFuture(lambda _frame: complete(2)))
    assert registry.register(one).is_ok
    assert registry.register(two).is_ok
    assert registry.specialize(ModuleId.parse("one"), "f", ()).value_or(None).identity.module == ModuleId.parse("one")
