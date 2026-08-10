"""Explicit, injectable host-service contracts for M1.36."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Callable

from .dynamic import DynamicValue


class HostServiceError(RuntimeError):
    """Raised for an unavailable or incorrectly invoked host service."""


class HostService(Enum):
    CLOCK_MONOTONIC = "clock_monotonic"
    DIAGNOSTIC = "diagnostic"


@dataclass(frozen=True, slots=True)
class HostServiceRequest:
    service: HostService
    arguments: tuple[DynamicValue, ...] = ()


HostServiceHandler = Callable[[tuple[DynamicValue, ...]], DynamicValue]


class HostServiceRegistry:
    """A local dependency-injected registry with no implicit host access."""

    def __init__(self) -> None:
        self._handlers: dict[HostService, HostServiceHandler] = {}

    def register(self, service: HostService, handler: HostServiceHandler) -> None:
        if not isinstance(service, HostService):
            raise HostServiceError("service must be a HostService")
        if service in self._handlers:
            raise HostServiceError(f"host service already registered: {service.value}")
        self._handlers[service] = handler

    def invoke(self, request: HostServiceRequest) -> DynamicValue:
        handler = self._handlers.get(request.service)
        if handler is None:
            raise HostServiceError(f"host service unavailable: {request.service.value}")
        result = handler(request.arguments)
        if not isinstance(result, DynamicValue):
            raise HostServiceError("host service handler must return DynamicValue")
        return result
