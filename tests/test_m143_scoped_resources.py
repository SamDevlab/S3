from __future__ import annotations

import pytest

from bootstrap.s3 import compile_source, run_source
from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.dynamic import DynamicValue
from bootstrap.s3.host_services import (
    ResourceCapabilityError,
    ResourceClosedError,
    ResourceKind,
    ResourceLimitError,
    ResourceRegistry,
)


class _FakeProvider:
    def __init__(self, name: str, events: list[str]) -> None:
        self.name = name
        self.events = events
        self.next_id = 0

    def open(self) -> object:
        resource = f"{self.name}-{self.next_id}"
        self.next_id += 1
        self.events.append(f"open:{resource}")
        return resource

    def invoke(self, resource: object, arguments: tuple[DynamicValue, ...]) -> DynamicValue:
        self.events.append(f"invoke:{resource}")
        return DynamicValue.i64(len(arguments))

    def close(self, resource: object) -> None:
        self.events.append(f"close:{resource}")


def test_resource_capability_handle_lifecycle_is_explicit() -> None:
    events: list[str] = []
    registry = ResourceRegistry(max_active=2)
    registry.register(ResourceKind.FILE, _FakeProvider("file", events))
    capability = registry.grant(ResourceKind.FILE)
    handle = registry.open(capability)

    assert registry.is_open(handle)
    assert registry.invoke(handle, (DynamicValue.i64(1),)).value == 1
    registry.close(handle)
    assert not registry.is_open(handle)
    with pytest.raises(ResourceClosedError):
        registry.invoke(handle)
    with pytest.raises(ResourceClosedError):
        registry.close(handle)
    assert events == ["open:file-0", "invoke:file-0", "close:file-0"]


def test_capabilities_are_registry_scoped_and_provider_backed() -> None:
    first = ResourceRegistry()
    second = ResourceRegistry()
    first.register(ResourceKind.PROCESS, _FakeProvider("process", []))
    second.register(ResourceKind.PROCESS, _FakeProvider("other", []))

    capability = first.grant(ResourceKind.PROCESS)
    with pytest.raises(ResourceCapabilityError):
        second.open(capability)
    with pytest.raises(ResourceCapabilityError):
        first.grant(ResourceKind.SOCKET)


def test_resource_scope_closes_in_reverse_order_on_error() -> None:
    events: list[str] = []
    registry = ResourceRegistry()
    registry.register(ResourceKind.FILE, _FakeProvider("file", events))
    capability = registry.grant(ResourceKind.FILE)

    with pytest.raises(RuntimeError, match="body failure"):
        with registry.scope() as scope:
            scope.open(capability)
            scope.open(capability)
            raise RuntimeError("body failure")

    assert registry.active_count == 0
    assert events == [
        "open:file-0",
        "open:file-1",
        "close:file-1",
        "close:file-0",
    ]


def test_resource_limit_and_generation_are_deterministic() -> None:
    registry = ResourceRegistry(max_active=1)
    registry.register(ResourceKind.FILE, _FakeProvider("file", []))
    capability = registry.grant(ResourceKind.FILE)
    first = registry.open(capability)
    with pytest.raises(ResourceLimitError):
        registry.open(capability)
    registry.close(first)
    second = registry.open(capability)
    assert second._slot == first._slot
    assert second._generation == first._generation + 1


SOURCE_RESOURCE_LIFECYCLE = """\
fn main() -> i64:
    capability: host_capability = host_capability_grant(1)
    mut handle: resource_handle = resource_open(capability)
    mut total: i64 = resource_kind(&handle)
    one: i64 = 1
    ten: i64 = 10
    zero: i64 = 0
    match resource_is_open(&handle):
        -1:
            total = total + one
        0:
            total = total + zero
        1:
            discard resource_invoke(&handle, 1)
    discard resource_invoke(&handle, 7)
    discard resource_close(&mut handle)
    match resource_is_open(&handle):
        -1:
            total = total + ten
        0:
            total = total + zero
        1:
            discard resource_invoke(&handle, 1)
    return total
"""


def test_source_resource_lifecycle_is_deterministic_in_hosted_ir() -> None:
    assert run_source(SOURCE_RESOURCE_LIFECYCLE, optimization="O0") == 2
    assert run_source(SOURCE_RESOURCE_LIFECYCLE, optimization="O1") == 2


def test_source_resource_lifecycle_lowers_to_verified_native_fixture() -> None:
    native = X8664Backend().generate(compile_source(SOURCE_RESOURCE_LIFECYCLE).assembly)
    assert "__s3_builtin_host_capability_grant" in native
    assert "__s3_builtin_resource_open" in native
    assert "__s3_builtin_resource_close" in native
