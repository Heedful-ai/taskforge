import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
from nesting import max_depth  # noqa: E402


class TestMaxDepth(unittest.TestCase):
    def test_flat(self):
        self.assertEqual(max_depth("()()"), 1)

    def test_nested(self):
        self.assertEqual(max_depth("(())"), 2)
        self.assertEqual(max_depth("((()))"), 3)

    def test_empty(self):
        self.assertEqual(max_depth(""), 0)


if __name__ == "__main__":
    unittest.main()
