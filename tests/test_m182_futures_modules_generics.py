from __future__ import annotations

import copy

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
from bootstrap.s3.module_graph import ModuleId


def test_future_is_first_class_and_move_only() -> None:
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: complete(17)))
    moved = owner.move()
    assert moved.is_ok
    assert owner.poll().error_or(None).code is FutureErrorCode.OWNERSHIP
    assert moved.value_or(None).await_once().value_or(None) == 17
    try:
        copy.copy(moved.value_or(None))
    except TypeError:
        pass
    else:
        raise AssertionError("Future copying must be rejected")


def test_pending_future_has_bounded_await_and_explicit_failure() -> None:
    owner = MoveOnlyFuture(AsyncFuture(lambda _frame: pending()))
    result = owner.await_once(max_polls=2)
    assert result.is_err
    assert result.error_or(None).code is FutureErrorCode.POLL_LIMIT


def test_module_identity_is_qualified_and_duplicate_registration_is_rejected() -> None:
    module = ModuleId.parse("net.client")
    identity = AsyncFunctionIdentity(module, "fetch", ("i64",))
    registry = AsyncModuleRegistry(max_functions=2)
    spec = AsyncFunctionSpec(identity, lambda: AsyncFuture(lambda _frame: complete(3)))
    assert registry.register(spec).is_ok
    assert registry.register(spec).error_or(None).code is FutureErrorCode.DUPLICATE_IDENTITY
    instance = registry.instantiate(identity).value_or(None)
    assert instance.await_once().value_or(None) == 3


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


def test_generic_registry_keeps_module_boundaries() -> None:
    registry = AsyncGenericRegistry()
    one = AsyncGenericDeclaration(ModuleId.parse("one"), "f", (), lambda _args: AsyncFuture(lambda _frame: complete(1)))
    two = AsyncGenericDeclaration(ModuleId.parse("two"), "f", (), lambda _args: AsyncFuture(lambda _frame: complete(2)))
    assert registry.register(one).is_ok
    assert registry.register(two).is_ok
    assert registry.specialize(ModuleId.parse("one"), "f", ()).value_or(None).identity.module == ModuleId.parse("one")
