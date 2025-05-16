from homeassistant.helpers.entity import Entity
from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from . import DOMAIN

class BatteryOptimizerSwitch(SwitchEntity):
    def __init__(self, name, battery_optimizer):
        self._name = name
        self._battery_optimizer = battery_optimizer
        self._is_on = False

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        return self._is_on

    async def async_turn_on(self, **kwargs):
        self._is_on = True
        await self._battery_optimizer.start_charging()

    async def async_turn_off(self, **kwargs):
        self._is_on = False
        await self._battery_optimizer.stop_charging()

    async def async_update(self):
        # Update the switch state based on the battery optimizer's status
        self._is_on = self._battery_optimizer.is_charging()

async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities):
    battery_optimizer = hass.data[DOMAIN][entry.entry_id]
    
    switches = [
        BatteryOptimizerSwitch("Start Charging", battery_optimizer),
        BatteryOptimizerSwitch("Stop Charging", battery_optimizer),
    ]
    
    async_add_entities(switches)