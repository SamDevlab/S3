import os
import unittest

from bootstrap.s3.pipeline import run_source_with_buffer_capture


LENGTH_VALUES = [
    -364,
    -200,
    -192,
    -1,
    0,
    1,
    9,
    10,
    11,
    19,
    20,
    42,
    99,
    100,
    101,
    109,
    110,
    112,
    119,
    145,
    152,
    178,
    185,
    190,
    191,
    192,
    199,
    200,
    363,
    364,
]

EXPECTED_LENGTHS = {
    -364: 4,
    -200: 4,
    -192: 4,
    -1: 2,
    0: 1,
    1: 1,
    9: 1,
    10: 2,
    11: 2,
    19: 2,
    20: 2,
    42: 2,
    99: 2,
    100: 3,
    101: 3,
    109: 3,
    110: 3,
    112: 3,
    119: 3,
    145: 3,
    152: 3,
    178: 3,
    185: 3,
    190: 3,
    191: 3,
    192: 3,
    199: 3,
    200: 3,
    363: 3,
    364: 3,
}

BYTE_CASES = [
    (-364, b"-364"),
    (-200, b"-200"),
    (-192, b"-192"),
    (-1, b"-1"),
    (0, b"0"),
    (1, b"1"),
    (9, b"9"),
    (10, b"10"),
    (99, b"99"),
    (100, b"100"),
    (109, b"109"),
    (110, b"110"),
    (112, b"112"),
    (119, b"119"),
    (145, b"145"),
    (152, b"152"),
    (178, b"178"),
    (185, b"185"),
    (190, b"190"),
    (191, b"191"),
    (192, b"192"),
    (199, b"199"),
    (200, b"200"),
    (363, b"363"),
    (364, b"364"),
]

INVALID_BYTE_CASES = [
    (-364, -1),
    (-364, 4),
    (-200, 4),
    (-192, 4),
    (-1, 2),
    (0, -1),
    (0, 1),
    (42, -1),
    (42, 2),
    (191, 3),
    (192, 3),
    (200, 3),
    (364, 3),
    (364, 4),
]


def _zero_array(size: int) -> str:
    return ", ".join(["0"] * size)


def _decimal_test_source() -> str:
    path = os.path.join("examples", "self_hosting", "assembly_renderer_generic_text.s3")
    with open(path, encoding="utf-8") as f:
        src = f.read()

    byte_count = sum(len(expected) for _, expected in BYTE_CASES)
    lines = [
        "fn main() -> tryte:",
        f"    mut lengths: tryte[{len(LENGTH_VALUES)}] = [{_zero_array(len(LENGTH_VALUES))}]",
        f"    mut bytes_buf: tryte[{byte_count}] = [{_zero_array(byte_count)}]",
        f"    mut invalids: tryte[{len(INVALID_BYTE_CASES)}] = [{_zero_array(len(INVALID_BYTE_CASES))}]",
    ]

    for index, value in enumerate(LENGTH_VALUES):
        lines.append(f"    lengths[{index}] = decimal_length({value})")

    offset = 0
    for value, expected in BYTE_CASES:
        for index in range(len(expected)):
            lines.append(f"    bytes_buf[{offset + index}] = decimal_byte_at({value}, {index})")
        offset += len(expected)

    for index, (value, byte_index) in enumerate(INVALID_BYTE_CASES):
        lines.append(f"    invalids[{index}] = decimal_byte_at({value}, {byte_index})")

    lines.append("    return 0")
    test_main = "\n".join(lines)
    return src.replace("fn main() -> tryte:\n    return render_first()", test_main)


def _capture_array(memory: dict[int, list[int | None]], length: int) -> list[int]:
    matches = [values for values in memory.values() if len(values) == length]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one captured array of length {length}, got {len(matches)}")
    return [0 if value is None else value for value in matches[0]]


def _run_decimal_test() -> tuple[list[int], bytes, list[int]]:
    src = _decimal_test_source()
    result, capture = run_source_with_buffer_capture(src, entry="main", max_instructions=200000)
    if result != 0:
        raise ValueError(f"S3 program returned non-zero: {result}")

    memory = capture[-1]
    byte_count = sum(len(expected) for _, expected in BYTE_CASES)
    lengths = _capture_array(memory, len(LENGTH_VALUES))
    bytes_buf = _capture_array(memory, byte_count)
    invalids = _capture_array(memory, len(INVALID_BYTE_CASES))
    return lengths, bytes(bytes_buf), invalids


class TestDecimalFunctions(unittest.TestCase):
    lengths: list[int] = []
    output: bytes = b""
    invalids: list[int] = []

    @classmethod
    def setUpClass(cls):
        cls.lengths, cls.output, cls.invalids = _run_decimal_test()

    def test_decimal_lengths(self):
        for index, value in enumerate(LENGTH_VALUES):
            with self.subTest(value=value):
                self.assertEqual(self.lengths[index], EXPECTED_LENGTHS[value])

    def test_decimal_bytes(self):
        offset = 0
        for value, expected in BYTE_CASES:
            with self.subTest(value=value):
                actual = self.output[offset : offset + len(expected)]
                self.assertEqual(actual, expected)
            offset += len(expected)

    def test_invalid_byte_requests_return_zero(self):
        self.assertEqual(self.invalids, [0] * len(INVALID_BYTE_CASES))

    def test_all_valid_bytes_are_digits(self):
        self.assertTrue(self.output)
        self.assertTrue(all(byte == 45 or 48 <= byte <= 57 for byte in self.output))


if __name__ == "__main__":
    unittest.main()
