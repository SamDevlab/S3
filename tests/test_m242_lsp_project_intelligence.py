from __future__ import annotations

import pytest

from bootstrap.s3.lsp import LanguageServer
from bootstrap.s3.lsp_transport import JsonRpcTransport


pytestmark = pytest.mark.s3_fast


LIB = (
    "module lib\n"
    "export fn add(value: i64) -> i64:\n"
    "    return value\n"
)
MAIN = (
    "module main\n"
    "from lib import add as sum\n"
    "fn main() -> i64:\n"
    "    return sum(3)\n"
)


def test_cross_file_definition_references_and_rename_follow_aliases() -> None:
    server = LanguageServer()
    main_uri = "file:///workspace/main.s3"
    lib_uri = "file:///workspace/lib.s3"

    server.did_open(main_uri, MAIN, 1)
    server.did_open(lib_uri, LIB, 1)

    definition = server.definition(main_uri, {"line": 3, "character": 12})
    assert definition[0]["uri"] == lib_uri

    references = server.references(main_uri, {"line": 3, "character": 12})
    assert [item["uri"] for item in references] == [lib_uri, main_uri, main_uri]
    assert [item["range"]["start"] for item in references] == [
        {"line": 1, "character": 10},
        {"line": 1, "character": 23},
        {"line": 3, "character": 11},
    ]

    changes = server.rename(main_uri, {"line": 3, "character": 12}, "total")
    assert sorted(changes["changes"]) == [lib_uri, main_uri]
    assert len(changes["changes"][lib_uri]) == 1
    assert len(changes["changes"][main_uri]) == 2

    declaration_references = server.references(lib_uri, {"line": 1, "character": 11})
    assert [item["uri"] for item in declaration_references] == [lib_uri, main_uri, main_uri]


def test_stale_document_versions_are_rejected() -> None:
    server = LanguageServer()
    uri = "file:///workspace/main.s3"
    server.did_open(uri, MAIN, 4)
    with pytest.raises(ValueError, match="increase monotonically"):
        server.did_change(uri, MAIN, 4)


def test_ambiguous_imports_publish_diagnostic_and_fail_closed() -> None:
    server = LanguageServer()
    server.did_open(
        "file:///workspace/a.s3",
        "module a\nexport fn same() -> i64:\n    return 1\n",
        1,
    )
    server.did_open(
        "file:///workspace/b.s3",
        "module b\nexport fn same() -> i64:\n    return 2\n",
        1,
    )
    main_uri = "file:///workspace/main.s3"
    diagnostics = server.did_open(
        main_uri,
        (
            "module main\n"
            "from a import same\n"
            "from b import same\n"
            "fn main() -> i64:\n"
            "    return same()\n"
        ),
        1,
    )
    assert diagnostics["diagnostics"][0]["code"] == "S3E_SEMANTIC_INVALID_PROGRAM"
    assert server.definition(main_uri, {"line": 3, "character": 12}) == []
    assert server.references(main_uri, {"line": 3, "character": 12}) == []


def test_workspace_symbols_are_cross_file_and_deterministic() -> None:
    server = LanguageServer()
    server.did_open("file:///workspace/main.s3", MAIN, 1)
    server.did_open("file:///workspace/lib.s3", LIB, 1)
    symbols = server.workspace_symbols("ad")
    assert [(item["name"], item["uri"]) for item in symbols] == [
        ("add", "file:///workspace/lib.s3"),
    ]


def test_cancelled_request_is_rejected_before_dispatch() -> None:
    transport = JsonRpcTransport()
    assert transport.dispatch(
        {
            "jsonrpc": "2.0",
            "method": "$/cancelRequest",
            "params": {"id": 7},
        }
    ) is None
    response = transport.dispatch(
        {"jsonrpc": "2.0", "id": 7, "method": "workspace/symbol", "params": {"query": ""}}
    )
    assert response is not None
    assert response.error == {"code": -32800, "message": "request cancelled"}
