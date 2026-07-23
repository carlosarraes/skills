import unittest

from src.checkout import checkout_total


class CheckoutTotalTests(unittest.TestCase):
    def test_rounds_the_subtotal(self):
        self.assertEqual(checkout_total(10.125), 10.12)

    def test_rejects_negative_subtotal(self):
        with self.assertRaises(ValueError):
            checkout_total(-1)


if __name__ == "__main__":
    unittest.main()
