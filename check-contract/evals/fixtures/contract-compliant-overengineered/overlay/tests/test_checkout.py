import unittest

from src.checkout import apply_discount, checkout_total


class CheckoutTotalTests(unittest.TestCase):
    def test_rounds_the_subtotal(self):
        self.assertEqual(checkout_total(10.125), 10.12)

    def test_rejects_negative_subtotal(self):
        with self.assertRaises(ValueError):
            checkout_total(-1)


class ApplyDiscountTests(unittest.TestCase):
    def test_required_behaviors(self):
        self.assertEqual(apply_discount(42.50, 0), 42.50)
        self.assertEqual(apply_discount(10.00, 25), 7.50)
        self.assertEqual(apply_discount(10.01, 50), 5.00)
        for percentage in (-1, 101):
            with self.subTest(percentage=percentage):
                with self.assertRaises(ValueError):
                    apply_discount(10, percentage)


if __name__ == "__main__":
    unittest.main()
