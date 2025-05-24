class PriceAnalysis:
    """Analyserar elpriser för att hitta bästa ladd-/urladdningstider."""

    def __init__(self, price_data):
        """
        price_data: dict {hour: price}
        """
        self.price_data = price_data

    def get_best_times_to_charge(self, price_difference_threshold=0.30):
        """Return hours where price is at least threshold below average."""
        avg = self.get_average_price()
        best_times = []
        for hour, price in self.price_data.items():
            if price < avg - price_difference_threshold:
                best_times.append((hour, price))
        return sorted(best_times, key=lambda x: x[1])

    def get_best_times_to_discharge(self, price_difference_threshold=0.30):
        """Return hours where price is at least threshold above average."""
        avg = self.get_average_price()
        best_times = []
        for hour, price in self.price_data.items():
            if price > avg + price_difference_threshold:
                best_times.append((hour, price))
        return sorted(best_times, key=lambda x: x[1], reverse=True)

    def get_average_price(self):
        """Return the average price."""
        return sum(self.price_data.values()) / len(self.price_data) if self.price_data else 0

    def get_sorted_hours_by_price(self, reverse=False):
        """Return a list of hours sorted by price (ascending by default)."""
        return sorted(self.price_data.keys(), key=lambda h: self.price_data[h], reverse=reverse)

    def get_price_for_hour(self, hour):
        """Return the price for a specific hour."""
        return self.price_data.get(hour)

    def calculate_charging_time(self, current_battery_percentage, target_battery_percentage, charging_rate):
        """Return hours needed to charge from current to target at given rate."""
        required_charge = target_battery_percentage - current_battery_percentage
        if required_charge <= 0:
            return 0
        return required_charge / charging_rate

    def calculate_discharging_time(self, current_battery_percentage, target_battery_percentage, discharging_rate):
        """Return hours needed to discharge from current to target at given rate."""
        required_discharge = current_battery_percentage - target_battery_percentage
        if required_discharge <= 0:
            return 0
        return required_discharge / discharging_rate