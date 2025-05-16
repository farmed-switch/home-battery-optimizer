import unittest
from src.price_analysis import PriceAnalysis

class TestPriceAnalysis(unittest.TestCase):

    def setUp(self):
        self.price_data = {
            "2023-10-01": [0.10, 0.12, 0.15, 0.20, 0.18, 0.16, 0.14, 0.13, 0.11, 0.09, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05],
            "2023-10-02": [0.11, 0.13, 0.14, 0.19, 0.17, 0.15, 0.13, 0.12, 0.10, 0.08, 0.07, 0.06, 0.05, 0.04, 0.03, 0.02, 0.01, 0.00, 0.01, 0.02, 0.03, 0.04, 0.05, 0.06]
        }
        self.price_analysis = PriceAnalysis(self.price_data)

    def test_best_hours_to_charge(self):
        best_hours = self.price_analysis.get_best_hours_to_charge()
        expected_hours = [(0, 0.00), (1, 0.01), (2, 0.02), (3, 0.03), (4, 0.04), (5, 0.05)]
        self.assertEqual(best_hours, expected_hours)

    def test_best_hours_to_discharge(self):
        best_hours = self.price_analysis.get_best_hours_to_discharge()
        expected_hours = [(3, 0.19), (2, 0.14), (1, 0.13), (0, 0.11)]
        self.assertEqual(best_hours, expected_hours)

    def test_price_difference_threshold(self):
        self.price_analysis.set_price_difference_threshold(0.30)
        self.assertEqual(self.price_analysis.price_difference_threshold, 0.30)

    def test_analyze_prices(self):
        analysis_result = self.price_analysis.analyze_prices()
        self.assertIn('best_charge_hours', analysis_result)
        self.assertIn('best_discharge_hours', analysis_result)

if __name__ == '__main__':
    unittest.main()