from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityDescription
from .const import DOMAIN
from .entity import HBOEntity

BUTTON_DESCRIPTIONS = [
    EntityDescription(key="self_usage_toggle", name="Self Usage Toggle"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    buttons = [
        BatteryOptimizerButton(coordinator, entry, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(buttons)

class BatteryOptimizerButton(HBOEntity, ButtonEntity):
    def __init__(self, coordinator, config_entry, description):
        super().__init__(coordinator, config_entry, description)
        self._key = description.key
        self._name = description.name

    @property
    def name(self):
        return self._name

    async def async_press(self):
        if self._key == "self_usage_toggle":
            await self.coordinator.async_toggle_self_usage()
            self.async_write_ha_state()