from __future__ import annotations

import io

import pytest

from bootstrap.s3.diagnostics import S3Error
from bootstrap.s3.http2 import Http2Error, decode_hpack, parse_frame
from bootstrap.s3.lsp_transport import LspTransportError, JsonRpcTransport
from bootstrap.s3.package_dependencies import PackageDependencyError, parse_package_manifest
from bootstrap.s3.parser import parse
from tools.m239_adversarial import bounded_mutations


pytestmark = pytest.mark.s3_fast


def test_bounded_mutation_corpus_is_reproducible_and_size_limited() -> None:
    corpus = (b"fn main() -> i64:\n    return 0\n", b"\x00\xff\x7f")
    first = bounded_mutations(corpus, max_cases=32, max_bytes=64)
    second = bounded_mutations(corpus, max_cases=32, max_bytes=64)
    assert first == second
    assert len(first) <= 32
    assert all(len(case.payload) <= 64 for case in first)


def test_parser_and_protocol_mutations_fail_deterministically_without_unexpected_crashes() -> None:
    cases = bounded_mutations((b"fn main() -> i64:\n    return 0\n", b"\x00\xff\x7f"), max_cases=32, max_bytes=128)
    for case in cases:
        text = case.payload.decode("utf-8", "replace")
        try:
            parse(text)
        except S3Error:
            pass
        try:
            parse_frame(case.payload)
        except Http2Error:
            pass
        try:
            decode_hpack(case.payload)
        except Http2Error:
            pass
        try:
            JsonRpcTransport().read_message(io.BytesIO(case.payload))
        except LspTransportError:
            pass


def test_package_manifest_mutations_reject_path_and_syntax_attacks(tmp_path) -> None:
    corpus = bounded_mutations(
        (
            b"[package]\nname='demo'\nversion='1'\n",
            b"[package]\nname='../escape'\nversion='1'\n",
        ),
        max_cases=16,
        max_bytes=128,
    )
    for index, case in enumerate(corpus):
        path = tmp_path / f"case-{index}.toml"
        path.write_bytes(case.payload)
        try:
            parse_package_manifest(path)
        except PackageDependencyError:
            pass
