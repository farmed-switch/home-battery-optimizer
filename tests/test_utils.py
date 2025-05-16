import unittest
from src.utils.time_utils import convert_to_hour, is_time_in_range
from src.utils.price_utils import calculate_price_difference, get_best_price_hours

class TestUtils(unittest.TestCase):

    def test_convert_to_hour(self):
        self.assertEqual(convert_to_hour("02:00"), 2)
        self.assertEqual(convert_to_hour("12:30"), 12)
        self.assertEqual(convert_to_hour("23:59"), 23)

    def test_is_time_in_range(self):
        self.assertTrue(is_time_in_range("02:00", "01:00", "03:00"))
        self.assertFalse(is_time_in_range("04:00", "01:00", "03:00"))
        self.assertTrue(is_time_in_range("01:30", "01:00", "02:00"))

    def test_calculate_price_difference(self):
        self.assertEqual(calculate_price_difference(1.50, 1.20), 0.30)
        self.assertEqual(calculate_price_difference(2.00, 2.00), 0.00)
        self.assertEqual(calculate_price_difference(1.80, 2.10), -0.30)

    def test_get_best_price_hours(self):
        prices = [1.50, 1.20, 1.80, 2.00, 1.10]
        best_hours = get_best_price_hours(prices, threshold=0.30)
        self.assertIn(1, best_hours)  # Expecting hour index for the lowest price
        self.assertNotIn(3, best_hours)  # Hour index for the highest price

if __name__ == '__main__':
    unittest.main()