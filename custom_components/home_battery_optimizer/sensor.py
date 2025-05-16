from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from . import DOMAIN

class BatteryStatusSensor(Entity):
    def __init__(self, hass, name, battery_data):
        self.hass = hass
        self._name = name
        self._battery_data = battery_data

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        # Hämta aktuell batteriprocent från den valda entityn
        battery_entity_id = self._battery_data.get('battery_entity')
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            if battery_state is not None and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    return float(battery_state.state)
                except ValueError:
                    return STATE_UNKNOWN
        return STATE_UNKNOWN

    @property
    def extra_state_attributes(self):
        return {
            'charging': self._battery_data.get('charging', False),
            'discharging': self._battery_data.get('discharging', False),
            'next_charge_time': self._battery_data.get('next_charge_time', STATE_UNKNOWN),
            'next_discharge_time': self._battery_data.get('next_discharge_time', STATE_UNKNOWN),
            'schedule': self._battery_data.get('schedule', []),
            'battery_entity': self._battery_data.get('battery_entity', STATE_UNKNOWN),
            'nordpool_entity': self._battery_data.get('nordpool_entity', STATE_UNKNOWN),
            'default_charge_rate': self._battery_data.get('default_charge_rate', STATE_UNKNOWN),
            'default_discharge_rate': self._battery_data.get('default_discharge_rate', STATE_UNKNOWN),
        }

    @property
    def unique_id(self):
        return f"{DOMAIN}_battery_status"

async def async_setup_entry(hass, entry, async_add_entities):
    battery_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BatteryStatusSensor(hass, "Battery Status", battery_data)])