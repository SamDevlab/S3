from __future__ import annotations

import pytest

from bootstrap.s3.async_observability import ConcurrencyWaitGraph
from bootstrap.s3.ffi import FFIBufferRegistry, FFIError
from bootstrap.s3.http2 import HPACKError, decode_hpack


def test_concurrency_wait_graph_reports_only_observed_cycles() -> None:
    graph = ConcurrencyWaitGraph(max_tasks=2)
    graph.wait(1, 2)
    graph.wait(2, 1)
    assessment = graph.assess()
    assert assessment.status == "cycle-detected"
    assert set(assessment.cycle) == {1, 2}
    graph.notify(1)
    assert graph.assess().status == "no-cycle-observed"


def test_hpack_static_fields_are_bounded_and_malformed_dynamic_fields_fail_closed() -> None:
    assert decode_hpack(bytes((0x82, 0x84))) == ((":method", "GET"), (":path", "/"))
    # Literal without indexing: 0000 0000, length 3, "foo", length 3, "bar".
    assert decode_hpack(b"\x00\x03foo\x03bar") == (("foo", "bar"),)
    assert decode_hpack(b"\x20") == ()
    with pytest.raises(HPACKError, match="dynamic HPACK index"):
        decode_hpack(b"\xbe")
    with pytest.raises(HPACKError, match="Huffman"):
        decode_hpack(b"\x00\x81\xff\x01a")


def test_ffi_handles_are_bounded_and_release_is_explicit() -> None:
    registry = FFIBufferRegistry(max_buffers=1, max_bytes=4)
    handle = registry.acquire(b"abcd")
    assert registry.view(handle) == b"abcd"
    with pytest.raises(FFIError, match="exceeds bound"):
        registry.write(handle, b"abcde")
    registry.release(handle)
    with pytest.raises(FFIError, match="closed"):
        registry.view(handle)
