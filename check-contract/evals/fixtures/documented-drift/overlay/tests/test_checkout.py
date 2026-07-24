import unittest

from src.checkout import apply_discount, checkout_total


class CheckoutTests(unittest.TestCase):
    def test_checkout_and_required_discount_behaviors(self):
        self.assertEqual(checkout_total(10.125), 10.12)
        self.assertEqual(apply_discount(42.50, 0), 42.50)
        self.assertEqual(apply_discount(10, 25), 7.5)
        for percentage in (-1, 101):
            with self.assertRaises(ValueError):
                apply_discount(10, percentage)


if __name__ == "__main__":
    unittest.main()
