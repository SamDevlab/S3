"""M2.55 canonical source identity, line mapping, and span contracts."""

from __future__ import annotations

import pytest

from bootstrap.s3.source_manager import (
    SourceBoundsError,
    SourceCapacityError,
    SourceManager,
    SourceManagerError,
)


def test_source_manager_assigns_stable_ids_across_multiple_files() -> None:
    manager = SourceManager()
    first = manager.add("main.s3", "alpha")
    second = manager.add("lib.s3", "beta")
    assert (first, second) == (0, 1)
    assert manager.id_for_name("lib.s3") == second
    assert manager.file(first).name == "main.s3"
    assert manager.file(second).text == "beta"


def test_source_manager_maps_offsets_to_one_based_lines_and_columns() -> None:
    manager = SourceManager()
    source_id = manager.add("unicode.s3", "ab\r\nλx\nlast")
    assert manager.location(source_id, 0).line == 1
    assert manager.location(source_id, 5).line == 2
    assert manager.location(source_id, 5).column == 2
    assert manager.location(source_id, len("ab\r\nλx\nlast")).line == 3
    assert manager.line_text(source_id, 1) == "ab"
    assert manager.line_text(source_id, 2) == "λx"


def test_source_manager_creates_canonical_spans_and_extracts_text() -> None:
    manager = SourceManager()
    source_id = manager.add("main.s3", "let value")
    span = manager.span(source_id, 4, 9)
    assert (span.source_id, span.start, span.end) == (source_id, 4, 9)
    assert manager.text(span) == "value"
    with pytest.raises(SourceBoundsError):
        manager.span(source_id, 0, 100)


def test_source_manager_fails_closed_on_duplicate_names_and_capacity() -> None:
    manager = SourceManager(max_files=1, max_total_bytes=4)
    manager.add("main.s3", "S3")
    with pytest.raises(SourceManagerError):
        manager.add("main.s3", "new")
    with pytest.raises(SourceCapacityError):
        manager.add("lib.s3", "x")


def test_source_manager_rejects_unknown_identity_and_invalid_offsets() -> None:
    manager = SourceManager()
    source_id = manager.add("main.s3", "abc")
    with pytest.raises(SourceManagerError):
        manager.file(99)
    with pytest.raises(SourceBoundsError):
        manager.location(source_id, 4)
    with pytest.raises(SourceBoundsError):
        manager.line_text(source_id, 2)
