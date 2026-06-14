"""The team's own tests — green on the solution world. taskify STRIPS these from task/ (they'd spoil
and the candidate writes their own); the hidden suite is what actually grades."""
import unittest

from nesting import max_depth


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
