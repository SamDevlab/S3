"""Internal backend adapters and deterministic provider registry."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from ..assembly import AssemblyProgram
from ..emulator import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_MAX_INSTRUCTIONS,
    DEFAULT_MAX_MEMORY_TRITS,
    Emulator,
)
from ..targets import (
    BUILTIN_TARGETS,
    LINUX_X86_64_TARGET,
    TargetCatalog,
    TargetSpec,
)
from .x86_64 import X8664Backend


class BackendRegistryError(ValueError):
    """Raised for invalid internal backend registry operations."""


@runtime_checkable
class HostedExecutionBackend(Protocol):
    def execute(
        self,
        program: AssemblyProgram,
        entry: str = "main",
        *,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
        max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    ) -> int:
        ...


@runtime_checkable
class NativeAssemblyBackend(Protocol):
    def generate(
        self,
        program: AssemblyProgram,
        *,
        max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    ) -> str:
        ...


@dataclass(frozen=True, slots=True)
class _HostedExecutionRegistration:
    name: str
    provider: HostedExecutionBackend


@dataclass(frozen=True, slots=True)
class _NativeAssemblyRegistration:
    target: TargetSpec
    provider: NativeAssemblyBackend


@dataclass(frozen=True, slots=True)
class HostedEmulatorBackend:
    def execute(
        self,
        program: AssemblyProgram,
        entry: str = "main",
        *,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
        max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
    ) -> int:
        return Emulator(
            max_frames=max_frames,
            max_instructions=max_instructions,
            max_memory_trits=max_memory_trits,
        ).execute(program, entry)


@dataclass(frozen=True, slots=True)
class LinuxX8664NativeAssemblyBackend:
    def generate(
        self,
        program: AssemblyProgram,
        *,
        max_memory_trits: int = DEFAULT_MAX_MEMORY_TRITS,
        max_frames: int = DEFAULT_MAX_FRAMES,
        max_instructions: int = DEFAULT_MAX_INSTRUCTIONS,
    ) -> str:
        return X8664Backend(
            max_memory_trits=max_memory_trits,
            max_frames=max_frames,
            max_instructions=max_instructions,
        ).generate(program)


def _require_non_empty_name(name: str, *, field: str) -> None:
    if not isinstance(name, str) or not name:
        raise BackendRegistryError(f"{field} must be a non-empty string")


def _require_callable(provider: object, method: str, *, role: str) -> None:
    if not callable(getattr(provider, method, None)):
        raise BackendRegistryError(
            f"{role} provider must define callable {method}()"
        )


def _require_hosted_execution(
    provider: HostedExecutionBackend,
) -> None:
    if not isinstance(provider, HostedExecutionBackend):
        raise BackendRegistryError(
            "hosted execution provider does not satisfy the protocol"
        )
    _require_callable(provider, "execute", role="hosted execution")


def _require_native_assembly(
    provider: NativeAssemblyBackend,
) -> None:
    if not isinstance(provider, NativeAssemblyBackend):
        raise BackendRegistryError(
            "native assembly provider does not satisfy the protocol"
        )
    _require_callable(provider, "generate", role="native assembly")


@dataclass(frozen=True, slots=True)
class BackendRegistry:
    _hosted_execution: tuple[_HostedExecutionRegistration, ...]
    _native_assembly: tuple[_NativeAssemblyRegistration, ...]
    target_catalog: TargetCatalog

    def __init__(
        self,
        hosted_execution: Iterable[
            tuple[str, HostedExecutionBackend]
        ] = (),
        native_assembly: Iterable[
            tuple[str | TargetSpec, NativeAssemblyBackend]
        ] = (),
        *,
        target_catalog: TargetCatalog | None = None,
    ) -> None:
        catalog = target_catalog or TargetCatalog(BUILTIN_TARGETS)
        hosted = self._normalize_hosted_execution(hosted_execution)
        native = self._normalize_native_assembly(native_assembly, catalog)
        object.__setattr__(
            self,
            "_hosted_execution",
            tuple(sorted(hosted, key=lambda item: item.name)),
        )
        object.__setattr__(
            self,
            "_native_assembly",
            tuple(sorted(native, key=lambda item: item.target.name)),
        )
        object.__setattr__(self, "target_catalog", catalog)

    @staticmethod
    def _normalize_hosted_execution(
        hosted_execution: Iterable[tuple[str, HostedExecutionBackend]],
    ) -> tuple[_HostedExecutionRegistration, ...]:
        names: set[str] = set()
        duplicates: set[str] = set()
        registrations: list[_HostedExecutionRegistration] = []
        for name, provider in hosted_execution:
            _require_non_empty_name(name, field="hosted provider name")
            _require_hosted_execution(provider)
            if name in names:
                duplicates.add(name)
            names.add(name)
            registrations.append(_HostedExecutionRegistration(name, provider))
        if duplicates:
            rendered = ", ".join(sorted(duplicates))
            raise BackendRegistryError(
                f"duplicate hosted execution provider(s): {rendered}"
            )
        return tuple(registrations)

    @staticmethod
    def _normalize_native_assembly(
        native_assembly: Iterable[
            tuple[str | TargetSpec, NativeAssemblyBackend]
        ],
        catalog: TargetCatalog,
    ) -> tuple[_NativeAssemblyRegistration, ...]:
        targets: set[str] = set()
        duplicates: set[str] = set()
        registrations: list[_NativeAssemblyRegistration] = []
        for target, provider in native_assembly:
            target_spec = BackendRegistry._resolve_target(target, catalog)
            _require_native_assembly(provider)
            if target_spec.name in targets:
                duplicates.add(target_spec.name)
            targets.add(target_spec.name)
            registrations.append(
                _NativeAssemblyRegistration(target_spec, provider)
            )
        if duplicates:
            rendered = ", ".join(sorted(duplicates))
            raise BackendRegistryError(
                f"duplicate native assembly provider(s): {rendered}"
            )
        return tuple(registrations)

    @staticmethod
    def _resolve_target(
        target: str | TargetSpec,
        catalog: TargetCatalog,
    ) -> TargetSpec:
        if isinstance(target, TargetSpec):
            catalog_target = catalog.get(target.name)
            if target != catalog_target:
                raise BackendRegistryError(
                    f"target {target.name!r} does not match catalog"
                )
            return catalog_target
        if isinstance(target, str):
            return catalog.get(target)
        raise TypeError("native assembly target must be TargetSpec or str")

    @property
    def hosted_execution_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in self._hosted_execution)

    @property
    def native_assembly_targets(self) -> tuple[str, ...]:
        return tuple(item.target.name for item in self._native_assembly)

    def register_hosted_execution(
        self,
        name: str,
        provider: HostedExecutionBackend,
    ) -> BackendRegistry:
        return BackendRegistry(
            (*self._hosted_execution_pairs(), (name, provider)),
            self._native_assembly_pairs(),
            target_catalog=self.target_catalog,
        )

    def register_native_assembly(
        self,
        target: str | TargetSpec,
        provider: NativeAssemblyBackend,
    ) -> BackendRegistry:
        return BackendRegistry(
            self._hosted_execution_pairs(),
            (*self._native_assembly_pairs(), (target, provider)),
            target_catalog=self.target_catalog,
        )

    def get_hosted_execution(self, name: str) -> HostedExecutionBackend:
        for item in self._hosted_execution:
            if item.name == name:
                return item.provider
        raise BackendRegistryError(
            f"unknown hosted execution provider {name!r}"
        )

    def get_native_assembly(
        self,
        target_name: str,
    ) -> NativeAssemblyBackend:
        target = self.target_catalog.get(target_name)
        for item in self._native_assembly:
            if item.target.name == target.name:
                return item.provider
        raise BackendRegistryError(
            f"target {target_name!r} has no native assembly provider"
        )

    def iter_hosted_execution(
        self,
    ) -> Iterator[tuple[str, HostedExecutionBackend]]:
        return iter(self._hosted_execution_pairs())

    def iter_native_assembly(
        self,
    ) -> Iterator[tuple[TargetSpec, NativeAssemblyBackend]]:
        return iter(
            tuple((item.target, item.provider) for item in self._native_assembly)
        )

    def _hosted_execution_pairs(
        self,
    ) -> tuple[tuple[str, HostedExecutionBackend], ...]:
        return tuple(
            (item.name, item.provider) for item in self._hosted_execution
        )

    def _native_assembly_pairs(
        self,
    ) -> tuple[tuple[TargetSpec, NativeAssemblyBackend], ...]:
        return tuple(
            (item.target, item.provider) for item in self._native_assembly
        )


def create_builtin_backend_registry() -> BackendRegistry:
    return BackendRegistry(
        hosted_execution=(("hosted-emulator", HostedEmulatorBackend()),),
        native_assembly=(
            (LINUX_X86_64_TARGET, LinuxX8664NativeAssemblyBackend()),
        ),
    )
