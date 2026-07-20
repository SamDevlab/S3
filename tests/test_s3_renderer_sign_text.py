import hashlib
import os
import subprocess
import sys
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

EXPECTED_SHA256 = FIXTURE_METADATA["sign"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["sign"].expected_bytes
EXPECTED_LINES = FIXTURE_METADATA["sign"].expected_lines


def run_and_capture(source: str):
    meta = FIXTURE_METADATA["sign"]
    out = _capture_fixture_output(source, meta.buffer_count, meta.buffer_offset, meta.entry)
    return 0, out


class TestSignTextRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        meta = FIXTURE_METADATA["sign"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        cls.assertTrue(os.path.isfile(s3_path), f"S3 program missing: {s3_path}")
        with open(s3_path) as f:
            cls.source = f.read()

        cls.result, cls.output = run_and_capture(cls.source)

        cls.golden = _git_blob_bytes(meta.golden_path)

    def test_program_exists(self):
        meta = FIXTURE_METADATA["sign"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        self.assertTrue(os.path.isfile(s3_path))

    def test_program_compiles(self):
        from bootstrap.s3.pipeline import compile_source

        compile_source(self.source)

    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    def test_buffers_captured(self):
        meta = FIXTURE_METADATA["sign"]
        out = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
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
        meta = FIXTURE_METADATA["sign"]
        output2 = _capture_fixture_output(self.source, meta.buffer_count, meta.buffer_offset, meta.entry)
        self.assertEqual(output2, self.output)

    def test_candidate_render_sign_returns_zero(self):
        completed = subprocess.run(
            [sys.executable, "tools/compare_assembly_renderer.py", "--candidate-render-sign"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)

    def test_compare_check_returns_zero(self):
        completed = subprocess.run(
            [sys.executable, "tools/compare_assembly_renderer.py", "--check"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)

    def test_unified_text_table_present(self):
        self.assertIn("fn text_byte_at", self.source)

    def test_decimal_formatter_present(self):
        self.assertIn("fn decimal_tens_byte", self.source)
        self.assertIn("fn decimal_ones_byte", self.source)

    def test_triple_buffer_transition(self):
        self.assertIn("buffer_low", self.source)
        self.assertIn("buffer_mid", self.source)
        self.assertIn("buffer_high", self.source)


if __name__ == "__main__":
    unittest.main()
