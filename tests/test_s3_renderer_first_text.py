import hashlib
import os
import unittest
from tools.s3_renderer_contract import (
    FIXTURE_METADATA,
    _capture_fixture_output,
    _git_blob_bytes,
)

EXPECTED_SHA256 = FIXTURE_METADATA["first"].expected_sha256
EXPECTED_BYTES = FIXTURE_METADATA["first"].expected_bytes


class TestFirstTextRenderer(unittest.TestCase):
    def test_first_text_rendering(self):
        meta = FIXTURE_METADATA["first"]
        s3_path = os.path.join(*meta.s3_path.split("/"))
        with open(s3_path) as f:
            source = f.read()

        output = _capture_fixture_output(source, meta.buffer_count, meta.buffer_offset, meta.entry, meta.max_instructions, meta.expected_bytes)

        sha256 = hashlib.sha256(output).hexdigest()
        self.assertEqual(sha256, EXPECTED_SHA256)

        golden = _git_blob_bytes(meta.golden_path)

        self.assertEqual(len(output), len(golden))
        self.assertEqual(output, golden)

    def test_expected_sha256_constant(self):
        self.assertEqual(
            EXPECTED_SHA256,
            "a144d584ed40287d10cff5ecc50a170823aac7ddd0a7fed455837b936131a90f",
        )

    def test_expected_bytes_constant(self):
        self.assertEqual(EXPECTED_BYTES, 377)


if __name__ == "__main__":
    unittest.main()
