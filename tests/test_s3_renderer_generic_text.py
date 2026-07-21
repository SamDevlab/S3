import hashlib
import os
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

EXPECTED_SHA256 = FIXTURE_METADATA["first_generic"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["first_generic"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["first_generic"].expected_lines


class TestGenericFirstTextRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        meta = FIXTURE_METADATA["first_generic"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        with open(s3_path) as f:
            cls.source = f.read()
        cls.meta = meta
        cls.result, cls.output = 0, _capture_fixture_output(
            cls.source, meta.buffer_count, meta.buffer_offset, meta.entry, meta.max_instructions, meta.expected_bytes
        )
        cls.golden = _git_blob_bytes(meta.golden_path)

    def test_program_exists(self):
        self.assertTrue(os.path.isfile(os.path.join(*self.meta.s3_path.split("/"))))

    def test_program_compiles(self):
        from bootstrap.s3.pipeline import compile_source
        compile_source(self.source)

    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    def test_buffers_captured(self):
        out = _capture_fixture_output(
            self.source, self.meta.buffer_count, self.meta.buffer_offset, self.meta.entry, self.meta.max_instructions, self.meta.expected_bytes
        )
        self.assertTrue(len(out) > 0)

    def test_output_byte_count(self):
        self.assertEqual(len(self.output), EXPECTED_BYTES)

    def test_output_line_count(self):
        self.assertEqual(self.output.count(10), EXPECTED_LINES)

    def test_output_ends_with_lf(self):
        self.assertEqual(self.output[-1:], b"\n")

    def test_output_has_no_crlf(self):
        self.assertNotIn(b"\r\n", self.output)

    def test_output_matches_golden(self):
        self.assertEqual(len(self.output), len(self.golden))
        self.assertEqual(self.output, self.golden)

    def test_sha256_matches(self):
        actual = hashlib.sha256(self.output).hexdigest()
        self.assertEqual(actual, EXPECTED_SHA256)

    def test_two_runs_are_deterministic(self):
        output2 = _capture_fixture_output(
            self.source, self.meta.buffer_count, self.meta.buffer_offset, self.meta.entry, self.meta.max_instructions, self.meta.expected_bytes
        )
        self.assertEqual(output2, self.output)

    def test_event_driven_approach(self):
        self.assertIn("fn first_event_kind", self.source)
        self.assertIn("fn first_event_arg0", self.source)
        self.assertIn("fn first_event_count", self.source)

    def test_event_dispatch_functions_present(self):
        self.assertIn("fn event_length", self.source)
        self.assertIn("fn event_byte", self.source)

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
        self.assertIn("fn decimal_byte_at", self.source)

    def test_while_loop_present(self):
        self.assertIn("while", self.source)

    def test_dual_buffer_approach(self):
        self.assertIn("buffer_low", self.source)
        self.assertIn("buffer_high", self.source)

    def test_event_count_reasonable(self):
        from bootstrap.s3.pipeline import compile_source
        ir = compile_source(self.source).ir
        for fn in ir.functions:
            if fn.name == "first_event_count":
                break
        else:
            self.fail("first_event_count not found")

    def test_render_first_function_present(self):
        from bootstrap.s3.pipeline import compile_source
        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("render_first", fn_names)

    def test_main_calls_render_first(self):
        self.assertIn("return render_first", self.source)

    def test_no_raw_text_tables(self):
        self.assertNotIn("fn text_byte_at", self.source)

    def test_no_unrolled_assignment_pattern(self):
        self.assertNotIn("cursor_low", self.source)
        self.assertNotIn("cursor_high", self.source)

    def test_first_event_kind_returns_valid_kinds(self):
        from bootstrap.s3.pipeline import compile_source
        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("first_event_kind", fn_names)

    def test_first_event_arg0_returns_valid_args(self):
        from bootstrap.s3.pipeline import compile_source
        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("first_event_arg0", fn_names)

    def test_direct_event_iteration(self):
        self.assertIn("evt_idx", self.source)
        self.assertIn("buffer_idx", self.source)
        self.assertIn("buf_offset", self.source)

    def test_output_starts_with_s3asm_header(self):
        self.assertEqual(self.output[:6], b".s3asm")

    def test_output_contains_main_function(self):
        self.assertIn(b".function main", self.output)

    def test_output_contains_tconst(self):
        self.assertIn(b"TCONST r0", self.output)

    def test_output_contains_tmov(self):
        self.assertIn(b"TMOV   r1", self.output)

    def test_output_contains_tinv(self):
        self.assertIn(b"TINV   r4", self.output)

    def test_output_contains_tadd(self):
        self.assertIn(b"TADD   r5", self.output)

    def test_output_contains_tret(self):
        self.assertIn(b"TRET   r5", self.output)

    def test_output_contains_end_directive(self):
        self.assertIn(b".end", self.output)

    def test_output_contains_source_comments(self):
        self.assertIn(b"; source=", self.output)
        self.assertIn(b"2:16:35", self.output)


if __name__ == "__main__":
    unittest.main()
