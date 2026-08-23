from __future__ import annotations

import pytest

from bootstrap.s3.http2 import HPACKDecoder, HPACKError, decode_hpack


pytestmark = pytest.mark.s3_contract


def test_rfc7541_huffman_literal_decodes_with_static_fields() -> None:
    block = bytes.fromhex("828684418cf1e3c2e5f23a6ba0ab90f4ff")
    assert decode_hpack(block) == (
        (":method", "GET"),
        (":scheme", "http"),
        (":path", "/"),
        (":authority", "www.example.com"),
    )


def test_incremental_indexing_persists_and_indexes_newest_dynamic_entry() -> None:
    decoder = HPACKDecoder()
    first = b"\x40\x06x-test\x05hello"
    assert decode_hpack(first, decoder=decoder) == (("x-test", "hello"),)
    assert decoder.dynamic_table == (("x-test", "hello"),)
    assert decode_hpack(b"\xbe", decoder=decoder) == (("x-test", "hello"),)

    second = b"\x40\x06y-test\x03two"
    assert decode_hpack(second, decoder=decoder) == (("y-test", "two"),)
    assert decoder.dynamic_table[:2] == (("y-test", "two"), ("x-test", "hello"))


def test_dynamic_name_index_and_never_indexed_literal() -> None:
    decoder = HPACKDecoder()
    assert decode_hpack(b"\x40\x01x\x01a", decoder=decoder) == (("x", "a"),)
    assert decode_hpack(b"\x0f\x2f\x01b", decoder=decoder) == (("x", "b"),)
    assert decode_hpack(b"\x10\x05token\x03abc", decoder=decoder) == (("token", "abc"),)
    assert decoder.dynamic_table == (("x", "a"),)


def test_table_size_update_evicts_entries_and_respects_configured_bound() -> None:
    decoder = HPACKDecoder(max_dynamic_table_bytes=128)
    assert decode_hpack(b"\x40\x01x\x01a", decoder=decoder) == (("x", "a"),)
    assert decoder.dynamic_table_size == 34
    assert decode_hpack(b"\x20", decoder=decoder) == ()
    assert decoder.table_size_limit == 0
    assert decoder.dynamic_table == ()
    with pytest.raises(HPACKError, match="dynamic HPACK index"):
        decode_hpack(b"\xbe", decoder=decoder)
    with pytest.raises(HPACKError, match="exceeds configured bound"):
        decode_hpack(b"\x3f\x62", decoder=decoder)


def test_table_size_updates_must_precede_headers_and_state_is_atomic() -> None:
    decoder = HPACKDecoder()
    assert decode_hpack(b"\x40\x01x\x01a", decoder=decoder) == (("x", "a"),)
    with pytest.raises(HPACKError, match="must precede"):
        decode_hpack(b"\x82\x20", decoder=decoder)
    assert decoder.dynamic_table == (("x", "a"),)
    assert decoder.table_size_limit == 4096


def test_dynamic_entry_larger_than_table_is_not_retained() -> None:
    decoder = HPACKDecoder(max_dynamic_table_bytes=33)
    assert decode_hpack(b"\x40\x01x\x01a", decoder=decoder) == (("x", "a"),)
    assert decoder.dynamic_table == ()
    assert decoder.dynamic_table_size == 0


@pytest.mark.parametrize("block", [b"\x00\x81\x00\x01a", b"\x00\x81\xff\x01a"])
def test_malformed_huffman_padding_fails_closed(block: bytes) -> None:
    with pytest.raises(HPACKError, match="Huffman"):
        decode_hpack(block)


def test_header_count_and_retained_bytes_remain_bounded() -> None:
    block = b"\x00\x01a\x01b\x00\x01c\x01d"
    with pytest.raises(HPACKError, match="decoded headers"):
        decode_hpack(block, max_headers=1)
    with pytest.raises(HPACKError, match="decoded headers"):
        decode_hpack(b"\x00\x03abc\x03def", max_header_bytes=4)
