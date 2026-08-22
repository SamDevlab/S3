from __future__ import annotations

from bootstrap.s3.docs_generator import render_json, render_markdown
from bootstrap.s3.formatter import format_source, source_digest


SOURCE = (
    "module demo\n"
    "export fn main() -> i64:\n"
    "    return zeta(0)\n"
    "export fn zeta(value: i64) -> i64:\n"
    "    return value  # keep this comment\n"
    "fn hidden() -> i64:\n"
    "    return 0\n"
)


def test_formatter_preserves_comments_unicode_and_is_idempotent() -> None:
    source = "# café  \r\nfn main() -> i64:  \r\n    return 0  \r\n"
    formatted = format_source(source)
    assert "# café" in formatted
    assert formatted.endswith("\n")
    assert format_source(formatted) == formatted
    assert source_digest(formatted) == source_digest(format_source(formatted))


def test_documentation_is_ast_based_canonical_and_visibility_aware() -> None:
    markdown = render_markdown(SOURCE)
    assert "`zeta(value: i64) -> i64`" in markdown
    assert "hidden" not in markdown
    assert markdown == render_markdown(SOURCE)
    payload = render_json(SOURCE)
    assert '"schema": "s3-api-documentation"' in payload
