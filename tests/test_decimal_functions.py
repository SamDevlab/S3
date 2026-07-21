import hashlib
import os
import unittest

from bootstrap.s3.pipeline import run_source_with_buffer_capture


def _decimal_test_source() -> str:
    """Load the generic renderer and replace main with a decimal test harness."""
    path = "examples/self_hosting/assembly_renderer_generic_text.s3"
    with open(path) as f:
        src = f.read()

    # Build a test main that calls decimal_byte_at for each boundary value
    # and stores results in a buffer for capture.
    test_main = """fn main() -> tryte:
    mut buf: tryte[40] = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
    mut off: tryte = 0
    # value=0 -> "0"
    buf[off] = decimal_byte_at(0, 0)
    off = off + 1
    # value=1 -> "1"
    buf[off] = decimal_byte_at(1, 0)
    off = off + 1
    # value=9 -> "9"
    buf[off] = decimal_byte_at(9, 0)
    off = off + 1
    # value=10 -> "10"
    buf[off] = decimal_byte_at(10, 0)
    off = off + 1
    buf[off] = decimal_byte_at(10, 1)
    off = off + 1
    # value=11 -> "11"
    buf[off] = decimal_byte_at(11, 0)
    off = off + 1
    buf[off] = decimal_byte_at(11, 1)
    off = off + 1
    # value=19 -> "19"
    buf[off] = decimal_byte_at(19, 0)
    off = off + 1
    buf[off] = decimal_byte_at(19, 1)
    off = off + 1
    # value=20 -> "20"
    buf[off] = decimal_byte_at(20, 0)
    off = off + 1
    buf[off] = decimal_byte_at(20, 1)
    off = off + 1
    # value=42 -> "42"
    buf[off] = decimal_byte_at(42, 0)
    off = off + 1
    buf[off] = decimal_byte_at(42, 1)
    off = off + 1
    # value=99 -> "99"
    buf[off] = decimal_byte_at(99, 0)
    off = off + 1
    buf[off] = decimal_byte_at(99, 1)
    off = off + 1
    # value=100 -> "100"
    buf[off] = decimal_byte_at(100, 0)
    off = off + 1
    buf[off] = decimal_byte_at(100, 1)
    off = off + 1
    buf[off] = decimal_byte_at(100, 2)
    off = off + 1
    # value=101 -> "101"
    buf[off] = decimal_byte_at(101, 0)
    off = off + 1
    buf[off] = decimal_byte_at(101, 1)
    off = off + 1
    buf[off] = decimal_byte_at(101, 2)
    off = off + 1
    # value=109 -> "109"
    buf[off] = decimal_byte_at(109, 0)
    off = off + 1
    buf[off] = decimal_byte_at(109, 1)
    off = off + 1
    buf[off] = decimal_byte_at(109, 2)
    off = off + 1
    return 0
"""
    return src.replace("fn main() -> tryte:\n    return render_first()", test_main)


def _run_decimal_test() -> bytes:
    """Run the decimal test harness and return captured buffer bytes."""
    src = _decimal_test_source()
    result, capture = run_source_with_buffer_capture(src, entry="main", max_instructions=200000)
    if result != 0:
        raise ValueError(f"S3 program returned non-zero: {result}")
    if not capture:
        raise ValueError("memory capture is empty")
    memory = capture[-1]
    buf = memory.get(0, [])
    out = bytearray()
    for v in buf:
        if v is None:
            break
        out.append(v)
    return bytes(out)


EXPECTED = {
    # value -> expected ASCII string
    0: b"0",
    1: b"1",
    9: b"9",
    10: b"10",
    11: b"11",
    19: b"19",
    20: b"20",
    42: b"42",
    99: b"99",
    100: b"100",
    101: b"101",
    109: b"109",
}


class TestDecimalFunctions(unittest.TestCase):

    output: bytes = b""

    @classmethod
    def setUpClass(cls):
        cls.output = _run_decimal_test()

    def _extract_value(self, value: int) -> bytes:
        """Find the expected segment in the output buffer."""
        off = 0
        for v in sorted(EXPECTED.keys()):
            seg_len = len(EXPECTED[v])
            if v == value:
                return self.output[off:off+seg_len]
            off += seg_len
        self.fail(f"value {value} not in EXPECTED")

    def test_value_0(self):
        self.assertEqual(self._extract_value(0), b"0")

    def test_value_1(self):
        self.assertEqual(self._extract_value(1), b"1")

    def test_value_9(self):
        self.assertEqual(self._extract_value(9), b"9")

    def test_value_10(self):
        self.assertEqual(self._extract_value(10), b"10")

    def test_value_11(self):
        self.assertEqual(self._extract_value(11), b"11")

    def test_value_19(self):
        self.assertEqual(self._extract_value(19), b"19")

    def test_value_20(self):
        self.assertEqual(self._extract_value(20), b"20")

    def test_value_42(self):
        self.assertEqual(self._extract_value(42), b"42")

    def test_value_99(self):
        self.assertEqual(self._extract_value(99), b"99")

    def test_value_100(self):
        self.assertEqual(self._extract_value(100), b"100")

    def test_value_101(self):
        self.assertEqual(self._extract_value(101), b"101")

    def test_value_109(self):
        self.assertEqual(self._extract_value(109), b"109")

    def test_no_null_bytes_in_range(self):
        """All boundary values should produce non-null, printable ASCII.
        Trim at first null to separate actual data from buffer padding."""
        trimmed = self.output.split(b"\x00")[0]
        self.assertTrue(len(trimmed) > 0)
        # All non-null bytes should be digit ASCII
        self.assertTrue(all(48 <= b <= 57 for b in trimmed))

    def test_all_are_printable_ascii(self):
        """All bytes in the decimal output should be printable digits."""
        for b in self.output:
            if b == 0:
                break
            self.assertIn(b, range(48, 58), f"byte {b} is not a digit")


if __name__ == "__main__":
    unittest.main()
