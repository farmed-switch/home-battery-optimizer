class BatteryOptimizer:
    def __init__(self, battery_capacity, charge_rate, discharge_rate, price_analysis):
        self.battery_capacity = battery_capacity  # in percentage
        self.current_charge = 0  # current battery charge in percentage
        self.charge_rate = charge_rate  # percentage per hour
        self.discharge_rate = discharge_rate  # percentage per hour
        self.price_analysis = price_analysis  # instance of PriceAnalysis class
        self.schedule = []  # list to hold charging and discharging schedules

    def charge_battery(self, hours, keep_above=90):
        """Charge the battery for a given number of hours, but optionally keep above a certain percent if needed."""
        if self.current_charge < self.battery_capacity:
            charge_amount = min(self.charge_rate * hours, self.battery_capacity - self.current_charge)
            # Om vi redan är på 100% och det är fortsatt optimalt att ladda, håll över 90%
            if self.current_charge + charge_amount > self.battery_capacity:
                if self.should_keep_above_90():
                    self.current_charge = max(self.current_charge, keep_above)
                    self.schedule.append(f"Held charge above {keep_above}% for {hours} hours (optimal to keep high).")
                    return
            self.current_charge += charge_amount
            self.schedule.append(f"Charged {charge_amount}% for {hours} hours.")
        else:
            self.schedule.append("Battery is already fully charged.")

    def discharge_battery(self, hours, keep_above=0):
        """Discharge the battery for a given number of hours, but optionally keep above a certain percent if needed."""
        if self.current_charge > 0:
            discharge_amount = min(self.discharge_rate * hours, self.current_charge - keep_above)
            if discharge_amount <= 0:
                self.schedule.append(f"Held charge above {keep_above}% for {hours} hours (optimal to keep some charge).")
                return
            self.current_charge -= discharge_amount
            self.schedule.append(f"Discharged {discharge_amount}% for {hours} hours.")
        else:
            self.schedule.append("Battery is already empty.")

    def should_keep_above_90(self):
        """Return True if kommande timmar är fortsatt optimala för laddning."""
        # Här behöver du implementera logik baserat på din price_analysis
        return self.price_analysis.is_future_charging_optimal()

    def should_keep_above_0(self):
        """Return True om det är mer ekonomiskt att spara batteri till senare."""
        return self.price_analysis.is_future_discharging_optimal()

    def optimize_charging(self):
        best_times = self.price_analysis.get_best_charging_times()
        for time in best_times:
            if self.current_charge >= 100 and self.should_keep_above_90():
                self.charge_battery(time['duration'], keep_above=90)
            else:
                self.charge_battery(time['duration'])

    def optimize_discharging(self):
        best_times = self.price_analysis.get_best_discharging_times()
        for time in best_times:
            if self.current_charge <= 0 and self.should_keep_above_0():
                self.discharge_battery(time['duration'], keep_above=10)
            else:
                self.discharge_battery(time['duration'])
