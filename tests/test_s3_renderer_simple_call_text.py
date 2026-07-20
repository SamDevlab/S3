import hashlib
import os
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

EXPECTED_SHA256 = FIXTURE_METADATA["simple_call"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["simple_call"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["simple_call"].expected_lines


def run_and_capture(source: str):
    meta = FIXTURE_METADATA["simple_call"]
    out = _capture_fixture_output(source, meta.buffer_count, meta.buffer_offset, meta.entry)
    return 0, out


class TestSimpleCallTextRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        meta = FIXTURE_METADATA["simple_call"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        cls.assertTrue(os.path.isfile(s3_path), f"S3 program missing: {s3_path}")
        with open(s3_path) as f:
            cls.source = f.read()

        cls.result, cls.output = run_and_capture(cls.source)

        cls.golden = _git_blob_bytes(meta.golden_path)

    def test_program_exists(self):
        meta = FIXTURE_METADATA["simple_call"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        self.assertTrue(os.path.isfile(s3_path))

    def test_program_compiles(self):
        from bootstrap.s3.pipeline import compile_source

        compile_source(self.source)

    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    def test_buffers_captured(self):
        meta = FIXTURE_METADATA["simple_call"]
        out = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
        self.assertTrue(len(out) > 0)

    def test_output_byte_count(self):
        self.assertEqual(len(self.output), EXPECTED_BYTES)

    def test_output_line_count(self):
        lines = self.output.count(10)
        self.assertEqual(lines, EXPECTED_LINES)

    def test_output_ends_with_lf(self):
        self.assertEqual(self.output[-1], 10)

    def test_output_no_crlf(self):
        self.assertNotIn(b"\r\n", bytes(self.output))

    def test_output_matches_golden(self):
        self.assertEqual(len(self.output), len(self.golden))
        self.assertEqual(self.output, self.golden)

    def test_sha256(self):
        actual_sha256 = hashlib.sha256(self.output).hexdigest()
        self.assertEqual(actual_sha256, EXPECTED_SHA256)

    def test_deterministic_two_runs(self):
        meta = FIXTURE_METADATA["simple_call"]
        out1 = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
        out2 = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
        self.assertEqual(out1, out2)

    def test_first_still_passes(self):
        meta = FIXTURE_METADATA["first"]
        first_path = os.path.join(*meta.s3_path.split("/"))
        with open(first_path) as f:
            first_source = f.read()
        _capture_fixture_output(first_source, meta.buffer_count, meta.buffer_offset, meta.entry)

    def test_compare_check_returns_zero(self):
        import subprocess
        import sys

        completed = subprocess.run(
            [sys.executable, "tools/compare_assembly_renderer.py", "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)

    def test_text_table_present(self):
        from bootstrap.s3.pipeline import compile_source

        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("text_byte_at", fn_names)
        self.assertIn("text_length", fn_names)

    def test_decimal_formatter(self):
        from bootstrap.s3.pipeline import compile_source

        ir = compile_source(self.source).ir
        fn_names = {fn.name for fn in ir.functions}
        self.assertIn("decimal_tens_byte", fn_names)
        self.assertIn("decimal_ones_byte", fn_names)

    def test_dual_buffer_transition(self):
        meta = FIXTURE_METADATA["simple_call"]
        out = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
        self.assertEqual(len(out), EXPECTED_BYTES)

    def test_unified_table(self):
        with open(
            os.path.join(*FIXTURE_METADATA["simple_call"].s3_path.split("/"))
        ) as f:
            text = f.read()
        self.assertIn("text_byte_at", text)
        self.assertNotIn("fragment_byte", text)
        self.assertNotIn("symbol_byte", text)
        self.assertNotIn("opcode_byte", text)


if __name__ == "__main__":
    unittest.main()
