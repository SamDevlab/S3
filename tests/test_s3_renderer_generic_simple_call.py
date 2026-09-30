import hashlib
import inspect
import os
import re
import unittest
from collections import Counter

from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _golden_file_bytes,
)


EXPECTED_SHA256 = FIXTURE_METADATA["simple_call_generic"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["simple_call_generic"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["simple_call_generic"].expected_lines
EXPECTED_EVENT_COUNT = 175
EXPECTED_DISTRIBUTION = Counter(
    {
        1: 28,
        2: 21,
        3: 6,
        4: 20,
        5: 12,
        6: 52,
        7: 13,
        9: 2,
        10: 21,
    }
)


def _read_source(meta_name: str) -> str:
    meta = FIXTURE_METADATA[meta_name]
    s3_path = os.path.join(*meta.s3_path.split("/"))
    with open(s3_path, encoding="utf-8") as f:
        return f.read()


def _function_body(source: str, name: str) -> str:
    match = re.search(
        rf"^fn {name}\([^\n]*\)\s*->\s*tryte:\n(.*?)(?=^fn |\Z)",
        source,
        re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"{name} not found")
    return match.group(1)


def _event_count(source: str, prefix: str) -> int:
    match = re.search(
        rf"^fn {prefix}_event_count\(\)\s*->\s*tryte:\n\s*return\s+(\d+)",
        source,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"{prefix}_event_count not found")
    return int(match.group(1))


def _indexed_returns(source: str, function_name: str) -> tuple[dict[int, int], list[int]]:
    body = _function_body(source, function_name)
    pairs = re.findall(
        r"match index <=> (\d+):.*?\n\s*0:\n\s*return (-?\d+)",
        body,
        re.DOTALL,
    )
    indices = [int(index) for index, _ in pairs]
    values = {int(index): int(value) for index, value in pairs}
    return values, indices


def _event_plan(source: str, prefix: str) -> list[tuple[int, int]]:
    count = _event_count(source, prefix)
    kinds, _ = _indexed_returns(source, f"{prefix}_event_kind")
    args, _ = _indexed_returns(source, f"{prefix}_event_arg0")
    return [(kinds[index], args[index]) for index in range(count)]


def _length_table(source: str, prefix: str) -> dict[int, int]:
    body = _function_body(source, f"{prefix}_length")
    result: dict[int, int] = {}
    for match in re.finditer(
        r"match id <=> (\d+):(.*?)(?=\n    match id <=>|\n    return 0)",
        body,
        re.DOTALL,
    ):
        return_match = re.search(r"\n\s*0:\n\s*return (\d+)", match.group(2))
        if return_match:
            result[int(match.group(1))] = int(return_match.group(1))
    return result


def _text_table(source: str, prefix: str) -> dict[int, str]:
    lengths = _length_table(source, prefix)
    body = _function_body(source, f"{prefix}_byte")
    result: dict[int, str] = {}
    for match in re.finditer(
        r"match id <=> (\d+):(.*?)(?=\n    match id <=>|\n    return 0)",
        body,
        re.DOTALL,
    ):
        id_value = int(match.group(1))
        returns = [int(value) for value in re.findall(r"\n\s*0:\n\s*return (\d+)", match.group(2))]
        result[id_value] = "".join(chr(value) for value in returns[: lengths[id_value]])
    return result


def _event_text(
    kind: int,
    arg0: int,
    fragments: dict[int, str],
    symbols: dict[int, str],
    opcodes: dict[int, str],
) -> str:
    if kind == 1:
        return fragments[arg0]
    if kind == 2:
        return symbols[arg0]
    if kind == 3:
        return opcodes[arg0]
    if kind == 4:
        return str(arg0)
    if kind == 5:
        return ":"
    if kind == 6:
        return " " * arg0
    if kind == 7:
        return ","
    if kind == 9:
        return "->"
    if kind == 10:
        return "\n"
    raise AssertionError(f"unknown event kind: {kind}")


def _reconstruct_bytes(source: str, events: list[tuple[int, int]]) -> bytes:
    fragments = _text_table(source, "fragment")
    symbols = _text_table(source, "symbol")
    opcodes = _text_table(source, "opcode")
    text = "".join(_event_text(kind, arg0, fragments, symbols, opcodes) for kind, arg0 in events)
    return text.encode("utf-8")


class TestGenericSimpleCallStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = FIXTURE_METADATA["simple_call_generic"]
        cls.source = _read_source("simple_call_generic")
        from bootstrap.s3.pipeline import compile_source

        cls.ir = compile_source(cls.source).ir
        cls.fn_names = {fn.name for fn in cls.ir.functions}
        cls.events = _event_plan(cls.source, "simple_call")
        cls.rendered = _reconstruct_bytes(cls.source, cls.events)
        cls.golden = _golden_file_bytes(cls.meta.golden_path)

    def test_structure_class_does_not_call_vm_helpers(self):
        forbidden = (
            "run_" + "source",
            "run_" + "source_with_buffer_capture",
            "_capture_fixture_output",
        )
        for name, method in type(self).__dict__.items():
            if name == "test_structure_class_does_not_call_vm_helpers":
                continue
            if not inspect.isfunction(method) and not isinstance(method, classmethod):
                continue
            if isinstance(method, classmethod):
                method = method.__func__
            method_source = inspect.getsource(method)
            for token in forbidden:
                with self.subTest(method=name, token=token):
                    self.assertNotIn(token, method_source)
            self.assertNotIn("legacy", method_source.lower())

    def test_metadata_and_program_exist(self):
        self.assertIn("simple_call_generic", FIXTURE_METADATA)
        self.assertTrue(os.path.isfile(os.path.join(*self.meta.s3_path.split("/"))))

    def test_program_compiles(self):
        self.assertIsNotNone(self.ir)

    def test_entry_and_dispatch_functions_present(self):
        self.assertIn("render_simple_call", self.fn_names)
        self.assertIn("simple_call_event_kind", self.fn_names)
        self.assertIn("simple_call_event_arg0", self.fn_names)
        self.assertIn("simple_call_event_count", self.fn_names)
        self.assertIn("event_length", self.fn_names)
        self.assertIn("event_byte", self.fn_names)

    def test_shared_tables_present(self):
        for name in (
            "fragment_length",
            "fragment_byte",
            "symbol_length",
            "symbol_byte",
            "opcode_length",
            "opcode_byte",
            "decimal_length",
            "decimal_tens_byte",
            "decimal_ones_byte",
            "decimal_byte_at",
        ):
            self.assertIn(name, self.fn_names)

    def test_no_position_or_raw_byte_helpers(self):
        self.assertNotIn("line_complete", self.fn_names)
        self.assertNotIn("event_by_position", self.fn_names)
        self.assertNotIn("raw_byte", self.source.lower())
        self.assertNotIn(11, [kind for kind, _ in self.events])

    def test_event_indices_are_continuous(self):
        count = _event_count(self.source, "simple_call")
        _, kind_indices = _indexed_returns(self.source, "simple_call_event_kind")
        _, arg_indices = _indexed_returns(self.source, "simple_call_event_arg0")
        expected = list(range(count))
        self.assertEqual(sorted(kind_indices), expected)
        self.assertEqual(sorted(arg_indices), expected)
        self.assertEqual(len(kind_indices), len(set(kind_indices)))
        self.assertEqual(len(arg_indices), len(set(arg_indices)))

    def test_event_count_and_distribution_are_preserved(self):
        self.assertEqual(len(self.events), EXPECTED_EVENT_COUNT)
        self.assertEqual(Counter(kind for kind, _ in self.events), EXPECTED_DISTRIBUTION)

    def test_last_event_is_newline(self):
        self.assertEqual(self.events[-1][0], 10)

    def test_reconstructed_output_matches_canonical_golden(self):
        self.assertEqual(len(self.rendered), EXPECTED_BYTES)
        self.assertEqual(self.rendered.count(10), EXPECTED_LINES)
        self.assertEqual(self.rendered, self.golden)
        self.assertEqual(hashlib.sha256(self.rendered).hexdigest(), EXPECTED_SHA256)


class TestGenericSimpleCallExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = FIXTURE_METADATA["simple_call_generic"]
        cls.source = _read_source("simple_call_generic")
        cls.output = _capture_fixture_output(
            cls.source,
            cls.meta.buffer_count,
            cls.meta.buffer_offset,
            cls.meta.entry,
            cls.meta.max_instructions,
            cls.meta.expected_bytes,
        )
        cls.golden = _golden_file_bytes(cls.meta.golden_path)
        legacy_meta = FIXTURE_METADATA["simple_call"]
        legacy_source = _read_source("simple_call")
        cls.legacy = _capture_fixture_output(
            legacy_source,
            legacy_meta.buffer_count,
            legacy_meta.buffer_offset,
            legacy_meta.entry,
            legacy_meta.max_instructions,
            legacy_meta.expected_bytes,
        )

    def test_execution_captures_buffers(self):
        self.assertTrue(self.output)

    def test_output_byte_count(self):
        self.assertEqual(len(self.output), EXPECTED_BYTES)

    def test_output_line_count(self):
        self.assertEqual(self.output.count(10), EXPECTED_LINES)

    def test_output_ends_with_lf(self):
        self.assertEqual(self.output[-1:], b"\n")

    def test_output_has_no_crlf(self):
        self.assertNotIn(b"\r\n", self.output)

    def test_sha256_matches(self):
        actual = hashlib.sha256(self.output).hexdigest()
        self.assertEqual(actual, EXPECTED_SHA256)

    def test_output_matches_golden(self):
        self.assertEqual(self.output, self.golden)

    def test_output_matches_legacy(self):
        self.assertEqual(self.output, self.legacy)

    def test_two_runs_are_deterministic(self):
        output2 = _capture_fixture_output(
            self.source,
            self.meta.buffer_count,
            self.meta.buffer_offset,
            self.meta.entry,
            self.meta.max_instructions,
            self.meta.expected_bytes,
        )
        self.assertEqual(output2, self.output)

    def test_output_contains_expected_program_text(self):
        self.assertEqual(self.output[:6], b".s3asm")
        self.assertIn(b".function add", self.output)
        self.assertIn(b".function main", self.output)
        self.assertIn(b"TCALL", self.output)
        self.assertIn(b"; source=", self.output)
        self.assertEqual(self.output.count(b".function "), 2)


if __name__ == "__main__":
    unittest.main()
