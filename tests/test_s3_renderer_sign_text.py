import hashlib
import os
import subprocess
import sys
import unittest
from bootstrap.s3.pipeline import run_source_with_buffer_capture

S3_PATH = os.path.join('examples', 'self_hosting', 'assembly_renderer_sign_text.s3')
GOLDEN_PATH = 'tests/golden/inspect/sign.assembly.txt'
EXPECTED_SHA256 = 'c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9'
EXPECTED_BYTES = 946
EXPECTED_LINES = 36


def run_and_capture(source: str):
    result, capture = run_source_with_buffer_capture(source)
    memory = capture[-1]
    low = memory.get(0, [])
    mid = memory.get(1, [])
    high = memory.get(2, [])

    out = bytearray()
    for v in low:
        if v is not None and v != 0:
            out.append(v)
    for v in mid:
        if v is not None and v != 0:
            out.append(v)
    for v in high:
        if v is not None and v != 0:
            out.append(v)
    return result, out


class TestSignTextRenderer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.assertTrue(os.path.isfile(S3_PATH), f'S3 program missing: {S3_PATH}')
        with open(S3_PATH) as f:
            cls.source = f.read()

        cls.result, cls.output = run_and_capture(cls.source)

        result = subprocess.run(
            ["git", "show", f"HEAD:{GOLDEN_PATH}"],
            capture_output=True, check=True,
        )
        cls.golden = result.stdout

    def test_program_exists(self):
        self.assertTrue(os.path.isfile(S3_PATH))

    def test_program_compiles(self):
        from bootstrap.s3.pipeline import compile_source
        compile_source(self.source)

    def test_execution_returns_zero(self):
        self.assertEqual(self.result, 0)

    def test_buffers_captured(self):
        _, capture = run_source_with_buffer_capture(self.source)
        self.assertTrue(len(capture) > 0)
        memory = capture[-1]
        self.assertIn(0, memory)
        self.assertIn(1, memory)
        self.assertIn(2, memory)

    def test_output_byte_count(self):
        self.assertEqual(len(self.output), EXPECTED_BYTES)

    def test_output_line_count(self):
        self.assertEqual(self.output.count(10), EXPECTED_LINES)

    def test_output_ends_with_lf(self):
        self.assertEqual(self.output[-1:], b'\n')

    def test_output_has_no_crlf(self):
        self.assertNotIn(b'\r\n', self.output)

    def test_output_matches_golden(self):
        self.assertEqual(len(self.output), len(self.golden))
        self.assertEqual(self.output, self.golden)

    def test_sha256_matches(self):
        actual = hashlib.sha256(self.output).hexdigest()
        self.assertEqual(actual, EXPECTED_SHA256)

    def test_two_runs_are_deterministic(self):
        result2, output2 = run_and_capture(self.source)
        self.assertEqual(result2, 0)
        self.assertEqual(output2, self.output)

    def test_first_still_passes(self):
        import importlib
        mod = importlib.import_module('test_s3_renderer_first_text')
        self.assertEqual(mod.EXPECTED_SHA256,
                         '46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67')

    def test_simple_call_still_passes(self):
        import importlib
        mod = importlib.import_module('test_s3_renderer_simple_call_text')
        self.assertEqual(mod.EXPECTED_SHA256,
                         'd6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f')

    def test_candidate_render_sign_returns_zero(self):
        completed = subprocess.run(
            [sys.executable, 'tools/compare_assembly_renderer.py', '--candidate-render-sign'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)

    def test_compare_check_returns_zero(self):
        completed = subprocess.run(
            [sys.executable, 'tools/compare_assembly_renderer.py', '--check'],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(completed.returncode, 0)

    def test_fragment_table_present(self):
        self.assertIn('fn fragment_byte', self.source)
        self.assertIn('fn fragment_length', self.source)

    def test_symbol_table_present(self):
        self.assertIn('fn symbol_byte', self.source)
        self.assertIn('fn symbol_length', self.source)

    def test_opcode_table_present(self):
        self.assertIn('fn opcode_byte', self.source)
        self.assertIn('fn opcode_length', self.source)

    def test_decimal_formatter_present(self):
        self.assertIn('fn decimal_tens_byte', self.source)
        self.assertIn('fn decimal_ones_byte', self.source)

    def test_dual_buffer_transition(self):
        self.assertIn('buffer_low', self.source)
        self.assertIn('buffer_mid', self.source)
        self.assertIn('buffer_high', self.source)

    def test_no_arbitrary_replay(self):
        replay_indicator = 'return ' + str(ord('.'))
        count = self.source.count(replay_indicator)
        self.assertLess(count, 50)


if __name__ == '__main__':
    unittest.main()
