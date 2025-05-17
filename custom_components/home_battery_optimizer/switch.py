from homeassistant.components.switch import SwitchEntity
from . import DOMAIN
from .battery_optimizer import BatteryOptimizer

class BatteryChargingSwitch(SwitchEntity):
    def __init__(self, hass, name, config):
        self.hass = hass
        self._name = name
        self._config = config
        self._is_on = False
        self._optimizer = BatteryOptimizer(
            battery_capacity=100,
            charge_rate=config.get("default_charge_rate", 10),
            discharge_rate=config.get("default_discharge_rate", 10),
            price_analysis=None
        )

    @property
    def name(self):
        return f"{self._name} Charging"

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        self._optimizer.charge_battery(1)  # Starta laddning (exempel: 1 timme)

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        # Här kan du lägga till logik för att stoppa laddning om det behövs

    async def async_update(self):
        pass

class BatteryDischargingSwitch(SwitchEntity):
    def __init__(self, hass, name, config):
        self.hass = hass
        self._name = name
        self._config = config
        self._is_on = False
        self._optimizer = BatteryOptimizer(
            battery_capacity=100,
            charge_rate=config.get("default_charge_rate", 10),
            discharge_rate=config.get("default_discharge_rate", 10),
            price_analysis=None
        )

    @property
    def name(self):
        return f"{self._name} Discharging"

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        self._optimizer.discharge_battery(1)  # Starta urladdning (exempel: 1 timme)

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        # Här kan du lägga till logik för att stoppa urladdning om det behövs

    async def async_update(self):
        pass

async def async_setup_entry(hass, entry, async_add_entities):
    config = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([
        BatteryChargingSwitch(hass, "Battery", config),
        BatteryDischargingSwitch(hass, "Battery", config)
    ])