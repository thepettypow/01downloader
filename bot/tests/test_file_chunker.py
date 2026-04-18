import os
import tempfile
import unittest

from bot.utils.file_chunker import split_file


class TestFileChunker(unittest.TestCase):
    def test_split_file_respects_max_part_bytes(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "src.bin")
            out_dir = os.path.join(td, "out")
            data = b"a" * (1024 * 1024 + 123)
            with open(src, "wb") as f:
                f.write(data)

            parts = split_file(src, 256 * 1024, out_dir)
            self.assertGreater(len(parts), 1)

            total = 0
            for p in parts:
                sz = os.path.getsize(p)
                self.assertLessEqual(sz, 256 * 1024)
                total += sz

            self.assertEqual(total, len(data))

    def test_split_file_empty_file_creates_one_part(self):
        with tempfile.TemporaryDirectory() as td:
            src = os.path.join(td, "empty.bin")
            out_dir = os.path.join(td, "out")
            open(src, "wb").close()

            parts = split_file(src, 1024, out_dir)
            self.assertEqual(len(parts), 1)
            self.assertTrue(os.path.exists(parts[0]))
            self.assertEqual(os.path.getsize(parts[0]), 0)


if __name__ == "__main__":
    unittest.main()

