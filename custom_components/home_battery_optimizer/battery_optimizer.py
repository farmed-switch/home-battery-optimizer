import math
from datetime import datetime, timedelta

class BatteryOptimizer:
    def __init__(self, battery_capacity=100, charge_rate=10, discharge_rate=10,
                 charge_pct=100, discharge_pct=0, price_analysis=None, min_profit=0.01, hass=None):
        self.battery_capacity = battery_capacity
        self.charge_rate = charge_rate
        self.discharge_rate = discharge_rate
        self.charge_pct = charge_pct
        self.discharge_pct = discharge_pct
        self.price_analysis = price_analysis
        self.min_profit = min_profit
        self.schedule = []
        self.current_charge = 0
        self.hass = hass  # Viktigt för loggning

    def log(self, msg):
        pass  # Loggning till notifikationsfältet är nu inaktiverad

    def generate_schedule(self, soc):
        self.schedule = []
        self.current_charge = soc
        if not self.price_analysis or not hasattr(self.price_analysis, "price_data"):
            return []
        prices = self.price_analysis.price_data
        # prices är nu en lista av dictar med 'start', 'end', 'value'
        n_hours = len(prices)
        now = datetime.now()
        now_hour = now.replace(minute=0, second=0, microsecond=0)
        start_idx = 0
        for i, entry in enumerate(prices):
            start_dt = datetime.fromisoformat(entry["start"])
            if start_dt >= now_hour:
                start_idx = i
                break
        # Markera alla timmar före aktuell timme som 'past'
        actions = ["idle"] * n_hours
        socs = [None] * n_hours
        current_soc = soc
        for i in range(start_idx):
            actions[i] = "idle"
            socs[i] = soc
        # (Resten av logiken jobbar bara på framtida timmar)
        idx = start_idx
        used_hours = set()
        hours = list(range(n_hours))
        # Beräkna mean_price för framtida timmar
        future_prices = [entry["value"] for entry in prices[start_idx:]]
        mean_price = sum(future_prices) / len(future_prices) if future_prices else 0
        while idx < n_hours:
            # 1. Leta efter närmaste urladdningstimme där pris >= mean + min_profit
            discharge_idx = None
            for j in range(idx, n_hours):
                if prices[j]["value"] >= mean_price + self.min_profit:
                    discharge_idx = j
                    break
            if discharge_idx is None:
                break  # Inga fler lönsamma urladdningstimmar
            # 2. Leta billigaste laddtimmar från idx till discharge_idx (inklusive)
            charge_needed = max(self.charge_pct - current_soc, 0)
            charge_hours = int(math.ceil(charge_needed / self.charge_rate))
            charge_candidates = [(k, prices[k]["value"]) for k in range(idx, discharge_idx)]
            charge_candidates.sort(key=lambda x: x[1])
            charge_hours = min(charge_hours, discharge_idx - idx)  # Kan inte ladda fler timmar än som finns
            charge_hours_idxs = [k for k, _ in charge_candidates[:charge_hours]]
            # 3. Markera laddningstimmar
            for k in charge_hours_idxs:
                if current_soc >= self.charge_pct:
                    break
                if k in used_hours:
                    continue
                charge_amount = min(self.charge_rate, self.charge_pct - current_soc)
                if charge_amount <= 0:
                    continue
                current_soc += charge_amount
                actions[k] = "charge"
                socs[k] = current_soc
                used_hours.add(k)
            # 4. Markera urladdningstimmen och sänk SoC
            if discharge_idx not in used_hours:
                actions[discharge_idx] = "discharge"
                # Sänk SoC vid discharge
                current_soc = max(current_soc - self.discharge_rate, self.discharge_pct)
                socs[discharge_idx] = current_soc
                used_hours.add(discharge_idx)
            idx = discharge_idx + 1
        # Efter att ha markerat charge/discharge, gå igenom alla framtida timmar och sänk SoC varje timme som är 'discharge'
        for i in range(start_idx, n_hours):
            if actions[i] == "discharge":
                if i == 0:
                    prev_soc = soc
                else:
                    prev_soc = socs[i-1] if socs[i-1] is not None else soc
                socs[i] = max(prev_soc - self.discharge_rate, self.discharge_pct)

        # Korrekt SoC-uppdatering: gå igenom alla timmar i ordning och ändra SoC endast vid charge/discharge
        last_soc = soc
        for i in range(start_idx, n_hours):
            if actions[i] == "charge":
                last_soc = min(last_soc + self.charge_rate, self.charge_pct)
            elif actions[i] == "discharge":
                last_soc = max(last_soc - self.discharge_rate, self.discharge_pct)
            socs[i] = last_soc

        # Fyll i idle före start_idx
        for i in range(start_idx):
            socs[i] = soc

        # Fyll i idle och propagatera SoC
        last_soc = soc
        for i in range(start_idx, n_hours):
            if socs[i] is None:
                socs[i] = last_soc
            else:
                last_soc = socs[i]
        self.schedule = []
        for i in range(n_hours):
            self.schedule.append({
                "hour": i,
                "action": actions[i],
                "price": prices[i]["value"],
                "soc": socs[i],
                "past": i < start_idx
            })
        return self.schedule