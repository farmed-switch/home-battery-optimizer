from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from homeassistant.helpers.entity import EntityDescription
from .entity import HBOEntity
import logging
from datetime import datetime

_LOGGER = logging.getLogger(__name__)

# Define entity descriptions for all sensors
SENSOR_DESCRIPTIONS = [
    EntityDescription(key="soc", name="Batteri SoC"),
    EntityDescription(key="estimated_soc", name="Estimated SoC"),
    EntityDescription(key="power", name="Batteri Effekt"),
    EntityDescription(key="target_soc", name="Mål SoC"),
    EntityDescription(key="status", name="Batteristatus"),
    EntityDescription(key="schedule", name="Battery Schedule"),
    EntityDescription(key="price_raw", name="Battery Price (raw_two_days)"),
    EntityDescription(key="window_raw", name="Battery Window (raw_two_days)"),
    EntityDescription(key="charge_raw", name="Battery Charge (raw_two_days)"),
    EntityDescription(key="discharge_raw", name="Battery Discharge (raw_two_days)"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    sensors = [
        BatteryOptimizerSensor(coordinator, entry, description)
        for description in SENSOR_DESCRIPTIONS
    ]
    async_add_entities(sensors)

class BatteryOptimizerSensor(HBOEntity, SensorEntity):
    def __init__(self, coordinator, config_entry, description):
        super().__init__(coordinator, config_entry, description)
        self._key = description.key
        self._name = description.name
        # Remove reference to description after extracting key and name
        if hasattr(self, 'entity_description'):
            del self.entity_description

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        key = self._key
        if key == "soc":
            return self.coordinator.soc
        if key == "estimated_soc":
            # Returnera None eller logik för uppskattad SoC per timme
            return None
        if key == "power":
            return getattr(self.coordinator, "current_power", None)
        if key == "target_soc":
            return getattr(self.coordinator, "target_soc", None)
        if key == "status":
            return getattr(self.coordinator, "status", None)
        if key == "schedule":
            schedule = self.coordinator.schedule or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else None
            for entry in schedule:
                start_dt = entry.get("start")
                end_dt = entry.get("end")
                if start_dt and end_dt and now:
                    try:
                        from datetime import datetime
                        start_dt = datetime.fromisoformat(start_dt)
                        end_dt = datetime.fromisoformat(end_dt)
                        if start_dt <= now < end_dt:
                            return entry.get("action", "idle")
                    except Exception:
                        continue
            return "idle"
        return None

    @property
    def extra_state_attributes(self):
        key = self._key
        if key == "soc":
            return {"unit_of_measurement": "%", "source": self.coordinator.config.get("battery_entity")}
        if key == "power":
            return {"unit_of_measurement": "W", "source": self.coordinator.config.get("battery_power_entity")}
        if key == "target_soc":
            return {"unit_of_measurement": "%", "source": self.coordinator.config.get("target_soc_entity")}
        if key == "status":
            return {"charging_on": self.coordinator.charging_on, "discharging_on": self.coordinator.discharging_on}
        if key == "schedule":
            return {
                "schedule": self.coordinator.schedule,
                "raw_two_days": self.coordinator.price_data,
            }
        elif key == "price_raw":
            price_data = self.coordinator.price_data or []
            return {
                "raw_two_days": [
                    {
                        "start": entry.get("start"),
                        "end": entry.get("end"),
                        "value": entry.get("value")
                    }
                    for entry in price_data
                ]
            }
        elif key == "window_raw":
            # Visa alltid start, end, window även om window är None
            schedule = self.coordinator.schedule or []
            if not schedule:
                # Fallback: visa price_data med window=None
                price_data = self.coordinator.price_data or []
                return {
                    "raw_two_days": [
                        {
                            "start": entry.get("start"),
                            "end": entry.get("end"),
                            "window": None
                        }
                        for entry in price_data
                    ]
                }
            return {
                "raw_two_days": [
                    {
                        "start": entry.get("start"),
                        "end": entry.get("end"),
                        "window": entry.get("window") if "window" in entry else None
                    }
                    for entry in schedule
                ]
            }
        elif key == "charge_raw":
            # Visa window 1-4 om de finns
            result = []
            for n in range(1, 5):
                charge_raw = getattr(self.coordinator, f"charge_raw_window{n}", None)
                avg_price = getattr(self.coordinator, f"avg_charge_price_window{n}", None)
                if charge_raw:
                    result.append({"window": n, "raw_two_days": charge_raw, "avg_charge_price": avg_price})
            if result:
                return {"windows": result}
            # Fallback: visa gamla schedule om det finns
            schedule = self.coordinator.schedule or []
            if not schedule:
                price_data = self.coordinator.price_data or []
                return {
                    "raw_two_days": [
                        {
                            "start": entry.get("start"),
                            "end": entry.get("end"),
                            "charge": 0
                        }
                        for entry in price_data
                    ]
                }
            return {
                "raw_two_days": [
                    {
                        "start": entry.get("start"),
                        "end": entry.get("end"),
                        "charge": 1 if entry.get("action") == "charge" else 0
                    }
                    for entry in schedule
                ]
            }
        elif key == "discharge_raw":
            # Visa discharge_raw för window 1-4 om de finns
            result = []
            for n in range(1, 5):
                discharge_raw = getattr(self.coordinator, f"discharge_raw_window{n}", None)
                if discharge_raw:
                    result.append({"window": n, "raw_two_days": discharge_raw})
            if result:
                return {"windows": result}
            schedule = self.coordinator.schedule or []
            if not schedule:
                price_data = self.coordinator.price_data or []
                return {
                    "raw_two_days": [
                        {
                            "start": entry.get("start"),
                            "end": entry.get("end"),
                            "discharge": 0
                        }
                        for entry in price_data
                    ]
                }
            return {
                "raw_two_days": [
                    {
                        "start": entry.get("start"),
                        "end": entry.get("end"),
                        "discharge": 1 if entry.get("action") == "discharge" else 0
                    }
                    for entry in schedule
                ]
            }
        elif key == "estimated_soc":
            # Bygg SoC-kurva direkt från optimeringslogikens schedule (fältet 'soc')
            schedule = self.coordinator.schedule or []
            soc_curve = []
            for entry in schedule:
                soc_curve.append({
                    "start": entry.get("start"),
                    "end": entry.get("end"),
                    "soc": entry.get("soc")
                })
            if soc_curve:
                return {
                    "raw_two_days": soc_curve,
                    "last_updated": datetime.now().isoformat()
                }
            return {"raw_two_days": [], "last_updated": datetime.now().isoformat()}
        elif key == "debug_table":
            # Bygg en felsökningstabell med start, value, charge, discharge, estimated_soc för ALLA windows
            price_data = self.coordinator.price_data or []
            # Hämta alla window-data
            charge_raw_all = []
            discharge_raw_all = []
            estimated_soc_all = []
            for n in range(1, 5):
                cr = getattr(self.coordinator, f"charge_raw_window{n}", []) or []
                dr = getattr(self.coordinator, f"discharge_raw_window{n}", []) or []
                es = getattr(self.coordinator, f"estimated_soc_window{n}", []) or []
                # Lägg till window-index för felsökning
                for i, row in enumerate(cr):
                    if i < len(price_data):
                        row = dict(row)
                        row["window"] = n
                        if i >= len(charge_raw_all):
                            charge_raw_all.append(row)
                        else:
                            # Om flera windows på samma timme, summera charge
                            charge_raw_all[i]["charge"] += row["charge"]
                for i, row in enumerate(dr):
                    if i < len(price_data):
                        row = dict(row)
                        row["window"] = n
                        if i >= len(discharge_raw_all):
                            discharge_raw_all.append(row)
                        else:
                            discharge_raw_all[i]["discharge"] += row["discharge"]
                for i, row in enumerate(es):
                    if i < len(price_data):
                        row = dict(row)
                        row["window"] = n
                        if i >= len(estimated_soc_all):
                            estimated_soc_all.append(row)
                        else:
                            estimated_soc_all[i]["soc"] = max(estimated_soc_all[i]["soc"], row["soc"])
            table = []
            for i in range(len(price_data)):
                entry = price_data[i]
                start = entry.get("start")
                value = entry.get("value")
                charge = charge_raw_all[i]["charge"] if i < len(charge_raw_all) else None
                discharge = discharge_raw_all[i]["discharge"] if i < len(discharge_raw_all) else None
                soc = estimated_soc_all[i]["soc"] if i < len(estimated_soc_all) else None
                table.append({
                    "start": start,
                    "value": value,
                    "charge": charge,
                    "discharge": discharge,
                    "estimated_soc": soc
                })
            return {"table": table}
        return {}