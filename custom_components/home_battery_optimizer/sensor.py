from homeassistant.components.sensor import SensorEntity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from homeassistant.helpers.entity import EntityDescription
from .entity import HBOEntity
import logging
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

# Define entity descriptions for all sensors
SENSOR_DESCRIPTIONS = [
    EntityDescription(key="soc", name="Batteri SoC"),
    EntityDescription(key="estimated_soc", name="Estimated SoC"),
    EntityDescription(key="power", name="Batteri Effekt"),
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
            now = datetime.now()
            next_charge_time = None
            next_discharge_time = None
            for n in range(1, 5):
                charge_raw = getattr(self.coordinator, f"charge_raw_window{n}", None) or []
                for entry in charge_raw:
                    end_val = entry.get("end")
                    if not end_val:
                        continue
                    try:
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    if end_dt > now and entry.get("charge", 0) == 1:
                        next_charge_time = end_dt
                        break
                if next_charge_time:
                    break
            for n in range(1, 5):
                discharge_raw = getattr(self.coordinator, f"discharge_raw_window{n}", None) or []
                for entry in discharge_raw:
                    end_val = entry.get("end")
                    if not end_val:
                        continue
                    try:
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    if end_dt > now and entry.get("discharge", 0) == 1:
                        next_discharge_time = end_dt
                        break
                if next_discharge_time:
                    break
            if next_charge_time and (not next_discharge_time or next_charge_time <= next_discharge_time):
                return f"Waiting Charge {next_charge_time.strftime('%H.%M')}"
            elif next_discharge_time:
                return f"Waiting Discharge {next_discharge_time.strftime('%H.%M')}"
            else:
                return "No upcoming charge/discharge"
        if key == "charge_raw":
            now = datetime.now()
            # Kolla om vi är i en pågående laddning
            for n in range(1, 5):
                charge_raw = getattr(self.coordinator, f"charge_raw_window{n}", None) or []
                for entry in charge_raw:
                    start_val = entry.get("start")
                    end_val = entry.get("end")
                    if not start_val or not end_val:
                        continue
                    try:
                        start_dt = datetime.fromisoformat(start_val)
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    if start_dt <= now < end_dt and entry.get("charge", 0) == 1:
                        return "Charging"
            # Annars visa nästa planerade laddning (idag eller imorgon)
            next_charge_time = None
            next_charge_day = None
            for n in range(1, 5):
                charge_raw = getattr(self.coordinator, f"charge_raw_window{n}", None) or []
                for entry in charge_raw:
                    end_val = entry.get("end")
                    if not end_val:
                        continue
                    try:
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    if end_dt > now and entry.get("charge", 0) == 1:
                        next_charge_time = end_dt
                        next_charge_day = "Idag" if end_dt.date() == now.date() else "Imorgon"
                        break
                if next_charge_time:
                    break
            if next_charge_time:
                return f"Waiting Charge {next_charge_day} {next_charge_time.strftime('%H.%M')}"
            else:
                return "No upcoming charge"
        if key == "discharge_raw":
            now = datetime.utcnow()  # Använd UTC för att matcha Home Assistant-data
            # Hämta discharge_raw för alla windows och kolla om discharge=1 för aktuell timme
            for n in range(1, 5):
                discharge_raw = getattr(self.coordinator, f"discharge_raw_window{n}", None) or []
                for entry in discharge_raw:
                    start_val = entry.get("start")
                    end_val = entry.get("end")
                    if not start_val or not end_val:
                        continue
                    try:
                        start_dt = datetime.fromisoformat(start_val)
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    # Om nuvarande tid är inom intervallet och discharge=1, visa Discharging
                    if start_dt <= now < end_dt and entry.get("discharge", 0) == 1:
                        return "Discharging"
            # Annars visa nästa planerade urladdning
            next_discharge_time = None
            next_discharge_day = None
            for n in range(1, 5):
                discharge_raw = getattr(self.coordinator, f"discharge_raw_window{n}", None) or []
                for entry in discharge_raw:
                    end_val = entry.get("end")
                    if not end_val:
                        continue
                    try:
                        end_dt = datetime.fromisoformat(end_val)
                    except Exception:
                        continue
                    if end_dt > now and entry.get("discharge", 0) == 1:
                        next_discharge_time = end_dt
                        next_discharge_day = "Idag" if end_dt.date() == now.date() else "Imorgon"
                        break
                if next_discharge_time:
                    break
            if next_discharge_time:
                return f"Waiting Discharge {next_discharge_day} {next_discharge_time.strftime('%H.%M')}"
            else:
                return "No upcoming discharge"
        if key == "power":
            return getattr(self.coordinator, "current_power", None)
        if key == "status":
            # Prioritera Self Usage om aktiv
            if getattr(self.coordinator, "self_usage_on", False):
                return "Self Usage"
            schedule = self.coordinator.schedule or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
            for entry in schedule:
                start_dt = entry.get("start")
                end_dt = entry.get("end")
                if start_dt and end_dt:
                    try:
                        start_dt = datetime.fromisoformat(start_dt)
                        end_dt = datetime.fromisoformat(end_dt)
                        if start_dt <= now < end_dt:
                            action = entry.get("action", "idle")
                            if action == "charge":
                                return "Charge"
                            elif action == "discharge":
                                return "Discharge"
                            else:
                                return "Idle"
                    except Exception:
                        continue
            return "Idle"
        if key == "schedule":
            schedule = self.coordinator.schedule or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
            for entry in schedule:
                start_dt = entry.get("start")
                end_dt = entry.get("end")
                if start_dt and end_dt and now:
                    try:
                        start_dt = datetime.fromisoformat(start_dt)
                        end_dt = datetime.fromisoformat(end_dt)
                        if start_dt <= now < end_dt:
                            return entry.get("action", "idle")
                    except Exception:
                        continue
            return "idle"
        if key == "price_raw":
            # Visa aktuellt pris (value) för nuvarande tid, annars "Unknown"
            price_data = self.coordinator.price_data or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
            for entry in price_data:
                start = entry.get("start")
                end = entry.get("end")
                if start and end:
                    try:
                        start_dt = datetime.fromisoformat(start)
                        end_dt = datetime.fromisoformat(end)
                        if start_dt <= now < end_dt:
                            return entry.get("value")
                    except Exception:
                        continue
            return "Unknown"
        if key == "window_raw":
            schedule = self.coordinator.schedule or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
            for entry in schedule:
                start_dt = entry.get("start")
                end_dt = entry.get("end")
                window = entry.get("window")
                if start_dt and end_dt and window is not None:
                    try:
                        start_dt = datetime.fromisoformat(start_dt)
                        end_dt = datetime.fromisoformat(end_dt)
                        if start_dt <= now < end_dt:
                            return window
                    except Exception:
                        continue
            return None
        return ""

    @property
    def extra_state_attributes(self):
        key = self._key
        if key == "soc":
            return {"unit_of_measurement": "%", "source": self.coordinator.config.get("battery_entity")}
        if key == "power":
            return {"unit_of_measurement": "W", "source": self.coordinator.config.get("battery_power_entity")}
        if key == "status":
            # Dynamiskt beräkna charging_on och discharging_on utifrån schemat och nuvarande tid
            schedule = self.coordinator.schedule or []
            now = self.coordinator.hass.now() if hasattr(self.coordinator.hass, 'now') else datetime.now()
            charging_on = False
            discharging_on = False
            for entry in schedule:
                start_dt = entry.get("start")
                end_dt = entry.get("end")
                if start_dt and end_dt:
                    try:
                        start_dt = datetime.fromisoformat(start_dt)
                        end_dt = datetime.fromisoformat(end_dt)
                        if start_dt <= now < end_dt:
                            action = entry.get("action", "idle")
                            if action == "charge":
                                charging_on = True
                            elif action == "discharge":
                                discharging_on = True
                    except Exception:
                        continue
            return {"charging_on": charging_on, "discharging_on": discharging_on}
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
            # Bygg alltid raw_two_days direkt från schemat
            schedule = self.coordinator.schedule or []
            # Extra debug: visa schema-längd och första/andra rad
            try:
                schema_preview = "[tomt]" if not schedule else str(schedule[:2])
                self.coordinator.hass.async_create_task(
                    self.coordinator.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "HBO Debug: charge_raw schema-preview",
                            "message": f"Schema-längd: {len(schedule)}. Första/andra rad: {schema_preview}",
                            "notification_id": "hbo_charge_raw_schema_preview"
                        },
                        blocking=False
                    )
                )
            except Exception:
                pass
            debug_count = sum(1 for entry in schedule if entry.get("action") == "charge")
            # Skicka debug-info till Home Assistant notifikationspanel
            try:
                self.coordinator.hass.async_create_task(
                    self.coordinator.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "HBO Debug: charge_raw",
                            "message": f"Bygger raw_two_days: {len(schedule)} timmar, {debug_count} med charge=1",
                            "notification_id": "hbo_charge_raw_debug"
                        },
                        blocking=False
                    )
                )
            except Exception:
                pass
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
            # Bygg alltid raw_two_days direkt från schemat
            schedule = self.coordinator.schedule or []
            # Extra debug: visa schema-längd och första/andra rad
            try:
                schema_preview = "[tomt]" if not schedule else str(schedule[:2])
                self.coordinator.hass.async_create_task(
                    self.coordinator.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "HBO Debug: discharge_raw schema-preview",
                            "message": f"Schema-längd: {len(schedule)}. Första/andra rad: {schema_preview}",
                            "notification_id": "hbo_discharge_raw_schema_preview"
                        },
                        blocking=False
                    )
                )
            except Exception:
                pass
            debug_count = sum(1 for entry in schedule if entry.get("action") == "discharge")
            # Skicka debug-info till Home Assistant notifikationspanel
            try:
                self.coordinator.hass.async_create_task(
                    self.coordinator.hass.services.async_call(
                        "persistent_notification",
                        "create",
                        {
                            "title": "HBO Debug: discharge_raw",
                            "message": f"Bygger raw_two_days: {len(schedule)} timmar, {debug_count} med discharge=1",
                            "notification_id": "hbo_discharge_raw_debug"
                        },
                        blocking=False
                    )
                )
            except Exception:
                pass
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