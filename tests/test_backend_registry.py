from __future__ import annotations

from dataclasses import dataclass

import pytest

from bootstrap.s3.backends.registry import (
    BackendRegistry,
    BackendRegistryError,
    HostedEmulatorBackend,
    LinuxX8664NativeAssemblyBackend,
    create_builtin_backend_registry,
)
from bootstrap.s3.backends.x86_64 import generate_native_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.targets import LINUX_X86_64_TARGET, UnknownTargetError


SOURCE = "fn main() -> tryte:\n    return 6\n"


@dataclass(frozen=True, slots=True)
class _HostedProvider:
    result: int = 0

    def execute(self, program, entry: str = "main", **limits) -> int:
        del program, entry, limits
        return self.result


@dataclass(frozen=True, slots=True)
class _NativeAssemblyProvider:
    assembly: str = ".text\n"

    def generate(self, program, **limits) -> str:
        del program, limits
        return self.assembly


@dataclass(frozen=True, slots=True)
class _MissingExecute:
    pass


@dataclass(frozen=True, slots=True)
class _MissingGenerate:
    pass


def test_registry_registers_and_gets_hosted_execution_provider() -> None:
    provider = _HostedProvider(result=7)
    registry = BackendRegistry().register_hosted_execution("hosted", provider)

    assert registry.get_hosted_execution("hosted") is provider
    assert registry.get_hosted_execution("hosted").execute(None) == 7
    assert registry.hosted_execution_names == ("hosted",)


def test_registry_registers_and_gets_native_assembly_provider() -> None:
    provider = _NativeAssemblyProvider()
    registry = BackendRegistry().register_native_assembly(
        LINUX_X86_64_TARGET,
        provider,
    )

    assert registry.get_native_assembly("linux-x86_64") is provider
    assert registry.native_assembly_targets == ("linux-x86_64",)


def test_hosted_provider_does_not_require_target_spec() -> None:
    provider = HostedEmulatorBackend()
    registry = BackendRegistry().register_hosted_execution(
        "hosted-emulator",
        provider,
    )

    assert registry.get_hosted_execution("hosted-emulator") is provider
    assert not hasattr(provider, "target")


def test_native_assembly_provider_requires_known_target() -> None:
    with pytest.raises(UnknownTargetError, match="unknown target"):
        BackendRegistry().register_native_assembly(
            "windows-x86_64",
            _NativeAssemblyProvider(),
        )


def test_registry_rejects_duplicate_hosted_providers() -> None:
    with pytest.raises(BackendRegistryError, match="duplicate hosted"):
        BackendRegistry(
            hosted_execution=(
                ("hosted", _HostedProvider()),
                ("hosted", _HostedProvider()),
            )
        )


def test_registry_rejects_duplicate_native_assembly_targets() -> None:
    with pytest.raises(BackendRegistryError, match="duplicate native assembly"):
        BackendRegistry(
            native_assembly=(
                (LINUX_X86_64_TARGET, _NativeAssemblyProvider()),
                ("linux-x86_64", _NativeAssemblyProvider()),
            )
        )


def test_registry_reports_unknown_provider_and_missing_native_role() -> None:
    registry = BackendRegistry()

    with pytest.raises(BackendRegistryError, match="unknown hosted"):
        registry.get_hosted_execution("missing")
    with pytest.raises(BackendRegistryError, match="no native assembly"):
        registry.get_native_assembly("linux-x86_64")


def test_registry_rejects_missing_required_methods_on_registration() -> None:
    with pytest.raises(BackendRegistryError, match="hosted execution"):
        BackendRegistry().register_hosted_execution(
            "bad-hosted",
            _MissingExecute(),  # type: ignore[arg-type]
        )
    with pytest.raises(BackendRegistryError, match="native assembly"):
        BackendRegistry().register_native_assembly(
            LINUX_X86_64_TARGET,
            _MissingGenerate(),  # type: ignore[arg-type]
        )


def test_builtin_registry_factory_creates_independent_instances() -> None:
    first = create_builtin_backend_registry()
    second = create_builtin_backend_registry()

    assert first is not second
    assert first.hosted_execution_names == ("hosted-emulator",)
    assert first.native_assembly_targets == ("linux-x86_64",)
    assert second.hosted_execution_names == first.hosted_execution_names


def test_builtin_hosted_emulator_executes_s3_assembly() -> None:
    backend = create_builtin_backend_registry().get_hosted_execution(
        "hosted-emulator"
    )
    compilation = compile_source(SOURCE)

    assert isinstance(backend, HostedEmulatorBackend)
    assert backend.execute(compilation.assembly) == 6


def test_builtin_linux_adapter_generates_existing_native_assembly() -> None:
    backend = create_builtin_backend_registry().get_native_assembly(
        "linux-x86_64"
    )
    program = compile_source(SOURCE, mode=SyntaxMode.V0_6).assembly

    assert isinstance(backend, LinuxX8664NativeAssemblyBackend)
    assert backend.generate(program) == generate_native_assembly(program)


def test_registry_does_not_declare_native_build_or_execution() -> None:
    registry = create_builtin_backend_registry()
    provider = registry.get_native_assembly("linux-x86_64")

    assert not hasattr(registry, "select")
    assert not hasattr(provider, "build")
    assert not hasattr(provider, "run")


def test_registry_lists_roles_deterministically() -> None:
    registry = create_builtin_backend_registry()

    assert tuple(name for name, _ in registry.iter_hosted_execution()) == (
        "hosted-emulator",
    )
    assert tuple(
        target.name for target, _ in registry.iter_native_assembly()
    ) == ("linux-x86_64",)


def test_registry_instances_do_not_share_mutable_state() -> None:
    original = BackendRegistry()
    updated = original.register_hosted_execution("hosted", _HostedProvider())

    assert original.hosted_execution_names == ()
    assert updated.hosted_execution_names == ("hosted",)
    assert original is not updated
