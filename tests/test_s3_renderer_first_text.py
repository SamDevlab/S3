import os
import unittest
from bootstrap.s3.pipeline import run_source_with_buffer_capture

class TestFirstTextRenderer(unittest.TestCase):
    def test_first_text_rendering(self):
        s3_path = os.path.join('examples', 'self_hosting', 'assembly_renderer_first_text.s3')
        with open(s3_path) as f:
            source = f.read()
        
        result, capture = run_source_with_buffer_capture(source)
        self.assertEqual(result, 0)
        self.assertTrue(len(capture) > 0, 'Memory capture must not be empty')
        
        memory = capture[-1]
        low = memory.get(0, [])
        high = memory.get(1, [])
        
        out = bytearray()
        for v in low:
            if v is not None and v != 0:
                out.append(v)
        for v in high:
            if v is not None and v != 0:
                out.append(v)
                
        golden_path = os.path.join('tests', 'golden', 'inspect', 'first.assembly.txt')
        with open(golden_path, 'rb') as f:
            golden = f.read().replace(b'\r\n', b'\n')
            
        self.assertEqual(len(out), len(golden), 'Output length must match golden length')
        self.assertEqual(out, golden, 'Output content must match golden content exactly')

if __name__ == '__main__':
    unittest.main()
