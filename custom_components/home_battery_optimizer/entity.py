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
        if description is not None:
            self._attr_translation_key = description.key
            self._attr_has_entity_name = True
            self._attr_unique_id = f"{config_entry.entry_id}_{description.key}"
            self._attr_name = description.name
        else:
            # Sensorn: sätt defaultnamn och unikt id
            self._attr_has_entity_name = False
            self._attr_unique_id = f"{config_entry.entry_id}_schedule"
            self._attr_name = "Battery Schedule"
            self.entity_description = None
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

    @property
    def device_class(self):
        # Returnera None om entity_description saknas
        if hasattr(self, "entity_description") and self.entity_description is not None and hasattr(self.entity_description, "device_class"):
            return self.entity_description.device_class
        return None

    @property
    def entity_registry_enabled_default(self):
        # Returnera True om entity_description saknas (default), annars fråga entity_description
        if hasattr(self, "entity_description") and self.entity_description is not None and hasattr(self.entity_description, "entity_registry_enabled_default"):
            return self.entity_description.entity_registry_enabled_default
        return True

    @property
    def entity_registry_visible_default(self):
        # Return True if entity_description is None (default), otherwise ask entity_description
        if hasattr(self, "entity_description") and self.entity_description is not None and hasattr(self.entity_description, "entity_registry_visible_default"):
            return self.entity_description.entity_registry_visible_default
        return True

    @property
    def icon(self):
        return "mdi:battery-clock"

    @property
    def translation_key(self):
        return None

    @property
    def native_unit_of_measurement(self):
        return None

    @property
    def suggested_unit_of_measurement(self):
        return None

    @property
    def state_class(self):
        return None

    @property
    def options(self):
        return None

    @property
    def entity_category(self):
        return None

    @property
    def has_entity_name(self):
        return getattr(self, '_attr_has_entity_name', False)

    @property
    def unique_id(self):
        return getattr(self, '_attr_unique_id', None)

    @property
    def name(self):
        return getattr(self, '_attr_name', None)

    @property
    def suggested_display_precision(self):
        return None

    @property
    def last_reset(self):
        return None

    @property
    def force_update(self):
        # Returnera False om entity_description saknas, annars fråga entity_description
        if hasattr(self, "entity_description") and self.entity_description is not None and hasattr(self.entity_description, "force_update"):
            return self.entity_description.force_update
        return False

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
