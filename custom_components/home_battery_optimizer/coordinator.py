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
        self.full_schedule = []  # Initiera alltid så den finns
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
        _LOGGER.debug(f"update_soc: battery_entity_id = {battery_entity_id}")
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            _LOGGER.debug(f"update_soc: battery_state = {battery_state.state if battery_state else None}")
            if battery_state and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    soc = float(battery_state.state)
                except Exception:
                    soc = None
        self.soc = soc
        _LOGGER.debug(f"update_soc: self.soc sätts till {self.soc}")
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
        elif not self.charging_on and not self.discharging_on and self.soc is not None:
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
        Ny logik: Hitta windows som sträcker sig från första charge-timmen (innan peak) till sista discharge-timmen (efter peak).
        Charge sker på billigaste timmarna innan peak, discharge på dyraste timmarna efter peak. Window stängs direkt efter sista discharge.
        """
        price_data = self.price_data or []
        min_profit = getattr(self, "min_profit", 10)
        windows = []
        n = len(price_data)
        i = 0
        window_counter = 1
        charge_hours_per_window = 3  # Kan göras konfigurerbart
        discharge_hours_per_window = 3
        while i < n - (charge_hours_per_window + discharge_hours_per_window):
            # 1. Leta peak (lokal max)
            peak_idx = i + charge_hours_per_window
            peak_price = price_data[peak_idx]["value"]
            for j in range(i + charge_hours_per_window, n - discharge_hours_per_window):
                if price_data[j]["value"] > peak_price:
                    peak_idx = j
                    peak_price = price_data[j]["value"]
            # 2. Välj X timmar innan peak för charge (sortera på lägsta pris)
            before_idxs = list(range(max(0, peak_idx - charge_hours_per_window), peak_idx))
            before_prices = [(idx, price_data[idx]["value"]) for idx in before_idxs]
            charge_idxs = sorted(before_prices, key=lambda x: x[1])[:charge_hours_per_window]
            charge_idxs = sorted([idx for idx, _ in charge_idxs])
            # 3. Välj X timmar efter peak för discharge (sortera på högsta pris)
            after_idxs = list(range(peak_idx + 1, min(n, peak_idx + 1 + discharge_hours_per_window)))
            after_prices = [(idx, price_data[idx]["value"]) for idx in after_idxs]
            discharge_idxs = sorted(after_prices, key=lambda x: x[1], reverse=True)[:discharge_hours_per_window]
            discharge_idxs = sorted([idx for idx, _ in discharge_idxs])
            # 4. Window sträcker sig från första charge till sista discharge
            if not charge_idxs or not discharge_idxs:
                break
            window_start = charge_idxs[0]
            window_end = discharge_idxs[-1]
            window = {
                "window": f"window_{window_counter}",
                "start": price_data[window_start]["start"],
                "end": price_data[window_end]["end"],
                "min_price": min([price_data[idx]["value"] for idx in charge_idxs]),
                "max_price": max([price_data[idx]["value"] for idx in discharge_idxs]),
                "start_idx": window_start,
                "end_idx": window_end,
                "charge_idxs": charge_idxs,
                "discharge_idxs": discharge_idxs,
                "peak_idx": peak_idx
            }
            windows.append(window)
            window_counter += 1
            i = window_end + 1  # Nästa window börjar efter detta
        self.charge_windows = windows
        _LOGGER.debug(f"find_charge_windows: windows={windows}")
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
        battery_entity_id = self.config.get("battery_entity")
        solar_entity = self.config.get("solar_entity")
        consumption_entity = self.config.get("consumption_entity")
        max_charge_entity = self.config.get("charge_percentage_entity") or self.config.get("max_charge_entity")
        # Hämta state
        soc = None
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            if battery_state and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    soc = float(battery_state.state)
                except Exception:
                    soc = None
        solar = self.hass.states.get(solar_entity)
        consumption = self.hass.states.get(consumption_entity)
        try:
            solar_val = float(solar.state) if solar and solar.state not in (None, "", "unknown", "unavailable") else 0
        except Exception:
            solar_val = 0
        try:
            consumption_val = float(consumption.state) if consumption and consumption.state not in (None, "", "unknown", "unavailable") else 0
        except Exception:
            consumption_val = 0
        # Hämta max charge från number-entity
        max_charge = 100
        if max_charge_entity:
            max_charge_state = self.hass.states.get(max_charge_entity)
            try:
                max_charge = float(max_charge_state.state) if max_charge_state and max_charge_state.state not in (None, "", "unknown", "unavailable") else 100
            except Exception:
                max_charge = 100
        # Kontrollera om charge eller discharge är aktiv
        charge_active = self.charging_on
        discharge_active = self.discharging_on
        # Self usage får INTE vara på om varken charge eller discharge är aktiv
        if not charge_active and not discharge_active:
            self.self_usage_on = False
            return
        # Self usage får INTE vara på om charge är aktiv
        if charge_active:
            self.self_usage_on = False
            return
        # Steg 1: Om solproduktion > 100W i >1 minut och SoC < 90% av max_charge
        soc_ok = soc is not None and soc < 0.9 * max_charge
        solar_ok = solar_val > 100
        if solar_ok and soc_ok:
            if not hasattr(self, '_self_usage_solar_start') or self._self_usage_solar_start is None:
                self._self_usage_solar_start = now
            elif (now - self._self_usage_solar_start).total_seconds() >= 60:
                self.self_usage_on = True
                return
        else:
            self._self_usage_solar_start = None
        # Steg 2: Om SoC >= 90% av max_charge och solproduktion > konsumtion i >1 minut
        soc_full = soc is not None and soc >= 0.9 * max_charge
        solar_gt_consumption = solar_val > consumption_val
        if soc_full and solar_gt_consumption:
            if not hasattr(self, '_self_usage_solar_gt_consumption_start') or self._self_usage_solar_gt_consumption_start is None:
                self._self_usage_solar_gt_consumption_start = now
            elif (now - self._self_usage_solar_gt_consumption_start).total_seconds() >= 60:
                self.self_usage_on = True
                return
        else:
            self._self_usage_solar_gt_consumption_start = None
        # Om inget villkor är uppfyllt, stäng av self usage
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
        _LOGGER.debug(f"async_update_sensors: self.soc efter update_soc = {self.soc}")
        self.update_price_data()
        # Set price_analysis for optimizer
        self.optimizer.price_analysis = self
        # Generate schedule if SoC is available
        if self.soc is not None:
            self.find_charge_windows()  # SÄKERSTÄLL att charge_windows alltid är aktuell
            _LOGGER.debug(f"async_update_sensors: self.soc innan build_full_schedule = {self.soc}")
            self.build_full_schedule()
        # Notify all listeners/entities
        if hasattr(self, 'async_update_listeners'):
            await self.async_update_listeners()
        # If entities are not using listeners, you may need to call async_write_ha_state on each
        # This can be handled by the entity base class if using DataUpdateCoordinator pattern
        # Uppdatera self usage-status varje gång sensorer uppdateras
        await self.async_update_self_usage()

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

    def build_full_schedule(self):
        """
        Bygg EN central lista (self.full_schedule) med alla timmar och attribut:
        - charge, discharge, soc, price, start, end
        - charge=0 om discharge=1
        - soc beräknas sekventiellt
        """
        if not self.price_data or not hasattr(self, "charge_windows") or not self.charge_windows:
            _LOGGER.warning(f"build_full_schedule: Ingen price_data eller inga charge_windows! price_data={self.price_data}, charge_windows={getattr(self, 'charge_windows', None)}")
            self.full_schedule = []
            return []
        n = len(self.price_data)
        # Initiera listan
        schedule = []
        soc = self.soc if self.soc is not None else 0
        max_soc = self.max_battery_soc
        min_soc = self.min_battery_soc
        charge_rate = self.charge_rate
        discharge_rate = self.discharge_rate
        # NY LOGIK: Använd charge_idxs och discharge_idxs från varje window
        charge_hours = set()
        discharge_hours = set()
        if hasattr(self, "charge_windows"):
            for w in self.charge_windows:
                charge_hours.update(w.get("charge_idxs", []))
                discharge_hours.update(w.get("discharge_idxs", []))
        _LOGGER.debug(f"build_full_schedule: soc={soc}, max_soc={max_soc}, min_soc={min_soc}, charge_rate={charge_rate}, discharge_rate={discharge_rate}")
        # NY LOGIK: sekventiell SoC mellan ALLA fönster (charge/discharge)
        current_soc = soc
        # Hitta discharge-fönster (pris-toppar)
        discharge_windows = []
        price_data = self.price_data or []
        n = len(price_data)
        i = 0
        window_counter = 1
        while i < n - 1:
            # 1. Hitta första stigande sekvens (lokal max)
            start_idx = i
            ref_idx = i
            ref_price = price_data[i]["value"]
            while i + 1 < n and price_data[i+1]["value"] > ref_price:
                i += 1
                ref_price = price_data[i]["value"]
                ref_idx = i
            max_idx = ref_idx
            max_price = ref_price
            # 2. Leta efter prisfall som är minst min_profit
            found = False
            j = max_idx + 1
            while j < n:
                if price_data[j]["value"] <= max_price - self.min_profit:
                    found = True
                    break
                if price_data[j]["value"] > max_price:
                    max_price = price_data[j]["value"]
                    max_idx = j
                j += 1
            if not found:
                break
            # 3. Hitta botten efter tröskel
            min_idx = j
            min_price = price_data[j]["value"]
            k = j + 1
            while k < n and price_data[k]["value"] < min_price:
                min_idx = k
                min_price = price_data[k]["value"]
                k += 1
            # 4. Spara window ENDAST om min_profit uppfylls
            if max_price - min_price >= self.min_profit:
                window = {
                    "window": f"discharge_{window_counter}",
                    "start": price_data[start_idx]["start"],
                    "end": price_data[min_idx]["end"],
                    "max_price": max_price,
                    "min_price": min_price,
                    "start_idx": start_idx,
                    "end_idx": min_idx
                }
                discharge_windows.append(window)
                window_counter += 1
            i = min_idx + 1
        # Bygg window_list med både charge och discharge
        window_list = [("charge", w) for w in self.charge_windows[:4]] + [("discharge", w) for w in discharge_windows[:4]]
        window_list.sort(key=lambda w: w[1]["start_idx"])
        # Sekventiell SoC och hoppa fönster där SoC inte räcker
        current_soc = soc
        for win_type, window in window_list:
            start_idx = window["start_idx"]
            end_idx = window["end_idx"]
            window_idxs = list(range(start_idx, end_idx+1))
            window_prices = [(i, float(self.price_data[i]["value"])) for i in window_idxs]
            if win_type == "charge":
                if current_soc >= max_soc - 5:
                    _LOGGER.debug(f"Hoppar charge-window pga SoC redan full: {current_soc}")
                    continue
                soc_needed = max(0, max_soc - current_soc)
                hours_needed = int((soc_needed + charge_rate - 1) // charge_rate)
                if soc_needed < 5:
                    hours_needed = 0
                sorted_hours = sorted(window_prices, key=lambda x: x[1])
                ch_idxs = sorted([i for i, _ in sorted_hours[:hours_needed]])
                _LOGGER.debug(f"build_full_schedule: window {win_type}, start_idx={start_idx}, end_idx={end_idx}, soc_needed={soc_needed}, hours_needed={hours_needed}, ch_idxs={ch_idxs}, current_soc={current_soc}")
                charge_hours.update(ch_idxs)
                current_soc = min(current_soc + charge_rate * len(ch_idxs), max_soc)
            elif win_type == "discharge":
                # Tillåt discharge i sitt fönster om SoC > min_soc, oavsett källa
                soc_available = max(current_soc - min_soc, 0)
                hours_possible = int((soc_available + discharge_rate - 1) // discharge_rate)
                if soc_available < 5:
                    hours_possible = 0
                sorted_hours = sorted(window_prices, key=lambda x: x[1], reverse=True)
                discharge_idxs = sorted([i for i, _ in sorted_hours[:hours_possible]])
                _LOGGER.debug(f"build_full_schedule: window {win_type}, start_idx={start_idx}, end_idx={end_idx}, soc_available={soc_available}, hours_possible={hours_possible}, discharge_idxs={discharge_idxs}, current_soc={current_soc}")
                discharge_hours.update(discharge_idxs)
                current_soc = max(current_soc - discharge_rate * len(discharge_idxs), min_soc)
        current_soc = soc
        # Hitta index för aktuell timme
        now = datetime.now()
        soc_index = None
        for idx, entry in enumerate(self.price_data):
            start_dt = datetime.fromisoformat(entry["start"])
            end_dt = datetime.fromisoformat(entry["end"])
            if start_dt <= now < end_dt:
                soc_index = idx
                break
        if soc_index is None:
            soc_index = 0  # fallback om ingen match
        # Bygg schemat
        current_soc = None
        for i, entry in enumerate(self.price_data):
            if i < soc_index:
                soc_start = None
            elif i == soc_index:
                soc_start = soc if soc is not None else 0
                current_soc = soc_start
            else:
                soc_start = current_soc
            # Charge/discharge baseras alltid på estimerad SoC
            charge = 1 if i in charge_hours and i not in discharge_hours and (soc_start is not None and soc_start < max_soc - 5) else 0
            discharge = 1 if i in discharge_hours and (soc_start is not None and soc_start > min_soc) else 0
            if discharge:
                charge = 0
            # Uppdatera estimerad SoC sekventiellt
            if soc_start is None:
                current_soc = None
            elif charge:
                current_soc = min(soc_start + charge_rate, max_soc)
            elif discharge:
                current_soc = max(soc_start - discharge_rate, min_soc)
            else:
                current_soc = soc_start
            schedule.append({
                "start": entry["start"],
                "end": entry["end"],
                "value": entry["value"],
                "charge": charge,
                "discharge": discharge,
                "soc": round(current_soc, 2) if current_soc is not None else None,
                "soc_start": round(soc_start, 2) if soc_start is not None else ""
            })
        _LOGGER.debug(f"build_full_schedule: Resultat schedule: {schedule}")
        self.full_schedule = schedule
        self.log_full_schedule_table()  # Logga tabellen direkt efter schemat byggts
        self.notify_full_schedule_table()  # Skicka tabellen som notis
        self.notify_charge_windows_debug()  # Skicka debug-info om charge windows
        return schedule

    def get_soc_for_index(self, estimated_soc, idx):
        """Hämta SoC för en viss index från estimated_soc-listan."""
        if not estimated_soc or idx < 0 or idx >= len(estimated_soc):
            return None
        return estimated_soc[idx]["soc"]

    def build_discharge_schedule_windows(self):
        """
        Deprecated: All discharge/charge/soc logic is now handled by build_full_schedule and full_schedule.
        This method is no longer used and should not be called.
        """
        return True

    def log_full_schedule_table(self):
        """
        Loggar en tabell med tid, value, charge, discharge, estimated soc (A-E).
        Kolumner:
        A: Tid (start)
        B: Value (pris)
        C: Charge (0/1)
        D: Discharge (0/1)
        E: Estimated SoC
        """
        if not self.full_schedule:
            _LOGGER.info("full_schedule är tom!")
            return
        header = f"{'A: Tid':<20} {'B: Value':<10} {'C: Charge':<8} {'D: Discharge':<10} {'E: Estimated SoC':<15}"
        _LOGGER.info("\n" + header)
        _LOGGER.info("-" * len(header))
        for row in self.full_schedule:
            tid = row.get("start", "")[:16].replace("T", " ")
            value = f"{row.get('value', ''):.2f}"
            charge = row.get("charge", "")
            discharge = row.get("discharge", "")
            soc = row.get("soc", "")
            _LOGGER.info(f"{tid:<20} {value:<10} {charge!s:<8} {discharge!s:<10} {soc!s:<15}")

    def notify_full_schedule_table(self):
        """
        Skickar en persistent notification med en tydlig markdown-tabell (A-E) till Home Assistant.
        Lägger även till debug-info om SoC, entity-id och state högst upp i notifikationen.
        """
        # Hämta debug-info
        battery_entity_id = self.config.get("battery_entity")
        battery_state = self.hass.states.get(battery_entity_id) if battery_entity_id else None
        soc_state = battery_state.state if battery_state else None
        soc_used = self.soc
        debug_header = (
            f"**Debug-info:**  "
            f"Entity: `{battery_entity_id}`  "
            f"State: `{soc_state}`  "
            f"SoC som används i schema: `{soc_used}`  \n\n"
        )
        if not self.full_schedule:
            message = debug_header + "full_schedule är tom!"
        else:
            # Bygg en markdown-tabell
            header = "| Tid | Pris | Ladda | Urladda | SoC (före åtgärd) |\n|------|------|-------|---------|--------------------|\n"
            rows = []
            for row in self.full_schedule:
                tid = row.get("start", "")[:16].replace("T", " ")
                value = f"{row.get('value', ''):.2f}"
                charge = row.get("charge", "")
                discharge = row.get("discharge", "")
                soc_start = row.get("soc_start", "")
                rows.append(f"| {tid} | {value} | {charge} | {discharge} | {soc_start} |")
            message = debug_header + header + "\n".join(rows)
        # Skicka notis via Home Assistant
        try:
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": "Home Battery Optimizer Schema", "message": message},
                )
            )
        except Exception as e:
            _LOGGER.error(f"Kunde inte skicka notifikation: {e}")

    def notify_charge_windows_debug(self):
        """
        Skickar en persistent notification med debug-info om hittade charge windows och varför fönster eventuellt inte hittas.
        """
        price_data = self.price_data or []
        min_profit = getattr(self, "min_profit", 10)
        message = f"min_profit: {min_profit}\n"
        if not price_data:
            message += "Ingen price_data tillgänglig."
        elif not hasattr(self, "charge_windows") or not self.charge_windows:
            message += "Inga charge_windows hittades!\n"
        else:
            message += f"Antal charge_windows: {len(self.charge_windows)}\n"
            for i, w in enumerate(self.charge_windows, 1):
                message += f"Fönster {i}: {w['start']} - {w['end']} (min: {w['min_price']}, max: {w['max_price']})\n"
        # Lägg till prisdata för insyn
        message += "\nPris per timme:\n"
        for i, p in enumerate(price_data):
            message += f"{i}: {p['start'][:16].replace('T',' ')} pris={p['value']}\n"
        # Skicka notis via Home Assistant
        try:
            self.hass.async_create_task(
                self.hass.services.async_call(
                    "persistent_notification",
                    "create",
                    {"title": "HBO Debug: Charge Windows", "message": message},
                )
            )
        except Exception as e:
            _LOGGER.error(f"Kunde inte skicka debug-notifikation: {e}")
