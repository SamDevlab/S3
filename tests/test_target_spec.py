from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from bootstrap.s3.targets import (
    BUILTIN_TARGETS,
    LINUX_X86_64_TARGET,
    TargetCatalog,
    TargetSpec,
    UnknownTargetError,
    builtin_target_catalog,
)


def test_linux_x86_64_target_is_real_and_stable() -> None:
    target = LINUX_X86_64_TARGET

    assert target.name == "linux-x86_64"
    assert target.architecture == "x86_64"
    assert target.environment == "linux"


def test_target_specs_are_immutable_and_hashable() -> None:
    equivalent = TargetSpec(
        name="linux-x86_64",
        architecture="x86_64",
        environment="linux",
    )

    assert LINUX_X86_64_TARGET == equivalent
    assert hash(LINUX_X86_64_TARGET) == hash(equivalent)
    with pytest.raises(FrozenInstanceError):
        LINUX_X86_64_TARGET.name = "other"  # type: ignore[misc]


def test_builtin_target_catalog_contains_only_real_targets() -> None:
    catalog = builtin_target_catalog()

    assert catalog.names == ("linux-x86_64",)
    assert "hosted-emulator" not in catalog.names
    assert "emulator" not in catalog.names
    assert "s3-assembly" not in catalog.names
    assert catalog.targets == tuple(sorted(BUILTIN_TARGETS, key=lambda item: item.name))


def test_target_catalog_rejects_unknown_and_duplicate_targets() -> None:
    catalog = builtin_target_catalog()

    with pytest.raises(UnknownTargetError, match="unknown target"):
        catalog.get("hosted-emulator")
    with pytest.raises(UnknownTargetError, match="unknown target"):
        catalog.get("windows-x86_64")

    duplicate = TargetSpec(
        name="linux-x86_64",
        architecture="x86_64",
        environment="test",
    )
    with pytest.raises(ValueError, match="duplicate target"):
        TargetCatalog((*BUILTIN_TARGETS, duplicate))


def test_target_catalog_has_no_shared_mutable_state() -> None:
    first = builtin_target_catalog()
    second = builtin_target_catalog()

    assert first is not second
    assert first.targets == second.targets
    with pytest.raises(FrozenInstanceError):
        first._targets = ()  # type: ignore[misc]
