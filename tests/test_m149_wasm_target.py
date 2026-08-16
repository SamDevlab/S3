from __future__ import annotations

import hashlib

import pytest

from bootstrap.s3.wasm_target import (
    LOGICAL_S3_INSTRUCTION_LIMIT,
    WASI_IMPORT_MANIFEST,
    WASI_MEMORY_LIMIT_BYTES,
    WASI_MEMORY_LIMIT_PAGES,
    WASM32_WASIP1_S3_TARGET,
    WasmTargetError,
    artifact_identity,
    build_i32_fixture,
    render_i32_fixture,
    validate_core_module,
)


def test_wasi_target_identity_and_safety_limits_are_explicit() -> None:
    assert WASM32_WASIP1_S3_TARGET.name == "wasm32-wasip1-s3"
    assert WASM32_WASIP1_S3_TARGET.environment == "wasi-preview1"
    assert WASI_MEMORY_LIMIT_BYTES == 64 * 1024 * 1024
    assert WASI_MEMORY_LIMIT_PAGES == 1024
    assert LOGICAL_S3_INSTRUCTION_LIMIT == 100000


def test_import_manifest_allows_declared_capabilities_and_denies_surface_growth() -> None:
    assert WASI_IMPORT_MANIFEST.imports_for_capabilities(("argv",)) == (
        "args_sizes_get",
        "args_get",
    )
    assert WASI_IMPORT_MANIFEST.validate(("args_get", "proc_exit")) == (
        "args_get",
        "proc_exit",
    )
    with pytest.raises(WasmTargetError, match="forbidden"):
        WASI_IMPORT_MANIFEST.validate(("random_get",))
    with pytest.raises(WasmTargetError, match="unsupported"):
        WASI_IMPORT_MANIFEST.validate(("unknown_import",))
    with pytest.raises(WasmTargetError, match="exact provider"):
        WASI_IMPORT_MANIFEST.imports_for_capabilities(("network.tcp",))


def test_core_fixture_is_deterministic_and_has_canonical_section_order() -> None:
    first = render_i32_fixture(42)
    second = render_i32_fixture(42)
    assert first == second
    assert first.startswith(b"\x00asm\x01\x00\x00\x00")
    assert validate_core_module(first) == (1, 3, 5, 7, 10)
    assert hashlib.sha256(first).hexdigest() == hashlib.sha256(second).hexdigest()
    assert b"/" not in first


def test_fixture_artifact_identity_uses_only_locked_inputs() -> None:
    first = build_i32_fixture(7, source=b"source", lockfile=b"lock")
    second = build_i32_fixture(7, source=b"source", lockfile=b"lock")
    changed_source = build_i32_fixture(7, source=b"source-2", lockfile=b"lock")
    changed_lock = build_i32_fixture(7, source=b"source", lockfile=b"lock-2")
    assert first.module_bytes == second.module_bytes
    assert first.artifact_sha256 == second.artifact_sha256
    assert first.identity == second.identity
    assert first.identity != changed_source.identity
    assert first.identity != changed_lock.identity
    assert first.source_sha256 == hashlib.sha256(b"source").hexdigest()


def test_identity_rejects_noncanonical_hashes_and_environment_fields() -> None:
    with pytest.raises(WasmTargetError, match="lowercase SHA-256"):
        artifact_identity(source_sha256="A" * 64, lock_sha256="0" * 64)
    with pytest.raises(WasmTargetError, match="non-empty"):
        artifact_identity(
            source_sha256="0" * 64,
            lock_sha256="0" * 64,
            compiler_version="",
        )


def test_no_runtime_is_claimed_by_structural_artifact_api() -> None:
    artifact = build_i32_fixture(0)
    assert artifact.target == WASM32_WASIP1_S3_TARGET
    assert artifact.module_bytes
    assert not hasattr(artifact, "run")
