import ast
import hashlib
import inspect
import os
import re
import unittest
from collections import Counter

from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
    flatten_capture,
)


EXPECTED_SHA256 = FIXTURE_METADATA["sign_generic"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["sign_generic"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["sign_generic"].expected_lines
EXPECTED_EVENT_COUNT = 342
EXPECTED_DISTRIBUTION = Counter(
    {
        1: 49,
        2: 40,
        3: 14,
        4: 51,
        5: 28,
        6: 98,
        7: 24,
        9: 2,
        10: 36,
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


def _array_values(source: str, function_name: str, name: str) -> list[int]:
    body = _function_body(source, function_name)
    match = re.search(
        rf"mut {name}: tryte\[(\d+)\] = (\[.*?\])",
        body,
        re.DOTALL,
    )
    if not match:
        raise AssertionError(f"{name} array not found in {function_name}")
    values = ast.literal_eval(match.group(2))
    declared = int(match.group(1))
    if len(values) != declared:
        raise AssertionError(
            f"{function_name}.{name} declared {declared}, has {len(values)}"
        )
    return values


def _event_count(source: str, prefix: str) -> int:
    match = re.search(
        rf"^fn {prefix}_event_count\(\)\s*->\s*tryte:\n\s*return\s+(\d+)",
        source,
        re.MULTILINE,
    )
    if not match:
        raise AssertionError(f"{prefix}_event_count not found")
    return int(match.group(1))


def _event_plan(source: str) -> list[tuple[int, int]]:
    count = _event_count(source, "sign")
    kinds = _array_values(source, "sign_event_kind", "kinds")
    args = _array_values(source, "sign_event_arg0", "args")
    if len(kinds) != count or len(args) != count:
        raise AssertionError("sign event table length mismatch")
    return list(zip(kinds, args))


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
        returns = [
            int(value)
            for value in re.findall(r"\n\s*0:\n\s*return (\d+)", match.group(2))
        ]
        result[id_value] = "".join(
            chr(value) for value in returns[: lengths[id_value]]
        )
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
    text = "".join(
        _event_text(kind, arg0, fragments, symbols, opcodes)
        for kind, arg0 in events
    )
    return text.encode("utf-8")


class TestGenericSignStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = FIXTURE_METADATA["sign_generic"]
        cls.source = _read_source("sign_generic")
        from bootstrap.s3.pipeline import compile_source

        cls.ir = compile_source(cls.source).ir
        cls.fn_names = {fn.name for fn in cls.ir.functions}
        cls.events = _event_plan(cls.source)
        cls.fragments = _text_table(cls.source, "fragment")
        cls.symbols = _text_table(cls.source, "symbol")
        cls.opcodes = _text_table(cls.source, "opcode")
        cls.rendered = _reconstruct_bytes(cls.source, cls.events)
        cls.golden = _git_blob_bytes(cls.meta.golden_path)

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
        self.assertIn("sign_generic", FIXTURE_METADATA)
        self.assertTrue(os.path.isfile(os.path.join(*self.meta.s3_path.split("/"))))

    def test_program_compiles(self):
        self.assertIsNotNone(self.ir)

    def test_entry_and_dispatch_functions_present(self):
        for name in (
            "render_sign",
            "sign_event_kind",
            "sign_event_arg0",
            "sign_event_count",
            "event_length",
            "event_byte",
        ):
            self.assertIn(name, self.fn_names)

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

    def test_existing_ids_are_preserved(self):
        self.assertEqual(self.fragments[2], ".function")
        self.assertEqual(self.fragments[8], "; source=")
        self.assertEqual(self.fragments[11], "tryte")
        self.assertEqual(self.symbols[1], "main")
        self.assertEqual(self.symbols[2], "entry")
        self.assertEqual(self.symbols[3], "r0")
        self.assertEqual(self.opcodes[100], "TCONST")
        self.assertEqual(self.opcodes[105], "TCALL")

    def test_new_tables_are_structural(self):
        self.assertEqual(self.fragments[21], "trit")
        self.assertEqual(self.symbols[10], "sign")
        self.assertEqual(self.symbols[11], "r6")
        self.assertEqual(self.symbols[12], "switch_negative_0")
        self.assertEqual(self.symbols[13], "switch_neutral_1")
        self.assertEqual(self.symbols[14], "switch_positive_2")
        self.assertEqual(self.opcodes[106], "TCMP")
        self.assertEqual(self.opcodes[107], "TBR3")

    def test_event_indices_are_continuous(self):
        count = _event_count(self.source, "sign")
        self.assertEqual(count, EXPECTED_EVENT_COUNT)
        self.assertEqual(len(self.events), count)
        self.assertEqual(list(range(count)), list(range(len(self.events))))

    def test_event_count_and_distribution(self):
        self.assertEqual(len(self.events), EXPECTED_EVENT_COUNT)
        self.assertEqual(Counter(kind for kind, _ in self.events), EXPECTED_DISTRIBUTION)

    def test_kinds_and_arguments_are_valid(self):
        valid_kinds = {1, 2, 3, 4, 5, 6, 7, 9, 10}
        for index, (kind, arg0) in enumerate(self.events):
            with self.subTest(index=index, kind=kind, arg0=arg0):
                self.assertIn(kind, valid_kinds)
                if kind == 1:
                    self.assertIn(arg0, self.fragments)
                elif kind == 2:
                    self.assertIn(arg0, self.symbols)
                elif kind == 3:
                    self.assertIn(arg0, self.opcodes)
                elif kind == 4:
                    self.assertGreaterEqual(arg0, 0)
                    self.assertLessEqual(arg0, 191)
                elif kind == 6:
                    self.assertGreaterEqual(arg0, 0)

    def test_sum_newline_and_last_event(self):
        self.assertEqual(len(self.rendered), EXPECTED_BYTES)
        self.assertEqual(self.rendered.count(10), EXPECTED_LINES)
        self.assertEqual(self.events[-1][0], 10)

    def test_no_raw_position_or_line_complete_helpers(self):
        self.assertNotIn(11, [kind for kind, _ in self.events])
        self.assertNotIn("line_complete", self.fn_names)
        self.assertNotIn("event_by_position", self.fn_names)
        self.assertNotIn("raw_byte", self.source.lower())

    def test_used_fragments_are_structural(self):
        used_fragment_ids = {arg0 for kind, arg0 in self.events if kind == 1}
        self.assertFalse({12, 13, 14, 15, 16, 17} & used_fragment_ids)
        self.assertNotIn(1, used_fragment_ids)
        self.assertNotIn(7, used_fragment_ids)
        for fragment_id in used_fragment_ids:
            text = self.fragments[fragment_id]
            with self.subTest(fragment_id=fragment_id, text=text):
                self.assertNotRegex(text, r"\d")
                self.assertNotIn(":", text)
                self.assertNotIn("\n", text)
                self.assertNotIn(",", text)
                self.assertNotIn("->", text)
                self.assertFalse(text.startswith(("TCONST", "TCMP", "TBR3", "TINV", "TRET", "TCALL")))

    def test_source_annotations_use_decimal_and_colon_events(self):
        prefix_positions = [
            index for index, event in enumerate(self.events) if event == (1, 8)
        ]
        self.assertEqual(len(prefix_positions), 14)
        for position in prefix_positions:
            window = self.events[position + 1 : position + 6]
            self.assertEqual([kind for kind, _ in window], [4, 5, 4, 5, 4])
        self.assertEqual(Counter(kind for kind, _ in self.events)[4], 51)
        self.assertEqual(Counter(kind for kind, _ in self.events)[5], 28)

    def test_render_sign_uses_four_buffers_and_loops(self):
        body = _function_body(self.source, "render_sign")
        self.assertIn("while evt_idx <=> sign_event_count()", body)
        self.assertIn("while byte_idx <=> length", body)
        self.assertIn("event_length(kind, arg0)", body)
        self.assertIn("event_byte(kind, arg0, byte_idx)", body)
        self.assertEqual(self.meta.buffer_count, 4)
        self.assertEqual(self.meta.buffer_layout.capacities, (300, 300, 300, 46))
        for name in self.meta.buffer_layout.buffer_names:
            self.assertIn(name, body)

    def test_no_unrolled_output_writes(self):
        body = _function_body(self.source, "render_sign")
        self.assertNotIn("# Line ", body)
        self.assertLessEqual(len(re.findall(r"buffer_\w+\[buf_offset\] =", body)), 4)

    def test_reconstructed_output_matches_canonical_golden(self):
        self.assertEqual(self.rendered, self.golden)
        self.assertEqual(hashlib.sha256(self.rendered).hexdigest(), EXPECTED_SHA256)


class TestGenericSignExecution(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta = FIXTURE_METADATA["sign_generic"]
        cls.source = _read_source("sign_generic")
        from bootstrap.s3.pipeline import run_source_with_buffer_capture

        cls.result, capture = run_source_with_buffer_capture(
            cls.source,
            entry=cls.meta.entry,
            max_instructions=cls.meta.max_instructions,
        )
        cls.memory = capture[-1]
        cls.output = flatten_capture(
            cls.memory,
            cls.meta.buffer_count,
            cls.meta.buffer_offset,
            cls.meta.expected_bytes,
        )
        cls.second_output = _capture_fixture_output(
            cls.source,
            cls.meta.buffer_count,
            cls.meta.buffer_offset,
            cls.meta.entry,
            cls.meta.max_instructions,
            cls.meta.expected_bytes,
        )
        legacy_meta = FIXTURE_METADATA["sign"]
        legacy_source = _read_source("sign")
        cls.legacy = _capture_fixture_output(
            legacy_source,
            legacy_meta.buffer_count,
            legacy_meta.buffer_offset,
            legacy_meta.entry,
            legacy_meta.max_instructions,
            legacy_meta.expected_bytes,
        )
        cls.golden = _git_blob_bytes(cls.meta.golden_path)

    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    def test_four_buffers_captured(self):
        for index in range(4):
            self.assertIn(index, self.memory)
        self.assertEqual(len(self.memory[0]), 300)
        self.assertEqual(len(self.memory[1]), 300)
        self.assertEqual(len(self.memory[2]), 300)
        self.assertEqual(len(self.memory[3]), 46)

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
        self.assertEqual(self.second_output, self.output)

    def test_buffer_transitions(self):
        self.assertEqual(self.memory[0][299], self.output[299])
        self.assertEqual(self.memory[1][0], self.output[300])
        self.assertEqual(self.memory[1][299], self.output[599])
        self.assertEqual(self.memory[2][0], self.output[600])
        self.assertEqual(self.memory[2][299], self.output[899])
        self.assertEqual(self.memory[3][0], self.output[900])
        self.assertEqual(self.memory[3][45], self.output[945])

    def test_no_write_beyond_expected_tail(self):
        self.assertEqual(len(self.memory[3]), 46)
        self.assertEqual(bytes(self.memory[3]), self.output[900:946])


if __name__ == "__main__":
    unittest.main()
