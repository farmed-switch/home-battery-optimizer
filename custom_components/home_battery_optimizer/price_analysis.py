class PriceAnalysis:
    def __init__(self, price_data):
        self.price_data = price_data

    def get_best_times_to_charge(self, price_difference_threshold=0.30):
        best_times = []
        for hour, price in self.price_data.items():
            if price < self.get_average_price() - price_difference_threshold:
                best_times.append((hour, price))
        return sorted(best_times, key=lambda x: x[1])

    def get_best_times_to_discharge(self, price_difference_threshold=0.30):
        best_times = []
        for hour, price in self.price_data.items():
            if price > self.get_average_price() + price_difference_threshold:
                best_times.append((hour, price))
        return sorted(best_times, key=lambda x: x[1], reverse=True)

    def get_average_price(self):
        return sum(self.price_data.values()) / len(self.price_data)

    def calculate_charging_time(self, current_battery_percentage, target_battery_percentage, charging_rate):
        required_charge = target_battery_percentage - current_battery_percentage
        if required_charge <= 0:
            return 0
        return required_charge / charging_rate

    def calculate_discharging_time(self, current_battery_percentage, target_battery_percentage, discharging_rate):
        required_discharge = current_battery_percentage - target_battery_percentage
        if required_discharge <= 0:
            return 0
        return required_discharge / discharging_rate