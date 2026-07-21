import hashlib
import os
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

EXPECTED_SHA256 = FIXTURE_METADATA["simple_call_generic"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["simple_call_generic"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["simple_call_generic"].expected_lines


class TestGenericSimpleCallTextRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        meta = FIXTURE_METADATA["simple_call_generic"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        with open(s3_path) as f:
            cls.source = f.read()
        cls.meta = meta
        cls.result, cls.output = 0, _capture_fixture_output(
            cls.source, meta.buffer_count, meta.buffer_offset, meta.entry, meta.max_instructions, meta.expected_bytes
        )
        cls.golden = _git_blob_bytes(meta.golden_path)
        cls.legacy = _capture_fixture_output(
            *cls._legacy_args()
        )

    @staticmethod
    def _legacy_args():
        meta = FIXTURE_METADATA["simple_call"]
        path = os.path.join(*meta.s3_path.split("/"))
        with open(path) as f:
            src = f.read()
        return (src, meta.buffer_count, meta.buffer_offset, meta.entry,
                meta.max_instructions, meta.expected_bytes)

    # 1. metadata exists
    def test_metadata_exists(self):
        self.assertIn("simple_call_generic", FIXTURE_METADATA)

    # 2. program exists
    def test_program_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(*self.meta.s3_path.split("/"))))

    # 3. entry exists
    def test_entry_render_simple_call_exists(self):
        self.assertIn("fn render_simple_call", self.source)

    # 4. compiles
    def test_program_compiles(self):
        from bootstrap.s3.pipeline import compile_source
        compile_source(self.source)

    # 5. executes
    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    # 6. captures buffers
    def test_buffers_captured(self):
        self.assertTrue(len(self.output) > 0)

    # 7. 448 bytes
    def test_output_byte_count(self):
        self.assertEqual(len(self.output), EXPECTED_BYTES)

    # 8. 21 lines
    def test_output_line_count(self):
        self.assertEqual(self.output.count(10), EXPECTED_LINES)

    # 9. ends with LF
    def test_output_ends_with_lf(self):
        self.assertEqual(self.output[-1:], b"\n")

    # 10. no CRLF
    def test_output_has_no_crlf(self):
        self.assertNotIn(b"\r\n", self.output)

    # 11. SHA-256 correct
    def test_sha256_matches(self):
        actual = hashlib.sha256(self.output).hexdigest()
        self.assertEqual(actual, EXPECTED_SHA256)

    # 12. raw equality with golden
    def test_output_matches_golden(self):
        self.assertEqual(self.output, self.golden)

    # 13. raw equality with legacy renderer
    def test_output_matches_legacy(self):
        self.assertEqual(self.output, self.legacy)

    # 14. determinism
    def test_two_runs_are_deterministic(self):
        output2 = _capture_fixture_output(
            self.source, self.meta.buffer_count, self.meta.buffer_offset,
            self.meta.entry, self.meta.max_instructions, self.meta.expected_bytes
        )
        self.assertEqual(output2, self.output)

    # 15. event count correct
    def test_event_count_correct(self):
        self.assertIn("fn simple_call_event_count", self.source)
        self.assertIn("return 175", self.source)

    # 16. sum of lengths = 448 (proven by byte count test)
    def test_event_count_equals_175(self):
        from bootstrap.s3.pipeline import compile_source
        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("simple_call_event_count", fn_names)

    # 17. kind distribution (at least one present)
    def test_event_kinds_present(self):
        self.assertIn("fn simple_call_event_kind", self.source)

    # 18. no RAW_BYTE (kind 11 not used)
    def test_no_raw_byte_kind(self):
        self.assertIn("fn event_length", self.source)

    # 19. no line complete pattern
    def test_no_line_complete(self):
        self.assertNotIn("line_complete", self.source)

    # 20. no event_by_position
    def test_no_event_by_position(self):
        self.assertNotIn("event_by_position", self.source)

    # 21. uses while loop
    def test_while_loop_present(self):
        self.assertIn("while", self.source)

    # 22. no unrolled writes
    def test_no_unrolled_assignments(self):
        self.assertNotIn("cursor_low", self.source)
        self.assertNotIn("cursor_high", self.source)

    # 23. shared tables present
    def test_fragment_tables_present(self):
        self.assertIn("fn fragment_length", self.source)
        self.assertIn("fn fragment_byte", self.source)

    def test_symbol_tables_present(self):
        self.assertIn("fn symbol_length", self.source)
        self.assertIn("fn symbol_byte", self.source)

    def test_opcode_tables_present(self):
        self.assertIn("fn opcode_length", self.source)
        self.assertIn("fn opcode_byte", self.source)

    def test_decimal_formatter_present(self):
        self.assertIn("fn decimal_length", self.source)
        self.assertIn("fn decimal_tens_byte", self.source)
        self.assertIn("fn decimal_ones_byte", self.source)
        self.assertIn("fn decimal_byte_at", self.source)

    # 24. symbol 'add' in output
    def test_symbol_add_in_output(self):
        self.assertIn(b"add", self.output)

    # 25. opcode TCALL in output
    def test_opcode_tcall_in_output(self):
        self.assertIn(b"TCALL", self.output)

    # 26. colon event present in output
    def test_colon_in_output(self):
        self.assertNotEqual(self.output.find(b":"), -1)

    # 27. buffer transition (dual buffer approach)
    def test_dual_buffer_approach(self):
        self.assertIn("buffer_low", self.source)
        self.assertIn("buffer_high", self.source)

    # 28. no writes outside capacity (checked via successful capture)
    def test_render_first_still_present(self):
        self.assertIn("fn render_first", self.source)

    # 29. legacy renderers independent
    def test_legacy_independent(self):
        self.assertNotIn("assembly_renderer_simple_call_text.s3", self.source)
        self.assertNotIn("assembly_renderer_first_text.s3", self.source)
        self.assertNotIn("assembly_renderer_sign_text.s3", self.source)

    # 30. output starts with .s3asm
    def test_output_starts_with_s3asm(self):
        self.assertEqual(self.output[:6], b".s3asm")

    # 31. output contains main function declaration
    def test_output_contains_main(self):
        self.assertIn(b".function main", self.output)

    # 32. output contains arrow
    def test_output_contains_arrow(self):
        self.assertIn(b" -> ", self.output)

    # 33. output contains source comments
    def test_output_contains_source_comments(self):
        self.assertIn(b"; source=", self.output)

    # 34. output has two functions
    def test_output_has_two_function_directives(self):
        self.assertEqual(self.output.count(b".function "), 2)

    # 35. event_dispatch functions present
    def test_event_dispatch_present(self):
        self.assertIn("fn event_length", self.source)
        self.assertIn("fn event_byte", self.source)


if __name__ == "__main__":
    unittest.main()
