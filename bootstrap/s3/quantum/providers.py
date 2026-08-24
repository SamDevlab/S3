"""Provider and QIR contracts; no provider SDK or network behavior."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol
from .ir import QuantumProgram, QuantumTarget

@dataclass(frozen=True)
class QirCapabilities:
    profiles: frozenset[str] = frozenset({"base"})

@dataclass(frozen=True)
class QirTargetProfile:
    name: str = "base"
    capabilities: QirCapabilities = QirCapabilities()

class QirBackend(Protocol):
    profile: QirTargetProfile

class QuantumProvider(Protocol):
    def discover_devices(self) -> tuple[str,...]: ...
    def capabilities(self, device: str) -> QuantumTarget: ...
    def submit(self, program: QuantumProgram, device: str) -> str: ...
    def status(self, job: str) -> str: ...
    def result(self, job: str) -> object: ...
