import unittest
from src.battery_optimizer import BatteryOptimizer

class TestBatteryOptimizer(unittest.TestCase):

    def setUp(self):
        self.battery_optimizer = BatteryOptimizer()

    def test_initial_battery_status(self):
        self.assertEqual(self.battery_optimizer.battery_percentage, 100)

    def test_charge_battery(self):
        self.battery_optimizer.charge_battery(20)
        self.assertEqual(self.battery_optimizer.battery_percentage, 100)

    def test_discharge_battery(self):
        self.battery_optimizer.battery_percentage = 50
        self.battery_optimizer.discharge_battery(20)
        self.assertEqual(self.battery_optimizer.battery_percentage, 30)

    def test_charge_battery_above_limit(self):
        self.battery_optimizer.battery_percentage = 90
        self.battery_optimizer.charge_battery(20)
        self.assertEqual(self.battery_optimizer.battery_percentage, 100)

    def test_discharge_battery_below_zero(self):
        self.battery_optimizer.battery_percentage = 10
        self.battery_optimizer.discharge_battery(20)
        self.assertEqual(self.battery_optimizer.battery_percentage, 0)

    def test_schedule_charging(self):
        self.battery_optimizer.schedule_charging(2, 4)
        self.assertIn((2, 4), self.battery_optimizer.charging_schedule)

    def test_schedule_discharging(self):
        self.battery_optimizer.schedule_discharging(7, 9)
        self.assertIn((7, 9), self.battery_optimizer.discharging_schedule)

if __name__ == '__main__':
    unittest.main()