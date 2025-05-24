"""Base entity class for Home Battery Optimizer, following EV Smart Charging best practices."""
from homeassistant.helpers.entity import Entity
from .const import DOMAIN

class HBOEntity(Entity):
    """Base entity for Home Battery Optimizer."""
    _entity_key: str

    def __init__(self, coordinator, config_entry, description):
        self.coordinator = coordinator
        self.config_entry = config_entry
        self.entity_description = description
        self._attr_translation_key = description.key
        self._attr_has_entity_name = True
        self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
        self._attr_name = description.name
        # Register update callback for state refresh
        if hasattr(self.coordinator, "add_update_callback"):
            self.coordinator.add_update_callback(self.async_write_ha_state)
        # DO NOT set entity_id manually!

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self.config_entry.entry_id)},
            "name": self.config_entry.title,
            "model": "Home Battery Optimizer",
            "manufacturer": "farmed-switch",
        }

    async def async_added_to_hass(self):
        # Register for coordinator updates if available
        if hasattr(self.coordinator, 'async_update_listeners'):
            if not hasattr(self.coordinator, '_entity_update_callbacks'):
                self.coordinator._entity_update_callbacks = set()
            self.coordinator._entity_update_callbacks.add(self.async_write_ha_state)

    async def async_will_remove_from_hass(self):
        # Unregister from coordinator updates
        if hasattr(self.coordinator, '_entity_update_callbacks'):
            self.coordinator._entity_update_callbacks.discard(self.async_write_ha_state)
