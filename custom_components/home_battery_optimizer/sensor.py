from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from homeassistant.helpers.entity import EntityDescription
from .entity import HBOEntity
import logging
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

# Endast schedule-sensorn ska finnas kvar
SENSOR_DESCRIPTIONS = [
    EntityDescription(key="schedule", name="Battery Schedule"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        BatteryOptimizerSensor(coordinator, entry, SENSOR_DESCRIPTIONS[0])
    ]
    async_add_entities(sensors)

class BatteryOptimizerSensor(HBOEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, description):
        super().__init__(coordinator, config_entry, description)
        self._key = description.key
        self._name = description.name
        # Ta bort referens till description efter att nyckel och namn har extraherats
        if hasattr(self, 'entity_description'):
            del self.entity_description

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        # Endast schedule-sensorn
        coordinator = self.coordinator
        def format_state(s):
            return " ".join([w.capitalize() for w in s.split(" ")])
        if coordinator.charging_on:
            return format_state("charging")
        if coordinator.discharging_on:
            return format_state("discharging")
        if getattr(coordinator, "self_usage_on", False):
            return format_state("self usage")
        now = coordinator.hass.now() if hasattr(coordinator.hass, 'now') else datetime.now()
        next_charge = None
        next_discharge = None
        for n in range(1, 5):
            charge_raw = getattr(coordinator, f"charge_raw_window{n}", None) or []
            for entry in charge_raw:
                end_val = entry.get("end")
                if not end_val:
                    continue
                try:
                    end_dt = datetime.fromisoformat(end_val)
                except Exception:
                    continue
                if end_dt > now and entry.get("charge", 0) == 1:
                    if not next_charge or end_dt < next_charge:
                        next_charge = end_dt
        for n in range(1, 5):
            discharge_raw = getattr(coordinator, f"discharge_raw_window{n}", None) or []
            for entry in discharge_raw:
                end_val = entry.get("end")
                if not end_val:
                    continue
                try:
                    end_dt = datetime.fromisoformat(end_val)
                except Exception:
                    continue
                if end_dt > now and entry.get("discharge", 0) == 1:
                    if not next_discharge or end_dt < next_discharge:
                        next_discharge = end_dt
        if next_charge and (not next_discharge or next_charge <= next_discharge):
            return format_state(f"waiting for charge {next_charge.strftime('%H:%M')}")
        if next_discharge:
            return format_state(f"waiting for discharge {next_discharge.strftime('%H:%M')}")
        if not coordinator.schedule:
            return format_state("no schedule")
        if coordinator.soc is None:
            return format_state("unknown")
        return format_state("idle")

    @property
    def extra_state_attributes(self):
        # Endast schedule-sensorns attribut
        coordinator = self.coordinator
        charge_windows = []
        for w in getattr(coordinator, "charge_windows", []) or []:
            charge_windows.append({
                "window": w.get("window"),
                "start": w.get("start"),
                "end": w.get("end"),
                "min_price": w.get("min_price"),
                "max_price": w.get("max_price")
            })
        schedule = coordinator.schedule or []
        data = []
        for entry in schedule:
            # Sätt charge=1 om SoC ökar denna timme jämfört med förra
            prev_soc = None
            if data:
                prev_soc = data[-1]["soc"]
            else:
                prev_soc = entry.get("soc")
            curr_soc = entry.get("soc")
            charge = 1 if prev_soc is not None and curr_soc is not None and curr_soc > prev_soc else 0
            discharge = 1 if prev_soc is not None and curr_soc is not None and curr_soc < prev_soc else 0
            data.append({
                "start": entry.get("start"),
                "end": entry.get("end"),
                "action": entry.get("action"),
                "price": entry.get("price"),
                "soc": curr_soc,
                "charge": charge,
                "discharge": discharge,
                "window": entry.get("window")
            })
        return {
            "status": self.state,
            "soc": coordinator.soc,
            "target_soc": coordinator.target_soc,
            "current_power": coordinator.current_power,
            "charge_windows": charge_windows,
            "data": data
        }