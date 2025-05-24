import logging
from datetime import datetime, timedelta
from .battery_optimizer import BatteryOptimizer

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
        self.optimizer = BatteryOptimizer(
            battery_capacity=self.max_battery_soc,
            charge_rate=self.charge_rate,
            discharge_rate=self.discharge_rate,
            price_analysis=None,  # Will be set below
            min_profit=self.min_profit,
            hass=hass
        )

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
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            if battery_state and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    soc = float(battery_state.state)
                except Exception:
                    soc = None
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
        return soc

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
                "window": f"window_{window_counter}",
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

    def generate_schedule(self, optimizer, soc, max_windows=3):
        # Only use available data and limit charge windows
        schedule = optimizer.generate_schedule(soc)
        schedule = self.limit_charge_windows(schedule, max_windows)
        # Identify charge windows (continuous charge blocks)
        base_time = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        formatted_schedule = []
        window_counter = 1
        current_window = None
        for i, item in enumerate(schedule):
            start_dt = base_time + timedelta(hours=i)
            end_dt = base_time + timedelta(hours=i+1)
            action = item.get("action", "idle")
            # Markera timmar som redan har passerat som 'past' och 'idle'
            if end_dt <= datetime.now():
                action = "idle"
                past = True
            else:
                past = False
            # Detect start of a new charge window
            if action == "charge" and (current_window is None or not current_window["active"]):
                current_window = {"active": True, "window": f"window_{window_counter}"}
                window_counter += 1
            elif action != "charge":
                current_window = {"active": False, "window": None}
            window_name = current_window["window"] if current_window and current_window["active"] else None
            formatted_schedule.append({
                "start": start_dt.isoformat(),
                "end": end_dt.isoformat(),
                "action": action,
                "price": item.get("price"),
                "soc": item.get("soc"),
                "past": past,
                "charge_switch_on": item.get("charge_switch_on"),
                "discharge_switch_on": item.get("discharge_switch_on"),
                "window": window_name
            })
        self.schedule = formatted_schedule
        # After schedule is built, find and label charge windows
        self.find_charge_windows()
        # Set window tag for every hour in each window range (not just charge hours)
        for w in self.charge_windows:
            for idx in range(w["start_idx"], w["end_idx"]+1):
                if idx < len(self.schedule):
                    self.schedule[idx]["window"] = w["window"]
        # Sätt action: 'idle' och window: None för timmar utanför alla charge windows
        window_indices = set()
        for w in self.charge_windows:
            window_indices.update(range(w["start_idx"], w["end_idx"]+1))
        for idx, item in enumerate(self.schedule):
            if idx not in window_indices:
                item["window"] = None
                item["action"] = "idle"
        return self.schedule

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

    async def async_toggle_self_usage(self):
        self.self_usage_on = not self.self_usage_on
        _LOGGER.debug(f"Self usage toggled to {self.self_usage_on}")
        # Här kan du lägga till logik för att påverka optimeringen

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
        self.update_soc()
        self.update_price_data()
        # Set price_analysis for optimizer
        self.optimizer.price_analysis = self
        # Generate schedule if SoC is available
        if self.soc is not None:
            self.generate_schedule(self.optimizer, self.soc, self.max_charge_windows)
        # Optionally: update charge/discharge periods
        self.find_charge_windows()
        self.build_charge_schedule_windows()  # <-- Lägg till denna rad
        self.build_discharge_schedule_windows()
        self.update_charge_discharge_periods()
        # Notify all listeners/entities
        if hasattr(self, 'async_update_listeners'):
            await self.async_update_listeners()
        # If entities are not using listeners, you may need to call async_write_ha_state on each
        # This can be handled by the entity base class if using DataUpdateCoordinator pattern

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
        Bygg laddschema för alla charge_windows (window 1, 2, 3, 4):
        - För varje window: utgå från estimated_soc efter föregående window (eller SoC för window 1)
        - Om det finns ett discharge window före, utgå från sista SoC i estimated_soc_discharge_windowN
        - Endast timmar i aktuellt window som inte redan använts i tidigare windows får användas
        - Skriv charge_raw_windowN och estimated_soc_windowN
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            for n in range(1, 5):
                setattr(self, f"charge_raw_window{n}", None)
                setattr(self, f"estimated_soc_window{n}", None)
            return []
        used_idxs = set()
        prev_soc = self.soc if self.soc is not None else 0
        for n, window in enumerate(self.charge_windows[:4], start=1):
            # Always use SoC after previous discharge window if it exists and is non-empty
            if n > 1:
                prev_discharge = getattr(self, f"estimated_soc_discharge_window{n-1}", None)
                prev_discharge_soc = None
                if prev_discharge and len(prev_discharge) > 0:
                    # Use the last SoC in the discharge window (should be after all discharge hours)
                    prev_discharge_soc = prev_discharge[-1]["soc"]
                if prev_discharge_soc is not None:
                    prev_soc = prev_discharge_soc
                else:
                    # Fallback: use last SoC from previous charge window
                    prev_charge = getattr(self, f"estimated_soc_window{n-1}", None)
                    if prev_charge and len(prev_charge) > 0:
                        prev_soc = prev_charge[-1]["soc"]
            start_idx = window["start_idx"]
            end_idx = window["end_idx"]
            max_soc = self.max_battery_soc
            charge_rate = self.charge_rate
            soc_needed = max(0, max_soc - prev_soc)
            hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
            if soc_needed < 5:
                hours_needed = 0
            # Endast tillåt timmar i detta window som INTE är i tidigare windows
            window_idxs = [i for i in range(start_idx, end_idx+1) if i not in used_idxs]
            window_prices = [(i, float(self.price_data[i]["value"])) for i in window_idxs]
            sorted_hours = sorted(window_prices, key=lambda x: x[1])
            charge_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
            charge_raw = []
            estimated_soc = []
            current_soc = prev_soc
            now = datetime.now()
            # For average charge price calculation
            charge_prices = []
            for i in range(len(self.price_data)):
                entry = self.price_data[i]
                in_window = i in window_idxs
                # end_dt = datetime.fromisoformat(entry["end"])
                # is_future = end_dt > now
                charge = 1 if i in charge_idxs and in_window else 0
                if current_soc >= max_soc - 5:
                    charge = 0
                if charge:
                    current_soc = min(current_soc + charge_rate, max_soc)
                    if in_window:
                        charge_prices.append(float(entry["value"]))
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
            setattr(self, f"charge_raw_window{n}", charge_raw)
            setattr(self, f"estimated_soc_window{n}", estimated_soc)
            # Calculate and store average charge price for this window
            avg_price = sum(charge_prices) / len(charge_prices) if charge_prices else None
            setattr(self, f"avg_charge_price_window{n}", avg_price)
            # För nästa window: utgå från sista SoC i estimated_soc (om ingen discharge)
            for entry in reversed(estimated_soc):
                end_dt = datetime.fromisoformat(entry["end"])
                if end_dt <= now:
                    prev_soc = entry["soc"]
                    break
            else:
                prev_soc = estimated_soc[end_idx]["soc"]
            used_idxs.update(window_idxs)
        return True

    def get_soc_for_index(self, estimated_soc, idx):
        """Hämta SoC för en viss index från estimated_soc-listan."""
        if not estimated_soc or idx < 0 or idx >= len(estimated_soc):
            return None
        return estimated_soc[idx]["soc"]

    def build_discharge_schedule_windows(self):
        """
        Förbättrad urladdningslogik:
        - Discharge kan börja i slutet av charge window och gå bakåt/framåt kring sista timmen.
        - Samla t.ex. 2 timmar före och 2 timmar efter sista timmen (totalt 5 timmar).
        - Sortera dessa på pris, välj de högsta (så många som SoC/discharge_rate tillåter).
        - Om någon av dessa timmar har högre pris än starttimmen, flytta start till den timmen och upprepa.
        - När discharge planeras på en timme i charge window, sätt charge=0 från och med den timmen och framåt i window.
        - estimated_soc och sensorer uppdateras korrekt.
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            for n in range(1, 5):
                setattr(self, f"discharge_raw_window{n}", None)
                setattr(self, f"estimated_soc_discharge_window{n}", None)
            return []
        now = datetime.now()
        min_profit = getattr(self, "min_profit", 10)
        deadband = 5  # Always keep at least this much above min_battery_soc
        num_windows = len(self.charge_windows)
        for n in range(1, num_windows + 1):
            prev_charge = getattr(self, f"estimated_soc_window{n}", None)
            prev_window = self.charge_windows[n-1]
            start_idx = prev_window["start_idx"]
            end_idx = prev_window["end_idx"]
            # 1. Utgångspunkt: sista timmen i window
            start_discharge_idx = end_idx
            # 2. Samla 2 timmar före och 2 timmar efter (totalt 5 timmar)
            idxs = list(range(max(0, start_discharge_idx-2), min(len(self.price_data), start_discharge_idx+3)))
            # 3. Sortera dessa på pris (fallande)
            price_candidates = [(i, float(self.price_data[i]["value"])) for i in idxs]
            price_candidates.sort(key=lambda x: x[1], reverse=True)
            # 4. Välj så många timmar som batteriet klarar
            avg_charge_price = getattr(self, f"avg_charge_price_window{n}", None)
            if avg_charge_price is None:
                avg_charge_price = 0
            min_soc = self.min_battery_soc
            discharge_rate = self.discharge_rate
            # Always use SoC at candidate start time
            soc = self.get_soc_for_index(prev_charge, start_discharge_idx-1) or self.soc or 0
            soc_limit = min_soc  # FIX: allow discharge to true min_soc, not min_soc + deadband
            soc_needed = max(soc - soc_limit, 0)
            hours_possible = int((soc_needed + discharge_rate - 1) // discharge_rate)
            # 5. Filtrera på min_profit
            discharge_candidates = [i for i, price in price_candidates if price >= avg_charge_price + min_profit]
            # 6. Ta högsta timmarna, max så många som batteriet klarar
            discharge_idxs = sorted(discharge_candidates[:hours_possible])
            # 7. Om någon av dessa timmar har högre pris än starttimmen, flytta start till den timmen och upprepa
            if discharge_idxs:
                start_price = float(self.price_data[start_discharge_idx]["value"])
                max_price_idx = max(discharge_idxs, key=lambda i: float(self.price_data[i]["value"]))
                if float(self.price_data[max_price_idx]["value"]) > start_price and max_price_idx != start_discharge_idx:
                    # Flytta start till max_price_idx och kör om logiken
                    start_discharge_idx = max_price_idx
                    # Recalculate SoC at new candidate start
                    soc = self.get_soc_for_index(prev_charge, start_discharge_idx-1) or self.soc or 0
                    soc_needed = max(soc - soc_limit, 0)
                    hours_possible = int((soc_needed + discharge_rate - 1) // discharge_rate)
                    idxs = list(range(max(0, start_discharge_idx-2), min(len(self.price_data), start_discharge_idx+3)))
                    price_candidates = [(i, float(self.price_data[i]["value"])) for i in idxs]
                    price_candidates.sort(key=lambda x: x[1], reverse=True)
                    discharge_candidates = [i for i, price in price_candidates if price >= avg_charge_price + min_profit]
                    discharge_idxs = sorted(discharge_candidates[:hours_possible])
            # Om ingen timme uppfyller min_profit, ingen urladdning
            if not discharge_idxs:
                setattr(self, f"discharge_raw_window{n}", None)
                setattr(self, f"estimated_soc_discharge_window{n}", None)
                continue
            # Bygg discharge_raw och estimated_soc
            discharge_raw = []
            estimated_soc = []
            current_soc = soc
            # DEBUG: Log discharge window selection
            _LOGGER.debug(f"Discharge window {n}: soc={soc}, soc_limit={soc_limit}, soc_needed={soc_needed}, hours_possible={hours_possible}, discharge_idxs={discharge_idxs}")
            for i in range(len(self.price_data)):
                entry = self.price_data[i]
                in_window = i in discharge_idxs
                end_dt = datetime.fromisoformat(entry["end"])
                is_future = end_dt > now
                # Only discharge if above min_battery_soc
                discharge = 1 if in_window and is_future and current_soc > soc_limit else 0
                if discharge:
                    _LOGGER.debug(f"Discharge hour: i={i}, current_soc before={current_soc}, after={max(current_soc - discharge_rate, soc_limit)}")
                    current_soc = max(current_soc - discharge_rate, soc_limit)
                discharge_raw.append({
                    "start": entry["start"],
                    "end": entry["end"],
                    "discharge": discharge
                })
                estimated_soc.append({
                    "start": entry["start"],
                    "end": entry["end"],
                    "soc": round(current_soc, 2)
                })
            setattr(self, f"discharge_raw_window{n}", discharge_raw)
            setattr(self, f"estimated_soc_discharge_window{n}", estimated_soc)
            # Begränsa charge window så att charge=0 från och med första discharge-timmen
            charge_raw = getattr(self, f"charge_raw_window{n}", None)
            if charge_raw:
                discharge_start_idx = discharge_idxs[0] if discharge_idxs else None
                if discharge_start_idx is not None:
                    for j in range(discharge_start_idx, len(charge_raw)):
                        charge_raw[j]["charge"] = 0
                setattr(self, f"charge_raw_window{n}", charge_raw)
        return True
