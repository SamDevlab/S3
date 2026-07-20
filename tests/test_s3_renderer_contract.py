import hashlib
import os
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_FRAGMENTS,
    FIXTURE_SYMBOLS,
    FIXTURE_OPCODES,
    FIXTURE_METADATA,
    COMMON_FRAGMENT_NAMES,
    _capture_fixture_output,
    _git_blob_bytes,
    RendererBufferLayout,
    verify_fixture_metadata,
    audit_duplication,
)


class TestRendererContract(unittest.TestCase):
    def test_three_fixtures_defined(self):
        self.assertIn("first", FIXTURE_METADATA)
        self.assertIn("simple_call", FIXTURE_METADATA)
        self.assertIn("sign", FIXTURE_METADATA)

    def test_fixture_metadata_has_all_fields(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                self.assertTrue(meta.s3_path.endswith(".s3"))
                self.assertTrue(meta.golden_path.startswith("tests/golden/"))
                self.assertEqual(len(meta.expected_sha256), 64)
                self.assertGreater(meta.expected_bytes, 0)
                self.assertGreater(meta.expected_lines, 0)
                self.assertIn(meta.buffer_count, (2, 3))

    def test_golden_sha256_matches_git_blob(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                golden = _git_blob_bytes(meta.golden_path)
                sha256 = hashlib.sha256(golden).hexdigest()
                self.assertEqual(sha256, meta.expected_sha256)

    def test_golden_byte_count_matches_git_blob(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                golden = _git_blob_bytes(meta.golden_path)
                self.assertEqual(len(golden), meta.expected_bytes)

    def test_golden_line_count_matches_git_blob(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                golden = _git_blob_bytes(meta.golden_path)
                lines = golden.count(10)
                self.assertEqual(lines, meta.expected_lines)

    def test_golden_ends_with_lf(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                golden = _git_blob_bytes(meta.golden_path)
                self.assertTrue(golden.endswith(b"\n"))

    def test_golden_no_crlf(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                golden = _git_blob_bytes(meta.golden_path)
                self.assertNotIn(b"\r\n", golden)

    def test_capture_first_matches_golden(self):
        meta = FIXTURE_METADATA["first"]
        path = os.path.join(*meta.s3_path.split("/"))
        with open(path) as f:
            source = f.read()
        output = _capture_fixture_output(source, meta.buffer_count)
        golden = _git_blob_bytes(meta.golden_path)
        self.assertEqual(output, golden)

    def test_capture_simple_call_matches_golden(self):
        meta = FIXTURE_METADATA["simple_call"]
        path = os.path.join(*meta.s3_path.split("/"))
        with open(path) as f:
            source = f.read()
        output = _capture_fixture_output(source, meta.buffer_count)
        golden = _git_blob_bytes(meta.golden_path)
        self.assertEqual(output, golden)

    def test_capture_sign_matches_golden(self):
        meta = FIXTURE_METADATA["sign"]
        path = os.path.join(*meta.s3_path.split("/"))
        with open(path) as f:
            source = f.read()
        output = _capture_fixture_output(source, meta.buffer_count)
        golden = _git_blob_bytes(meta.golden_path)
        self.assertEqual(output, golden)

    def test_capture_no_newline_normalization(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                path = os.path.join(*meta.s3_path.split("/"))
                with open(path) as f:
                    source = f.read()
                output = _capture_fixture_output(source, meta.buffer_count)
                golden = _git_blob_bytes(meta.golden_path)
                self.assertEqual(
                    output,
                    golden,
                    f"capture for {name} must use raw bytes, no normalization",
                )

    def test_capture_is_deterministic(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                path = os.path.join(*meta.s3_path.split("/"))
                with open(path) as f:
                    source = f.read()
                out1 = _capture_fixture_output(source, meta.buffer_count)
                out2 = _capture_fixture_output(source, meta.buffer_count)
                self.assertEqual(out1, out2)

    def test_verify_fixture_metadata_passes(self):
        for name in FIXTURE_METADATA:
            with self.subTest(fixture=name):
                ok, msg = verify_fixture_metadata(name)
                self.assertTrue(ok, msg)

    def test_fragment_ids_are_unique_within_fixture(self):
        for name, fragments in FIXTURE_FRAGMENTS.items():
            with self.subTest(fixture=name):
                ids = list(fragments.keys())
                self.assertEqual(len(ids), len(set(ids)))

    def test_symbol_ids_are_unique_within_fixture(self):
        for name, symbols in FIXTURE_SYMBOLS.items():
            with self.subTest(fixture=name):
                ids = list(symbols.keys())
                self.assertEqual(len(ids), len(set(ids)))

    def test_opcode_ids_are_unique_within_fixture(self):
        for name, opcodes in FIXTURE_OPCODES.items():
            with self.subTest(fixture=name):
                ids = list(opcodes.keys())
                self.assertEqual(len(ids), len(set(ids)))

    def test_buffer_layout_valid(self):
        for name, meta in FIXTURE_METADATA.items():
            with self.subTest(fixture=name):
                layout = meta.buffer_layout
                self.assertIsInstance(layout, RendererBufferLayout)
                self.assertEqual(len(layout.buffer_names), meta.buffer_count)
                self.assertEqual(len(layout.capacities), meta.buffer_count)
                for cap in layout.capacities:
                    self.assertGreater(cap, 0)

    def test_first_buffer_layout(self):
        layout = FIXTURE_METADATA["first"].buffer_layout
        self.assertEqual(layout.buffer_names, ("buffer_low", "buffer_high"))
        self.assertEqual(layout.capacities, (300, 300))

    def test_simple_call_buffer_layout(self):
        layout = FIXTURE_METADATA["simple_call"].buffer_layout
        self.assertEqual(layout.buffer_names, ("buffer_low", "buffer_high"))
        self.assertEqual(layout.capacities, (300, 300))

    def test_sign_buffer_layout(self):
        layout = FIXTURE_METADATA["sign"].buffer_layout
        self.assertEqual(
            layout.buffer_names, ("buffer_low", "buffer_mid", "buffer_high")
        )
        self.assertEqual(layout.capacities, (364, 364, 218))

    def test_audit_reports_strategy(self):
        audit = audit_duplication()
        self.assertIn("strategy", audit)
        self.assertEqual(audit["strategy"], "C — consolidação conceitual sem compartilhamento físico")

    def test_audit_reports_all_fixture_metrics(self):
        audit = audit_duplication()
        for name in ("first", "simple_call", "sign"):
            with self.subTest(fixture=name):
                self.assertIn(f"{name}_lines", audit)
                self.assertIn(f"{name}_bytes", audit)
                self.assertIn(f"{name}_sha256", audit)
                self.assertIn(f"{name}_buffer_count", audit)

    def test_common_fragments_defined(self):
        self.assertIn(1, COMMON_FRAGMENT_NAMES)
        self.assertEqual(COMMON_FRAGMENT_NAMES[1], ".s3asm")
        self.assertIn(2, COMMON_FRAGMENT_NAMES)
        self.assertEqual(COMMON_FRAGMENT_NAMES[2], ".function")


if __name__ == "__main__":
    unittest.main()
