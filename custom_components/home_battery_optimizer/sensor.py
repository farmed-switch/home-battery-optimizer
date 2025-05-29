from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .entity import HBOEntity
from datetime import datetime
import logging

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HBOScheduleSensor(coordinator, entry)])

class HBOScheduleSensor(HBOEntity, SensorEntity):
    def __init__(self, coordinator, config_entry):
        HBOEntity.__init__(self, coordinator, config_entry, description=None)
        SensorEntity.__init__(self)
        self._attr_name = "Battery Schedule"
        self._attr_unique_id = f"{config_entry.entry_id}_schedule"

    @property
    def state(self):
        # Status, t.ex. "idle (2), SoC: 100.0%"
        soc = self.coordinator.soc if hasattr(self.coordinator, 'soc') else None
        status = self._get_status()
        if soc is not None:
            return f"{status}, SoC: {soc}%"
        return status

    def _get_status(self):
        # Returnera nuvarande action och window
        schedule = getattr(self.coordinator, 'schedule', [])
        now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
        for entry in schedule:
            start = entry.get("start")
            end = entry.get("end")
            window = entry.get("window")
            if start and end:
                try:
                    start_dt = datetime.fromisoformat(start)
                    end_dt = datetime.fromisoformat(end)
                    if start_dt <= now < end_dt:
                        action = entry.get("action", "idle")
                        return f"{action} ({window})"
                except Exception:
                    continue
        return "idle"

    @property
    def extra_state_attributes(self):
        # Soc, Target soc, Current power
        attrs = {}
        attrs["soc"] = self.coordinator.soc if hasattr(self.coordinator, 'soc') else None
        attrs["target_soc"] = getattr(self.coordinator, 'target_soc', 'Unknown')
        attrs["current_power"] = getattr(self.coordinator, 'current_power', None)
        # Charge windows
        attrs["charge_windows"] = self._get_charge_windows()
        # Data (timrad tabell)
        attrs["data"] = self._get_data_table()
        return attrs

    def _get_charge_windows(self):
        # Bygg lista av windows med start, end, min_price, max_price
        windows = []
        schedule = getattr(self.coordinator, 'schedule', [])
        for entry in schedule:
            window = entry.get("window")
            if window is not None:
                # Finns redan denna window?
                found = next((w for w in windows if w["window"] == window), None)
                if not found:
                    # Hitta alla entries för detta window
                    window_entries = [e for e in schedule if e.get("window") == window]
                    if window_entries:
                        start = window_entries[0].get("start")
                        end = window_entries[-1].get("end")
                        prices = [e.get("price") for e in window_entries if e.get("price") is not None]
                        min_price = min(prices) if prices else None
                        max_price = max(prices) if prices else None
                        windows.append({
                            "window": window,
                            "start": start,
                            "end": end,
                            "min_price": min_price,
                            "max_price": max_price
                        })
        return windows

    def _get_data_table(self):
        # Bygg lista av alla schedule-rader med önskade fält
        schedule = getattr(self.coordinator, 'schedule', [])
        data = []
        for entry in schedule:
            data.append({
                "start": entry.get("start"),
                "end": entry.get("end"),
                "action": entry.get("action"),
                "price": entry.get("price"),
                "soc": entry.get("soc"),
                "charge": entry.get("charge"),
                "discharge": entry.get("discharge"),
                "window": entry.get("window")
            })
        return data