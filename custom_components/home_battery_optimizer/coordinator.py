import logging
from datetime import datetime, timedelta

DOMAIN = "home_battery_optimizer"

_LOGGER = logging.getLogger(__name__)

class HomeBatteryOptimizerCoordinator:
    def __init__(self, hass, config):
        self.hass = hass
        self.config = config
        self.schedule = []
        self.soc = None
        self.current_power = None
        self.target_soc = None
        self.status = None
        self.price_data = None
        self.max_charge_windows = 3  # Default, can be set 1-5
        self.status_attributes = {}
        self.charging_on = False
        self.discharging_on = False
        self.charge_rate = 25
        self.discharge_rate = 25
        self.max_battery_soc = 100
        self.min_battery_soc = 0
        self.self_usage_on = False
        self._self_usage_last_change = None
        self._self_usage_condition_met = False
        self._self_usage_last_check = None
        self._self_usage_max_battery_power = 0
        self._self_usage_delay_seconds = 120  # 2 minuter
        self._device_info = {
            "identifiers": {(DOMAIN, "home_battery_optimizer")},
            "name": "Home Battery Optimizer",
            "manufacturer": "farmed-switch",
            "model": "Home Battery Optimizer"
        }
        self.charge_periods = []  # Lista av dictar med kommande charge-perioder
        self.discharge_periods = []  # Lista av dictar med kommande discharge-perioder
        self.min_profit = 10  # Minimum profit threshold, default 10
        self._entity_update_callbacks = set()

    @property
    def device_info(self):
        return self._device_info

    async def async_update_all(self):
        # Hämta SoC och prisdata
        self.update_soc()
        self.update_price_data()
        # Generera schema och status
        # ...lägg all logik här...
        # Uppdatera self.schedule, self.soc, self.status_attributes osv
        # ...existing code...

    def update_soc(self):
        battery_entity_id = self.config.get("battery_entity")
        soc = None
        soc_changed = False
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            if battery_state and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    new_soc = float(battery_state.state)
                    soc_changed = (self.soc != new_soc)
                    soc = new_soc
                except Exception:
                    soc = None
        soc_update_needed = soc_changed
        self.soc = soc
        # Hämta även effekt om tillgängligt
        battery_power_entity = self.config.get("battery_power_entity")
        if battery_power_entity:
            power_state = self.hass.states.get(battery_power_entity)
            try:
                self.current_power = float(power_state.state) if power_state and power_state.state not in (None, "", "unknown", "unavailable") else None
            except Exception:
                self.current_power = None
        # Hämta target_soc om tillgängligt
        target_soc_entity = self.config.get("target_soc_entity")
        if target_soc_entity:
            target_soc_state = self.hass.states.get(target_soc_entity)
            try:
                self.target_soc = float(target_soc_state.state) if target_soc_state and target_soc_state.state not in (None, "", "unknown", "unavailable") else None
            except Exception:
                self.target_soc = None
        # Sätt status
        if self.charging_on:
            self.status = "charging"
        elif self.discharging_on:
            self.status = "discharging"
        elif self.soc is not None:
            self.status = "idle"
        else:
            self.status = None
        return soc_update_needed

    def update_price_data(self):
        price_entity_id = self.config.get("nordpool_entity")
        price_data = []
        if price_entity_id:
            price_state = self.hass.states.get(price_entity_id)
            if price_state and hasattr(price_state, "attributes"):
                raw_today = price_state.attributes.get("raw_today", [])
                raw_tomorrow = price_state.attributes.get("raw_tomorrow", [])
                # Start from today 00:00
                base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                all_hours = list(raw_today) + list(raw_tomorrow)
                for i, item in enumerate(all_hours):
                    start_dt = base_time + timedelta(hours=i)
                    end_dt = base_time + timedelta(hours=i+1)
                    price_data.append({
                        "start": start_dt.isoformat(),
                        "end": end_dt.isoformat(),
                        "value": float(item["value"])
                    })
        self.price_data = price_data
        return price_data

    def get_available_hours(self):
        if not self.price_data:
            return []
        now = datetime.now()
        available = []
        for i, _ in self.price_data.items():
            hour_dt = now.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=i)
            if hour_dt >= now:
                available.append(i)
        return available

    def limit_charge_windows(self, schedule, max_windows=3):
        # Only allow up to max_windows charge periods in the schedule
        charge_blocks = [i for i, item in enumerate(schedule) if item.get("action") == "charge"]
        if len(charge_blocks) <= max_windows:
            return schedule
        # Keep only the lowest price charge windows
        sorted_blocks = sorted(charge_blocks, key=lambda i: schedule[i]["price"])
        keep = set(sorted_blocks[:max_windows])
        for i in charge_blocks:
            if i not in keep:
                schedule[i]["action"] = "idle"
        return schedule

    def find_charge_windows(self):
        """
        Find charge windows based on falling price, min_profit, and peak detection.
        Ensure that no window overlaps another; each starts after the previous ends.
        """
        price_data = self.price_data or []
        min_profit = getattr(self, "min_profit", 10)
        windows = []
        i = 0
        n = len(price_data)
        window_counter = 1
        _LOGGER.debug(f"find_charge_windows: min_profit={min_profit}, n={n}")
        while i < n - 1:
            # 1. Find first falling price sequence (local minimum)
            start_idx = i
            ref_idx = i
            ref_price = price_data[i]["value"]
            while i + 1 < n and price_data[i+1]["value"] < ref_price:
                i += 1
                ref_price = price_data[i]["value"]
                ref_idx = i
            min_idx = ref_idx
            min_price = ref_price
            # 2. Look for price increase that meets min_profit
            found = False
            j = min_idx + 1
            while j < n:
                if price_data[j]["value"] >= min_price + min_profit:
                    found = True
                    break
                if price_data[j]["value"] < min_price:
                    min_price = price_data[j]["value"]
                    min_idx = j
                j += 1
            if not found:
                _LOGGER.debug(f"No more windows found after i={i}, min_price={min_price}")
                break  # No more windows
            # 3. Find peak after threshold met
            peak_idx = j
            peak_price = price_data[j]["value"]
            k = j + 1
            while k < n and price_data[k]["value"] > peak_price:
                peak_idx = k
                peak_price = price_data[k]["value"]
                k += 1
            # 4. Store window (no overlap: next window starts after this one ends)
            window = {
                "window": window_counter,  # Ändra från f"window_{window_counter}" till int
                "start": price_data[start_idx]["start"],
                "end": price_data[peak_idx]["end"],
                "min_price": min_price,
                "max_price": peak_price,
                "start_idx": start_idx,
                "end_idx": peak_idx
            }
            _LOGGER.debug(f"Window found: {window}")
            windows.append(window)
            window_counter += 1
            i = peak_idx + 1  # Move to first hour after this window (no overlap)
        self.charge_windows = windows
        _LOGGER.debug(f"Total windows found: {len(windows)}")
        return windows

    def build_full_schedule(self, force_all_unpassed=False):
        """
        Huvudmetod som bygger hela ladd- och urladdningsschemat enligt stepwise-logik:
        1. Hämta data från self.config (Home Assistant)
        2. Bygg prislista (self.price_data)
        3. Initiera schedule med prisdata (hela dygnet, även historik)
        4. Markera alla timmar där end < now som passed=True (om force_all_unpassed=False)
        5. Endast framtida timmar (passed=False) får ändras av window/charge/discharge-logik
        6. Allt lagras i self.schedule.
        """
        soc = self.soc if self.soc is not None else 0
        charge_rate = self.charge_rate
        discharge_rate = self.discharge_rate
        max_soc = self.max_battery_soc
        min_soc = self.min_battery_soc
        min_profit = self.min_profit
        price_data = self.price_data or []
        # Kontroll: Bygg bara schema om både SoC och prisdata är giltiga
        if soc is None or not price_data or len(price_data) < 1:
            _LOGGER.warning("[HBO] Skipping schedule build: SoC or price data not available yet (build_full_schedule).")
            self.schedule = []
            return
        self.schedule = []
        now = datetime.now()
        # Initiera schedule med passed-attribut
        for entry in price_data:
            end_dt = datetime.fromisoformat(entry["end"])
            passed = False
            if not force_all_unpassed:
                passed = end_dt < now
            self.schedule.append({
                "start": entry["start"],
                "end": entry["end"],
                "price": entry["value"],
                "action": "idle",
                "charge": 0,
                "discharge": 0,
                "window": None,
                "estimated_soc": None,
                "passed": passed
            })
        # Window-skapande och laddlogik utgår nu från första timmen, och logik körs för ALLA timmar
        window_counter = 1
        idx = 0
        prev_discharge_end = 0
        prev_soc = soc
        n = len(self.schedule)
        while idx < n:
            # a) Hitta första möjliga start efter prev_discharge_end (även passed)
            available_idxs = [i for i in range(prev_discharge_end, n)]
            if not available_idxs:
                break
            start_idx = available_idxs[0]
            # b) Hitta window: fallande pris till minimum, sedan ökning >= min_profit
            i = start_idx
            # Hitta lokal minimum
            while i+1 < n and self.schedule[i+1]["price"] < self.schedule[i]["price"]:
                i += 1
            min_idx = i
            min_price = self.schedule[min_idx]["price"]
            # Hitta första index där priset ökar minst min_profit
            found = False
            j = min_idx + 1
            while j < n:
                if self.schedule[j]["price"] >= min_price + min_profit:
                    found = True
                    break
                if self.schedule[j]["price"] < min_price:
                    min_price = self.schedule[j]["price"]
                    min_idx = j
                j += 1
            if not found:
                break
            # Hitta peak (slut på window)
            peak_idx = j
            peak_price = self.schedule[peak_idx]["price"]
            k = j + 1
            while k < n and self.schedule[k]["price"] > peak_price:
                peak_idx = k
                peak_price = self.schedule[k]["price"]
                k += 1
            window_start = start_idx
            window_end = peak_idx
            # c) Planera laddning i window (alla timmar)
            soc_needed = max(0, max_soc - prev_soc)
            hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
            if soc_needed < 5:
                hours_needed = 0
            window_prices = [(i, self.schedule[i]["price"]) for i in range(window_start, window_end+1)]
            sorted_hours = sorted(window_prices, key=lambda x: x[1])
            charge_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
            current_soc = prev_soc
            charge_prices = []
            for i in range(window_start, window_end+1):
                if i in charge_idxs and current_soc < max_soc - 5:
                    self.schedule[i]["charge"] = 1
                    self.schedule[i]["action"] = "charge"
                    charge_prices.append(self.schedule[i]["price"])
                    current_soc = min(current_soc + charge_rate, max_soc)
                else:
                    self.schedule[i]["charge"] = 0
                self.schedule[i]["window"] = window_counter
                self.schedule[i]["estimated_soc"] = round(current_soc, 2)
            avg_charge_price = sum(charge_prices) / len(charge_prices) if charge_prices else 0
            # d) Bygg discharge för window (alla timmar)
            discharge_soc = self.schedule[window_end]["estimated_soc"] if self.schedule[window_end]["estimated_soc"] is not None else current_soc
            soc_needed_discharge = max(discharge_soc - min_soc, 0)
            hours_needed_discharge = int((soc_needed_discharge + discharge_rate - 1) // discharge_rate)
            if hours_needed_discharge < 1:
                prev_discharge_end = window_end + 1
                prev_soc = current_soc
                window_counter += 1
                continue
            lookup = max(0, hours_needed_discharge - 1)
            idxs = [i for i in range(max(0, window_end - lookup), min(n, window_end + lookup + 1))]
            prices = [(i, self.schedule[i]["price"]) for i in idxs]
            last_price = self.schedule[window_end]["price"]
            max_price = max(prices, key=lambda x: x[1])[1] if prices else last_price
            while max_price > last_price:
                max_idx = max(prices, key=lambda x: x[1])[0]
                window_end = max_idx
                discharge_soc = self.schedule[window_end]["estimated_soc"] if self.schedule[window_end]["estimated_soc"] is not None else current_soc
                soc_needed_discharge = max(discharge_soc - min_soc, 0)
                hours_needed_discharge = int((soc_needed_discharge + discharge_rate - 1) // discharge_rate)
                if hours_needed_discharge < 1:
                    break
                lookup = max(0, hours_needed_discharge - 1)
                idxs = [i for i in range(max(0, window_end - lookup), min(n, window_end + lookup + 1))]
                prices = [(i, self.schedule[i]["price"]) for i in idxs]
                last_price = self.schedule[window_end]["price"]
                max_price = max(prices, key=lambda x: x[1])[1] if prices else last_price
            discharge_candidates = [(i, price) for i, price in prices if price >= avg_charge_price + min_profit]
            discharge_candidates.sort(key=lambda x: x[1], reverse=True)
            discharge_idxs = sorted([i for i, _ in discharge_candidates[:hours_needed_discharge]])
            current_soc = discharge_soc
            # NY LOGIK: Fyll i alla timmar mellan första och sista discharge-timmen
            if discharge_idxs:
                discharge_start = discharge_idxs[0]
                discharge_end = discharge_idxs[-1]
                for i in range(discharge_start, discharge_end + 1):
                    self.schedule[i]["discharge"] = 1
                    self.schedule[i]["action"] = "discharge"
                    self.schedule[i]["window"] = window_counter
                    self.schedule[i]["charge"] = 0  # Ta bort eventuell laddning
                    self.schedule[i]["estimated_soc"] = round(current_soc, 2)
                    current_soc = max(current_soc - discharge_rate, min_soc)
                # Fyll i tomma window-index mellan prev_discharge_end och discharge_end
                for i in range(prev_discharge_end, discharge_end + 1):
                    if self.schedule[i]["window"] is None:
                        self.schedule[i]["window"] = window_counter
            # Om du vill nollställa charge på övriga timmar i window efter discharge_start, kan du lägga till det här
            if discharge_idxs:
                prev_discharge_end = discharge_end + 1
                prev_soc = current_soc
            else:
                prev_discharge_end = window_end + 1
                prev_soc = current_soc
            window_counter += 1
        # Efter att hela schemat är byggt: fyll i alla None-värden för estimated_soc
        last_soc = None
        for entry in self.schedule:
            if entry["estimated_soc"] is not None:
                last_soc = entry["estimated_soc"]
            else:
                entry["estimated_soc"] = last_soc
        return self.schedule

    def update_charge_discharge_periods(self):
        """Hitta och spara alla kommande charge- och discharge-perioder från schemat."""
        self.charge_periods = []
        self.discharge_periods = []
        if not self.schedule:
            return
        current_time = datetime.now()
        # Hitta alla block av charge/discharge
        def find_periods(action_name):
            periods = []
            start_idx = None
            for idx, item in enumerate(self.schedule):
                if item.get("action") == action_name and not item.get("past"):
                    if start_idx is None:
                        start_idx = idx
                else:
                    if start_idx is not None:
                        stop_idx = idx - 1
                        periods.append({
                            "start_idx": start_idx,
                            "stop_idx": stop_idx,
                            "start_time": self._get_time_for_index(start_idx),
                            "stop_time": self._get_time_for_index(stop_idx + 1),
                            "number_of_hours": stop_idx - start_idx + 1
                        })
                        start_idx = None
            # Om perioden går till slutet
            if start_idx is not None:
                stop_idx = len(self.schedule) - 1
                periods.append({
                    "start_idx": start_idx,
                    "stop_idx": stop_idx,
                    "start_time": self._get_time_for_index(start_idx),
                    "stop_time": self._get_time_for_index(stop_idx + 1),
                    "number_of_hours": stop_idx - start_idx + 1
                })
            return periods
        self.charge_periods = find_periods("charge")
        self.discharge_periods = find_periods("discharge")

    def _get_time_for_index(self, idx):
        # Returnerar datetime för idx i schemat (timvis schema)
        today = datetime.now().replace(minute=0, second=0, microsecond=0)
        return today + timedelta(hours=idx)

    async def async_update_sensors(self):
        """Update SoC, price data, schedule, and notify listeners."""
        soc_update_needed = self.update_soc()
        self.update_price_data()
        _LOGGER.warning(f"[HBO DEBUG] soc={self.soc}, price_data_len={len(self.price_data) if self.price_data else 0}")
        # Kontroll: Bygg bara schema om både SoC och prisdata är giltiga
        if self.soc is None or not self.price_data or len(self.price_data) < 1:
            _LOGGER.warning("[HBO] Skipping schedule build: SoC or price data not available yet.")
            return
        # Bygg alltid nytt schema enligt stepwise-logik
        self.build_full_schedule()
        _LOGGER.warning(f"[HBO DEBUG] schedule_len={len(self.schedule)}; first={self.schedule[0] if self.schedule else None}")
        # Self use-logik ska alltid uppdateras
        await self.async_update_self_usage()
        self.update_charge_discharge_periods()
        if hasattr(self, 'async_update_listeners'):
            await self.async_update_listeners()
        # Skicka notifikation till Home Assistant UI
        await self._send_schedule_notification()

    async def _send_schedule_notification(self):
        """Skicka en notifikation med hela schemat till Home Assistant UI."""
        if not self.schedule:
            return
        # Bygg tabell som text
        header = f"| Start | End | Action | Price | Estimated SoC | Charge | Discharge | Window |\n|---|---|---|---|---|---|---|---|"
        rows = []
        for entry in self.schedule:
            rows.append(f"| {entry.get('start','')} | {entry.get('end','')} | {entry.get('action','')} | {entry.get('price','')} | {entry.get('estimated_soc','')} | {entry.get('charge','')} | {entry.get('discharge','')} | {entry.get('window','')} |")
        table = header + "\n" + "\n".join(rows)
        # Lägg till felsökningsinfo
        debug_info = f"\n\n**[DEBUG] min_profit:** {getattr(self, 'min_profit', None)}\n"
        debug_info += f"**[DEBUG] SoC:** {getattr(self, 'soc', None)}\n"
        debug_info += f"**[DEBUG] Price data:** {[e['value'] for e in self.price_data]}\n"
        debug_info += f"**[DEBUG] Windows:** {getattr(self, 'charge_windows', None)}\n"
        debug_info += f"**[DEBUG] Now:** {datetime.now().isoformat()}\n"
        message = f"**Batterischema uppdaterat**\n\n{table}{debug_info}"
        try:
            await self.hass.services.async_call(
                "persistent_notification",
                "create",
                {
                    "title": "Home Battery Optimizer",
                    "message": message,
                    "notification_id": "hbo_schedule_update"
                },
                blocking=True
            )
        except Exception as e:
            _LOGGER.error(f"Kunde inte skicka notifikation: {e}")

    def add_update_callback(self, callback):
        self._entity_update_callbacks.add(callback)

    def remove_update_callback(self, callback):
        self._entity_update_callbacks.discard(callback)

    async def async_update_listeners(self):
        """Notify all registered entity update callbacks."""
        for callback in list(self._entity_update_callbacks):
            if callable(callback):
                try:
                    result = callback()
                    if hasattr(result, "__await__"):
                        await result
                except Exception as e:
                    _LOGGER.error(f"Error in entity update callback: {e}")

    def build_charge_schedule_window1(self):
        """
        Bygg laddschema för endast window 1:
        - Använd aktuell SOC, charge_rate och max_battery_soc
        - Sortera priserna i window 1 och välj billigaste timmarna
        - Sätt charge=1 för dessa, annars 0
        - Implementera dödzon: starta ej ny sektion om <5% från max
        - Skriv estimated_soc
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            return []
        window = self.charge_windows[0]
        start_idx = window["start_idx"]
        end_idx = window["end_idx"]
        soc = self.soc if self.soc is not None else 0
        max_soc = self.max_battery_soc
        charge_rate = self.charge_rate
        n_hours = end_idx - start_idx + 1
        # Hur många timmar behövs?
        soc_needed = max(0, max_soc - soc)
        hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
        # Dödzon: om soc_needed < 5% -> ingen laddning
        if soc_needed < 5:
            hours_needed = 0
        # Hämta priser och index för window 1
        window_prices = [
            (i, float(self.price_data[i]["value"]))
            for i in range(start_idx, end_idx + 1)
        ]
        # Sortera på pris, ta billigaste timmarna
        sorted_hours = sorted(window_prices, key=lambda x: x[1])
        charge_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
        # Bygg charge_raw och estimated_soc
        charge_raw = []
        estimated_soc = []
        current_soc = soc
        now = datetime.now()
        for i in range(len(self.price_data)):
            entry = self.price_data[i]
            # Endast tillåt laddning i window 1 och om timmen inte har passerat
            in_window1 = start_idx <= i <= end_idx
            end_dt = datetime.fromisoformat(entry["end"])
            is_future = end_dt > now
            charge = 1 if i in charge_idxs and in_window1 else 0
            # Dödzon: om vi är inom 5% från max, ingen laddning
            if current_soc >= max_soc - 5:
                charge = 0
            if charge:
                current_soc = min(current_soc + charge_rate, max_soc)
            charge_raw.append({
                "start": entry["start"],
                "end": entry["end"],
                "charge": charge
            })
            estimated_soc.append({
                "start": entry["start"],
                "end": entry["end"],
                "soc": round(current_soc, 2)
            })
        self.charge_raw_window1 = charge_raw
        self.estimated_soc_window1 = estimated_soc
        return charge_raw

    def build_charge_schedule_window2(self):
        """
        Bygg laddschema för window 2 (om det finns):
        - Utgå från estimated_soc efter window 1
        - Endast timmar i window 2 som inte redan använts i window 1 får användas
        - Samma logik som window 1
        - Skriv charge_raw_window2 och estimated_soc_window2
        """
        if not self.price_data or not hasattr(self, "charge_windows") or len(self.charge_windows) < 2:
            self.charge_raw_window2 = None
            self.estimated_soc_window2 = None
            return []
        window1 = self.charge_windows[0]
        window2 = self.charge_windows[1]
        start_idx2 = window2["start_idx"]
        end_idx2 = window2["end_idx"]
        # estimated_soc efter window 1
        estimated_soc1 = getattr(self, "estimated_soc_window1", None)
        if not estimated_soc1:
            self.charge_raw_window2 = None
            self.estimated_soc_window2 = None
            return []
        # Hitta sista SoC från window 1 (eller aktuell SoC om window 1 är i framtiden)
        soc_after_w1 = None
        for entry in reversed(estimated_soc1):
            end_dt = datetime.fromisoformat(entry["end"])
            if end_dt <= datetime.now():
                soc_after_w1 = entry["soc"]
                break
        if soc_after_w1 is None:
            soc_after_w1 = estimated_soc1[window1["end_idx"]]["soc"]
        soc = soc_after_w1
        max_soc = self.max_battery_soc
        charge_rate = self.charge_rate
        soc_needed = max(0, max_soc - soc)
        hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
        if soc_needed < 5:
            hours_needed = 0
        # Endast tillåt timmar i window 2 som INTE är i window 1
        used_idxs = set(range(window1["start_idx"], window1["end_idx"]+1))
        window2_idxs = [i for i in range(start_idx2, end_idx2+1) if i not in used_idxs]
        window_prices = [(i, float(self.price_data[i]["value"])) for i in window2_idxs]
        sorted_hours = sorted(window_prices, key=lambda x: x[1])
        charge_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
        charge_raw = []
        estimated_soc = []
        current_soc = soc
        now = datetime.now()
        for i in range(len(self.price_data)):
            entry = self.price_data[i]
            in_window2 = i in window2_idxs
            # end_dt = datetime.fromisoformat(entry["end"])
            # is_future = end_dt > now
            charge = 1 if i in charge_idxs and in_window2 else 0
            if current_soc >= max_soc - 5:
                charge = 0
            if charge:
                current_soc = min(current_soc + charge_rate, max_soc)
            charge_raw.append({
                "start": entry["start"],
                "end": entry["end"],
                "charge": charge
            })
            estimated_soc.append({
                "start": entry["start"],
                "end": entry["end"],
                "soc": round(current_soc, 2)
            })
        self.charge_raw_window2 = charge_raw
        self.estimated_soc_window2 = estimated_soc
        return charge_raw

    def build_charge_schedule_windows(self):
        """
        Build charge schedule for all charge windows:
        - For each window: start from estimated SoC after previous window (or SoC for window 1)
        - Only use hours in the current window that are not already used in previous windows
        - Annotate each schedule entry with per-window charge plan and estimated SoC
        - All results are stored in self.schedule, not as dynamic attributes
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            return []
        used_idxs = set()
        prev_soc = self.soc if self.soc is not None else 0
        for n, window in enumerate(self.charge_windows[:4], start=1):
            start_idx = window["start_idx"]
            end_idx = window["end_idx"]
            max_soc = self.max_battery_soc
            charge_rate = self.charge_rate
            soc_needed = max(0, max_soc - prev_soc)
            hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
            if soc_needed < 5:
                hours_needed = 0
            window_idxs = [i for i in range(start_idx, end_idx+1) if i not in used_idxs]
            window_prices = [(i, float(self.price_data[i]["value"])) for i in window_idxs]
            sorted_hours = sorted(window_prices, key=lambda x: x[1])
            charge_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
            current_soc = prev_soc
            charge_prices = []
            for i in range(len(self.price_data)):
                entry = self.price_data[i]
                in_window = i in window_idxs
                charge = 1 if i in charge_idxs and in_window else 0
                if current_soc >= max_soc - 5:
                    charge = 0
                if charge:
                    current_soc = min(current_soc + charge_rate, max_soc)
                    if in_window:
                        charge_prices.append(float(entry["value"]))
                # Annotate schedule entry if it exists
                if i < len(self.schedule):
                    self.schedule[i][f"charge_window_{n}"] = charge
                    self.schedule[i][f"estimated_soc_window_{n}"] = round(current_soc, 2)
            avg_price = sum(charge_prices) / len(charge_prices) if charge_prices else None
            window["avg_charge_price"] = avg_price
            # For next window: use last SoC in window
            for i in reversed(range(start_idx, end_idx+1)):
                if i < len(self.schedule):
                    prev_soc = self.schedule[i][f"estimated_soc_window_{n}"]
                    break
            used_idxs.update(window_idxs)
        return True

    def build_discharge_schedule_windows(self):
        """
        Förbättrad discharge-logik:
        - Discharge startar vid slutet av en charge window och väljer bästa timmar runt detta index
        - Endast timmar där priset är minst (avg_charge_price + min_profit) används
        - Annoterar self.schedule med discharge=1 för dessa timmar, övriga får discharge=0
        - estimated_soc uppdateras för varje discharge-timme
        - Allt sker per window och är generaliserat
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            return []
        now = datetime.now()
        min_profit = getattr(self, "min_profit", 10)
        num_windows = len(self.charge_windows)
        for n in range(1, num_windows + 1):
            window = self.charge_windows[n-1]
            start_idx = window["start_idx"]
            end_idx = window["end_idx"]
            # Start discharge vid sista timmen i window
            start_discharge_idx = end_idx
            # Hämta SoC från sista charge-timmen i window (eller self.soc om tiden passerat)
            soc = self.schedule[start_discharge_idx][f"estimated_soc_window_{n}"] if start_discharge_idx < len(self.schedule) and f"estimated_soc_window_{n}" in self.schedule[start_discharge_idx] else self.soc or 0
            min_soc = self.min_battery_soc
            discharge_rate = self.discharge_rate
            soc_needed = max(soc - min_soc, 0)
            hours_needed = int((soc_needed + discharge_rate - 1) // discharge_rate)
            if hours_needed < 1:
                continue
            # "time discharge lookup" = hours_needed - 1
            lookup = max(0, hours_needed - 1)
            # Titta på timmarna runt sista window
            idxs = list(range(max(0, start_discharge_idx - lookup), min(len(self.price_data), start_discharge_idx + lookup + 1)))
            # Jämför priset på sista timmen i window med övriga
            prices = [(i, float(self.price_data[i]["value"])) for i in idxs]
            last_price = float(self.price_data[start_discharge_idx]["value"]) if start_discharge_idx < len(self.price_data) else 0
            max_price = max(prices, key=lambda x: x[1])[1] if prices else last_price
            # Om någon annan timme har högre pris, flytta window-slut till den timmen och upprepa
            if max_price > last_price:
                max_idx = max(prices, key=lambda x: x[1])[0]
                end_idx = max_idx
                start_discharge_idx = end_idx
                soc = self.schedule[start_discharge_idx][f"estimated_soc_window_{n}"] if start_discharge_idx < len(self.schedule) and f"estimated_soc_window_{n}" in self.schedule[start_discharge_idx] else self.soc or 0
                soc_needed = max(soc - min_soc, 0)
                hours_needed = int((soc_needed + discharge_rate - 1) // discharge_rate)
                if hours_needed < 1:
                    continue
                lookup = max(0, hours_needed - 1)
                idxs = list(range(max(0, start_discharge_idx - lookup), min(len(self.price_data), start_discharge_idx + lookup + 1)))
                prices = [(i, float(self.price_data[i]["value"])) for i in idxs]
            # Välj de timmar med högst pris, men endast om de uppnår min_profit
            avg_charge_price = window.get("avg_charge_price", 0)
            discharge_candidates = [(i, price) for i, price in prices if price >= avg_charge_price + min_profit]
            discharge_candidates.sort(key=lambda x: x[1], reverse=True)
            discharge_idxs = sorted([i for i, _ in discharge_candidates[:hours_needed]])
            # Markera i self.schedule
            current_soc = soc
            for i in range(len(self.price_data)):
                entry = self.price_data[i]
                in_window = i in discharge_idxs
                end_dt = datetime.fromisoformat(entry["end"])
                is_future = end_dt > now
                discharge = 1 if in_window and is_future and current_soc > min_soc else 0
                if discharge:
                    current_soc = max(current_soc - discharge_rate, min_soc)
                if i < len(self.schedule):
                    self.schedule[i][f"discharge_window_{n}"] = discharge
                    self.schedule[i][f"estimated_soc_discharge_window_{n}"] = round(current_soc, 2)
            # Sätt charge=0 för alla timmar som är tomma i window n efter discharge start
            if discharge_idxs:
                discharge_start_idx = discharge_idxs[0]
                for j in range(discharge_start_idx, len(self.schedule)):
                    if f"charge_window_{n}" in self.schedule[j]:
                        self.schedule[j][f"charge_window_{n}"] = 0
        return True

    async def async_set_charging(self, value: bool):
        self.charging_on = value
        # Optionally: Add logic to control hardware or call services
        _LOGGER.debug(f"Set charging_on to {value}")
        # Optionally: update state in Home Assistant

    async def async_set_discharging(self, value: bool):
        self.discharging_on = value
        # Optionally: Add logic to control hardware or call services
        _LOGGER.debug(f"Set discharging_on to {value}")
        # Optionally: update state in Home Assistant

    async def async_set_charge_rate(self, value: float):
        self.charge_rate = value
        _LOGGER.debug(f"Set charge_rate to {value}")
        # Optionally: Add logic to control hardware or call services

    async def async_set_self_usage(self, value: bool):
        self.self_usage_on = value
        _LOGGER.debug(f"Self usage set to {self.self_usage_on}")
        await self.async_update_sensors()

    async def async_toggle_self_usage(self):
        self.self_usage_on = not self.self_usage_on
        _LOGGER.debug(f"Self usage toggled to {self.self_usage_on}")
        await self.async_update_sensors()

    async def async_update_self_usage(self):
        """Uppdatera self usage state enligt automatik-villkor."""
        now = datetime.now()
        # Hämta entity ids
        battery_power_entity = self.config.get("battery_power_entity")
        solar_entity = self.config.get("solar_entity")
        consumption_entity = self.config.get("consumption_entity")
        # Hämta state
        battery_power = self.hass.states.get(battery_power_entity)
        solar = self.hass.states.get(solar_entity)
        consumption = self.hass.states.get(consumption_entity)
        try:
            battery_val = float(battery_power.state) if battery_power and battery_power.state not in (None, "", "unknown", "unavailable") else 0
        except Exception:
            battery_val = 0
        try:
            solar_val = float(solar.state) if solar and solar.state not in (None, "", "unknown", "unavailable") else 0
        except Exception:
            solar_val = 0
        try:
            consumption_val = float(consumption.state) if consumption and consumption.state not in (None, "", "unknown", "unavailable") else 0
        except Exception:
            consumption_val = 0
        # Hämta max batteri W från historik (7 dagar) om det behövs
        if not self._self_usage_max_battery_power or (self._self_usage_last_check is None or (now - self._self_usage_last_check).total_seconds() > 3600):
            try:
                history = await self.hass.helpers.history.get_significant_states(
                    now - timedelta(days=7),
                    now,
                    entity_ids=[battery_power_entity],
                    minimal_response=True
                )
                battery_w_values = []
                for state in history.get(battery_power_entity, []):
                    try:
                        val = float(state.state)
                        if val > 0:
                            battery_w_values.append(val)
                    except Exception:
                        continue
                if battery_w_values:
                    self._self_usage_max_battery_power = max(battery_w_values)
                self._self_usage_last_check = now
            except Exception:
                pass
        # Villkor
        cond1 = self._self_usage_max_battery_power and battery_val >= 0.75 * self._self_usage_max_battery_power
        cond2 = solar_val > consumption_val
        condition_met = cond1 or cond2
        # Hantera fördröjning
        if condition_met != self._self_usage_condition_met:
            self._self_usage_last_change = now
            self._self_usage_condition_met = condition_met
        if self._self_usage_last_change:
            elapsed = (now - self._self_usage_last_change).total_seconds()
            if self._self_usage_condition_met and not self.self_usage_on and elapsed >= self._self_usage_delay_seconds:
                self.self_usage_on = True
            elif not self._self_usage_condition_met and self.self_usage_on and elapsed >= self._self_usage_delay_seconds:
                self.self_usage_on = False

    __all__ = ["HomeBatteryOptimizerCoordinator"]