from homeassistant.components.button import ButtonEntity
from homeassistant.helpers.entity import EntityDescription
from .const import DOMAIN
from .entity import HBOEntity

BUTTON_DESCRIPTIONS = []

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    buttons = [
        HBOButton(coordinator, entry, description)
        for description in BUTTON_DESCRIPTIONS
    ]
    async_add_entities(buttons)

class HBOButton(ButtonEntity):
    def __init__(self, coordinator, config_entry, description):
        super().__init__()
        self.coordinator = coordinator
        self.config_entry = config_entry
        self._key = description.key
        self._name = description.name

    @property
    def name(self):
        return self._name

    async def async_press(self):
        pass  # Ingen self_usage_toggle längre