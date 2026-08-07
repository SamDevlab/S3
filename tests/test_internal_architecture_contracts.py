from __future__ import annotations

import ast
import inspect
from dataclasses import fields
from pathlib import Path

import bootstrap.s3 as s3
from bootstrap.s3.backends.registry import (
    HostedEmulatorBackend,
    LinuxX8664NativeAssemblyBackend,
    create_builtin_backend_registry,
)
from bootstrap.s3.backends.x86_64.backend import (
    X8664Backend,
    generate_native_assembly,
)
from bootstrap.s3.backends.x86_64.toolchain import NativeToolchain
from bootstrap.s3.compilation_context import CompilationContext
from bootstrap.s3.emulator import Emulator, execute_assembly
from bootstrap.s3.optimizer import _o1_passes
from bootstrap.s3.passes import _FunctionPass
from bootstrap.s3.pipeline import compile_source, run_source
from bootstrap.s3.targets import BUILTIN_TARGETS, LINUX_X86_64_TARGET, TargetSpec


ROOT = Path(__file__).parents[1]
FORBIDDEN_PUBLIC_PARAMETERS = {"registry", "provider", "target"}


def _module_imports(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            result.add(module)
    return result


def _top_level_imports(path: str) -> set[str]:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    result: set[str] = set()
    for node in tree.body:
        if isinstance(node, ast.Import):
            result.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = "." * node.level + (node.module or "")
            result.add(module)
    return result


def _assert_no_internal_selection_parameters(subject) -> None:
    parameters = inspect.signature(subject).parameters

    assert FORBIDDEN_PUBLIC_PARAMETERS.isdisjoint(parameters)


def test_public_package_exports_remain_small() -> None:
    assert tuple(s3.__all__) == (
        "OptimizationLevel",
        "CompilationCache",
        "CompilationCacheInfo",
        "compile_source",
        "deserialize_ir",
        "run_source",
        "serialize_ir",
    )
    assert "BackendRegistry" not in s3.__all__
    assert "TargetSpec" not in s3.__all__
    assert "PassManager" not in s3.__all__


def test_context_and_target_shapes_remain_narrow() -> None:
    assert tuple(field.name for field in fields(CompilationContext)) == (
        "optimization",
        "mode",
    )
    assert tuple(field.name for field in fields(TargetSpec)) == (
        "name",
        "architecture",
        "environment",
    )

    context = CompilationContext()
    target = LINUX_X86_64_TARGET

    for forbidden in ("target", "entry", "max_frames", "max_instructions"):
        assert not hasattr(context, forbidden)
    for forbidden in ("capabilities", "artifact_kind", "provider"):
        assert not hasattr(target, forbidden)

    assert BUILTIN_TARGETS == (LINUX_X86_64_TARGET,)
    assert "hosted-emulator" not in {target.name for target in BUILTIN_TARGETS}


def test_public_signatures_do_not_expose_registry_provider_or_target() -> None:
    for subject in (
        compile_source,
        run_source,
        execute_assembly,
        generate_native_assembly,
        Emulator,
        X8664Backend,
        NativeToolchain,
    ):
        _assert_no_internal_selection_parameters(subject)


def test_builtin_registry_is_internal_and_not_shared() -> None:
    first = create_builtin_backend_registry()
    second = create_builtin_backend_registry()

    assert first is not second
    assert first.hosted_execution_names == ("hosted-emulator",)
    assert first.native_assembly_targets == ("linux-x86_64",)
    assert second.hosted_execution_names == first.hosted_execution_names
    assert second.native_assembly_targets == first.native_assembly_targets

    hosted = first.get_hosted_execution("hosted-emulator")
    native = first.get_native_assembly("linux-x86_64")

    assert isinstance(hosted, HostedEmulatorBackend)
    assert isinstance(native, LinuxX8664NativeAssemblyBackend)
    assert not hasattr(hosted, "target")
    assert not hasattr(native, "build")
    assert not hasattr(native, "run")
    assert not hasattr(first, "fallback")
    assert not hasattr(first, "capabilities")


def test_import_boundaries_do_not_expose_registry_or_create_cycles() -> None:
    assert ".backends._hosted_execution" not in _module_imports(
        "bootstrap/s3/cli.py"
    )
    assert ".backends._native_assembly" not in _module_imports(
        "bootstrap/s3/cli.py"
    )

    assert ".backends.registry" not in _module_imports(
        "bootstrap/s3/backends/x86_64/toolchain.py"
    )
    assert ".registry" not in _top_level_imports(
        "bootstrap/s3/backends/x86_64/backend.py"
    )
    assert ".pipeline" not in _module_imports("bootstrap/s3/backends/registry.py")
    assert ".backends.registry" not in _top_level_imports("bootstrap/s3/emulator.py")
    assert ".backends._hosted_execution" not in _top_level_imports(
        "bootstrap/s3/emulator.py"
    )
    assert not any(
        item.startswith(".backends")
        for item in _module_imports("bootstrap/s3/targets.py")
    )


def test_routing_helpers_do_not_touch_toolchain_or_processes() -> None:
    for path in (
        "bootstrap/s3/backends/_native_assembly.py",
        "bootstrap/s3/backends/_hosted_execution.py",
    ):
        imports = _module_imports(path)

        assert "subprocess" not in imports
        assert ".x86_64.toolchain" not in imports
        assert ".toolchain" not in imports


def test_pass_manager_contract_stays_private_and_function_major() -> None:
    pass_ = _FunctionPass("identity", lambda function: function)

    assert not hasattr(pass_, "run")
    assert hasattr(pass_, "run_function")
    assert tuple(pass_.name for pass_ in _o1_passes()) == (
        "remove-unreachable-blocks",
        "thread-empty-jumps",
        "ssa-optimizations",
        "fold-constants",
        "eliminate-dead-pure-instructions",
    )

