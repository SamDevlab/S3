from __future__ import annotations

from hashlib import sha256

import pytest

from bootstrap.s3.aarch64_toolchain import create_cross_platform_backend_registry
from bootstrap.s3.backend_parity import BackendParityError, build_backend_parity_matrix
from bootstrap.s3.backends.registry import create_builtin_backend_registry
from bootstrap.s3.pipeline import compile_source


def _source() -> str:
    return (
        "fn add(left: i64, right: i64) -> i64:\n"
        "    return left + right\n"
        "fn main() -> i64:\n"
        "    return add(2, 3)\n"
    )


def test_registered_backends_share_source_identity_and_hosted_semantics() -> None:
    source = _source()
    compilation = compile_source(source)
    matrix = build_backend_parity_matrix(
        create_cross_platform_backend_registry(),
        compilation.assembly,
        source_sha256=sha256(source.encode()).hexdigest(),
    )
    assert matrix.structural_valid
    assert matrix.target_names == ("linux-aarch64", "linux-x86_64", "macos-arm64")
    assert matrix.hosted_result == 5
    assert {item.native_status for item in matrix.targets} == {"STRUCTURAL_ONLY_TOOLCHAIN_DEFERRED"}


def test_parity_artifacts_are_deterministic() -> None:
    source = _source()
    compilation = compile_source(source)
    registry = create_cross_platform_backend_registry()
    identity = sha256(source.encode()).hexdigest()
    first = build_backend_parity_matrix(registry, compilation.assembly, source_sha256=identity)
    second = build_backend_parity_matrix(registry, compilation.assembly, source_sha256=identity)
    assert first == second


def test_builtin_registry_does_not_silently_fallback_to_missing_targets() -> None:
    source = _source()
    compilation = compile_source(source)
    with pytest.raises(BackendParityError, match="not registered"):
        build_backend_parity_matrix(
            create_builtin_backend_registry(),
            compilation.assembly,
            source_sha256=sha256(source.encode()).hexdigest(),
        )
