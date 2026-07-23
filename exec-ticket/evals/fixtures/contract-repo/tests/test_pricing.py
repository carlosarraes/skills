import unittest

from src.pricing import validate_percentage


class PercentageValidationTests(unittest.TestCase):
    def test_accepts_boundaries(self):
        self.assertIsNone(validate_percentage(0))
        self.assertIsNone(validate_percentage(100))

    def test_rejects_out_of_range_values(self):
        for percentage in (-1, 101):
            with self.subTest(percentage=percentage):
                with self.assertRaises(ValueError):
                    validate_percentage(percentage)


if __name__ == "__main__":
    unittest.main()
