from __future__ import annotations

from pathlib import Path

import pytest

from bootstrap.s3.developer_experience import (
    DeveloperExperienceError,
    format_diagnostic,
    format_source,
    init_project,
    project_summary,
)
from bootstrap.s3.diagnostics import SemanticError, SourceLocation


def test_source_formatter_is_lf_canonical_and_idempotent() -> None:
    source = "fn main() -> i64:  \r\n    return 0  \r\n\r\n"
    formatted = format_source(source)
    assert formatted == "fn main() -> i64:\n    return 0\n"
    assert format_source(formatted) == formatted


def test_project_init_creates_a_valid_project_and_stable_summary(tmp_path: Path) -> None:
    manifest = init_project(tmp_path / "demo", "demo")
    assert manifest.name == "s3.toml"
    assert project_summary(tmp_path / "demo") == {
        "name": "demo",
        "version": "0.1.0",
        "entrypoint": "main",
        "profile": "hosted",
        "source_roots": ("src",),
        "sources": ("src/main.s3",),
        "dependencies": (),
    }
    with pytest.raises(DeveloperExperienceError, match="already exists"):
        init_project(tmp_path / "demo", "demo")


def test_diagnostic_summary_is_machine_code_and_location_stable() -> None:
    error = SemanticError("bad value", SourceLocation(4, 2, 5))
    assert format_diagnostic(error, file="main.s3") == (
        "main.s3:2:5: semantic: [S3E_SEMANTIC_INVALID_PROGRAM] "
        "2:5: semantic error: bad value"
    )
