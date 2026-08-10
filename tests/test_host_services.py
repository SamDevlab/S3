from __future__ import annotations

import pytest

from bootstrap.s3.dynamic import DynamicError, DynamicKind, DynamicValue
from bootstrap.s3.host_services import (
    HostService,
    HostServiceError,
    HostServiceRegistry,
    HostServiceRequest,
)


def test_host_service_registry_is_explicit_and_injectable() -> None:
    registry = HostServiceRegistry()
    registry.register(
        HostService.DIAGNOSTIC,
        lambda arguments: DynamicValue.i64(len(arguments)),
    )
    result = registry.invoke(
        HostServiceRequest(HostService.DIAGNOSTIC, (DynamicValue.tryte(1),))
    )
    assert result.kind is DynamicKind.I64
    assert result.value == 1


def test_host_service_registry_rejects_missing_or_duplicate_services() -> None:
    registry = HostServiceRegistry()
    request = HostServiceRequest(HostService.CLOCK_MONOTONIC)
    with pytest.raises(HostServiceError, match="unavailable"):
        registry.invoke(request)
    registry.register(HostService.CLOCK_MONOTONIC, lambda _: DynamicValue.i64(1))
    with pytest.raises(HostServiceError, match="already registered"):
        registry.register(HostService.CLOCK_MONOTONIC, lambda _: DynamicValue.i64(2))


def test_host_service_handler_result_is_checked() -> None:
    registry = HostServiceRegistry()
    registry.register(HostService.DIAGNOSTIC, lambda _: DynamicValue.i64(1))
    assert registry.invoke(HostServiceRequest(HostService.DIAGNOSTIC)).value == 1
