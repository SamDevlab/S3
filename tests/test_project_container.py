from __future__ import annotations

import pytest

from bootstrap.s3.project_container import (
    ProjectContainer,
    ProjectContainerError,
    ProjectUnit,
)


def test_project_container_manifest_is_deterministic() -> None:
    container = ProjectContainer(
        "demo",
        (
            ProjectUnit("core", ("main.s3", "util.s3")),
            ProjectUnit("tests", ("smoke.s3",)),
        ),
    )
    assert container.manifest == (
        ("core", ("main.s3", "util.s3")),
        ("tests", ("smoke.s3",)),
    )
    assert len(container.manifest_sha256) == 64


def test_project_container_rejects_duplicate_or_unsorted_units() -> None:
    unit = ProjectUnit("core", ("main.s3",))
    with pytest.raises(ProjectContainerError, match="sorted"):
        ProjectContainer("demo", (ProjectUnit("tests", ("t.s3",)), unit))
    with pytest.raises(ProjectContainerError, match="unique"):
        ProjectContainer("demo", (unit, unit))


def test_project_unit_requires_sorted_unique_sources() -> None:
    with pytest.raises(ProjectContainerError, match="sorted and unique"):
        ProjectUnit("core", ("z.s3", "a.s3"))
