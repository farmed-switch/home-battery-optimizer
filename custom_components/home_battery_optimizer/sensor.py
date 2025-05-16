from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from . import DOMAIN

class BatteryStatusSensor(Entity):
    def __init__(self, name, battery_data):
        self._name = name
        self._battery_data = battery_data

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._battery_data.get('percentage', STATE_UNKNOWN)

    @property
    def extra_state_attributes(self):
        return {
            'status': self._battery_data.get('status', STATE_UNKNOWN),
            'charging': self._battery_data.get('charging', False),
            'discharging': self._battery_data.get('discharging', False),
            'next_charge_time': self._battery_data.get('next_charge_time', STATE_UNKNOWN),
            'next_discharge_time': self._battery_data.get('next_discharge_time', STATE_UNKNOWN),
        }

    @property
    def unique_id(self):
        return f"{DOMAIN}_battery_status"

async def async_setup_entry(hass, entry, async_add_entities):
    battery_data = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BatteryStatusSensor("Battery Status", battery_data)])