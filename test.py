import unittest
from vga_driver import TinyVgaDriver


class TinyVgaDriverTestCase(unittest.TestCase):
    def setUp(self):
        pass

    def test__driver_initialization(self):
        vga = TinyVgaDriver()


if __name__ == "__main__":
    unittest.main()
