try:
    from homeassistant.util import dt as dt_util
except ImportError:
    import datetime as dt_util

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.entity import EntityDescription
from . import DOMAIN
from .entity import HBOEntity

SWITCH_DESCRIPTIONS = [
    EntityDescription(key="charging", name="Battery Charging"),
    EntityDescription(key="discharging", name="Battery Discharging"),
    EntityDescription(key="self_usage", name="Self Usage"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    switches = [
        BatteryOptimizerSwitch(coordinator, entry, description)
        for description in SWITCH_DESCRIPTIONS
    ]
    async_add_entities(switches)

class BatteryOptimizerSwitch(HBOEntity, SwitchEntity):
    def __init__(self, coordinator, config_entry, description):
        HBOEntity.__init__(self, coordinator, config_entry, description)
        SwitchEntity.__init__(self)
        self._key = description.key
        self._name = description.name

    @property
    def name(self):
        return self._name

    @property
    def is_on(self):
        key = self._key
        if key == "charging":
            return self.coordinator.charging_on
        elif key == "discharging":
            return self.coordinator.discharging_on
        elif key == "self_usage":
            return getattr(self.coordinator, "self_usage_on", False)
        return False

    async def async_turn_on(self, **kwargs):
        key = self._key
        if key == "charging":
            await self.coordinator.async_set_charging(True)
        elif key == "discharging":
            await self.coordinator.async_set_discharging(True)
        elif key == "self_usage":
            await self.coordinator.async_set_self_usage(True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        key = self._key
        if key == "charging":
            await self.coordinator.async_set_charging(False)
        elif key == "discharging":
            await self.coordinator.async_set_discharging(False)
        elif key == "self_usage":
            await self.coordinator.async_set_self_usage(False)
        self.async_write_ha_state()