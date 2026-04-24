import unittest

from bot.utils import round_robin as rr


class TestCookieRotation(unittest.TestCase):
    def setUp(self):
        rr.reset_cursor()

    def test_rotate_round_robin_ordering(self):
        items = ["a", "b", "c"]
        self.assertEqual(rr.rotate(items), ["a", "b", "c"])
        self.assertEqual(rr.rotate(items), ["b", "c", "a"])
        self.assertEqual(rr.rotate(items), ["c", "a", "b"])
        self.assertEqual(rr.rotate(items), ["a", "b", "c"])


if __name__ == "__main__":
    unittest.main()
