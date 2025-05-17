from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from . import DOMAIN
from .battery_optimizer import BatteryOptimizer

class BatteryStatusSensor(Entity):
    def __init__(self, hass, name, config):
        self.hass = hass
        self._name = name
        self._config = config
        self._optimizer = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        battery_entity_id = self._config.get('battery_entity')
        if battery_entity_id:
            battery_state = self.hass.states.get(battery_entity_id)
            if battery_state is not None and battery_state.state not in (None, "", "unknown", "unavailable"):
                try:
                    soc = float(battery_state.state)
                except ValueError:
                    soc = STATE_UNKNOWN
            else:
                soc = STATE_UNKNOWN
        else:
            soc = STATE_UNKNOWN

        # Skapa/uppdatera optimizer om vi har data
        if soc != STATE_UNKNOWN:
            self._optimizer = BatteryOptimizer(
                battery_capacity=100,
                charge_rate=self._config.get("default_charge_rate", 10),
                discharge_rate=self._config.get("default_discharge_rate", 10),
                price_analysis=None  # Lägg till PriceAnalysis om du har det
            )
            self._optimizer.current_charge = soc
            # Exempel: self._optimizer.charge_battery(1)
        return soc

    @property
    def extra_state_attributes(self):
        attrs = {
            'battery_entity': self._config.get('battery_entity', STATE_UNKNOWN),
            'nordpool_entity': self._config.get('nordpool_entity', STATE_UNKNOWN),
            'default_charge_rate': self._config.get('default_charge_rate', STATE_UNKNOWN),
            'default_discharge_rate': self._config.get('default_discharge_rate', STATE_UNKNOWN),
        }
        if self._optimizer:
            attrs["schedule"] = self._optimizer.schedule
        return attrs

    @property
    def unique_id(self):
        return f"{DOMAIN}_battery_status"

async def async_setup_entry(hass, entry, async_add_entities):
    config = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([BatteryStatusSensor(hass, "Battery Status", config)])