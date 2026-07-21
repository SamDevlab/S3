import hashlib
import os
import unittest

from bootstrap.s3.pipeline import run_source_with_buffer_capture


def _decimal_test_source() -> str:
    path = "examples/self_hosting/assembly_renderer_generic_text.s3"
    with open(path) as f:
        src = f.read()

    test_main = """fn main() -> tryte:
    mut lengths: tryte[40] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mut bytes_buf: tryte[60] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mut b_off: tryte = 0
    mut l_off: tryte = 0
    mut l: tryte = 0

    # We will test: -1, 0, 1, 9, 10, 11, 19, 20, 42, 99, 100, 101, 109, 110

    # -1
    lengths[l_off] = decimal_length(-1)
    l_off = l_off + 1

    # 0
    l = decimal_length(0)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(0, 0)
    b_off = b_off + l

    # 1
    l = decimal_length(1)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(1, 0)
    b_off = b_off + l

    # 9
    l = decimal_length(9)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(9, 0)
    b_off = b_off + l

    # 10
    l = decimal_length(10)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(10, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(10, 1)
    b_off = b_off + l

    # 11
    l = decimal_length(11)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(11, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(11, 1)
    b_off = b_off + l

    # 19
    l = decimal_length(19)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(19, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(19, 1)
    b_off = b_off + l

    # 20
    l = decimal_length(20)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(20, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(20, 1)
    b_off = b_off + l

    # 42
    l = decimal_length(42)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(42, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(42, 1)
    b_off = b_off + l

    # 99
    l = decimal_length(99)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(99, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(99, 1)
    b_off = b_off + l

    # 100
    l = decimal_length(100)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(100, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(100, 1)
    bytes_buf[b_off + 2] = decimal_byte_at(100, 2)
    b_off = b_off + l

    # 101
    l = decimal_length(101)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(101, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(101, 1)
    bytes_buf[b_off + 2] = decimal_byte_at(101, 2)
    b_off = b_off + l

    # 109
    l = decimal_length(109)
    lengths[l_off] = l
    l_off = l_off + 1
    bytes_buf[b_off] = decimal_byte_at(109, 0)
    bytes_buf[b_off + 1] = decimal_byte_at(109, 1)
    bytes_buf[b_off + 2] = decimal_byte_at(109, 2)
    b_off = b_off + l

    # 110
    lengths[l_off] = decimal_length(110)
    l_off = l_off + 1

    return 0
"""
    return src.replace("fn main() -> tryte:\n    return render_first()", test_main)


def _run_decimal_test() -> tuple[list[int], bytes]:
    src = _decimal_test_source()
    result, capture = run_source_with_buffer_capture(src, entry="main", max_instructions=200000)
    if result != 0:
        raise ValueError(f"S3 program returned non-zero: {result}")

    memory = capture[-1]
    lengths = []
    for v in memory.get(0, []):
        if v is None or v == 0:
            if v == -1:
                lengths.append(v)
                continue
            if len(lengths) == 14:
                break
            # we don't break if len == 0 etc, we break at len(lengths) == 14
            # wait, 0 is not a valid length, so we just break when we have 14
        lengths.append(v)
        if len(lengths) == 14:
            break

    bytes_buf = memory.get(1, [])
    out = bytearray()
    for i in range(sum(l for l in lengths if l > 0)):
        out.append(bytes_buf[i])

    return lengths, bytes(out)


EXPECTED = {
    0: (1, b"0"),
    1: (1, b"1"),
    9: (1, b"9"),
    10: (2, b"10"),
    11: (2, b"11"),
    19: (2, b"19"),
    20: (2, b"20"),
    42: (2, b"42"),
    99: (2, b"99"),
    100: (3, b"100"),
    101: (3, b"101"),
    109: (3, b"109"),
}

VALUES = [-1, 0, 1, 9, 10, 11, 19, 20, 42, 99, 100, 101, 109, 110]


class TestDecimalFunctions(unittest.TestCase):
    lengths: list[int] = []
    output: bytes = b""

    @classmethod
    def setUpClass(cls):
        cls.lengths, cls.output = _run_decimal_test()

    def test_out_of_bounds(self):
        """Test rejection of -1 and 110 by returning sentinel -1."""
        self.assertEqual(self.lengths[0], -1)  # For -1
        self.assertEqual(self.lengths[13], -1) # For 110

    def _extract_value(self, index: int, value: int) -> tuple[int, bytes]:
        length = self.lengths[index]
        if length <= 0:
            return length, b""

        # Calculate offset
        off = 0
        for i in range(1, index):
            if self.lengths[i] > 0:
                off += self.lengths[i]

        return length, self.output[off:off+length]

    def test_all_expected_values(self):
        # We start checking from index 1 (value 0) up to index 12 (value 109)
        for i, val in enumerate(VALUES[1:13], start=1):
            with self.subTest(value=val):
                expected_len, expected_bytes = EXPECTED[val]
                actual_len, actual_bytes = self._extract_value(i, val)
                self.assertEqual(actual_len, expected_len, f"Length mismatch for {val}")
                self.assertEqual(actual_bytes, expected_bytes, f"Bytes mismatch for {val}")

    def test_no_null_bytes_in_range(self):
        """All bytes in the captured string should be digits."""
        self.assertTrue(len(self.output) > 0)
        self.assertTrue(all(48 <= b <= 57 for b in self.output))


if __name__ == "__main__":
    unittest.main()
