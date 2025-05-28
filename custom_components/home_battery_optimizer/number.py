from homeassistant.components.number import NumberEntity
from homeassistant.helpers.entity import EntityDescription
from .const import DOMAIN
from .entity import HBOEntity

NUMBER_DESCRIPTIONS = [
    EntityDescription(key="charge_rate", name="Charge Rate"),
    EntityDescription(key="discharge_rate", name="Discharge Rate"),
    EntityDescription(key="max_battery_soc", name="Max Battery SOC"),
    EntityDescription(key="min_battery_soc", name="Min Battery SOC"),
    EntityDescription(key="min_profit", name="Min Profit"),
]

async def async_setup_entry(hass, entry, async_add_entities):
    coordinator = hass.data[DOMAIN][entry.entry_id]
    numbers = [
        BatteryOptimizerNumber(coordinator, entry, description)
        for description in NUMBER_DESCRIPTIONS
    ]
    async_add_entities(numbers)

class BatteryOptimizerNumber(HBOEntity, NumberEntity):
    def __init__(self, coordinator, config_entry, description):
        super().__init__(coordinator, config_entry, description)
        self._key = description.key
        self._name = description.name
        # Remove reference to description after extracting key and name
        if hasattr(self, 'entity_description'):
            del self.entity_description

    @property
    def name(self):
        return self._name

    @property
    def native_value(self):
        key = self._key
        if key == "charge_rate":
            return self.coordinator.charge_rate
        elif key == "discharge_rate":
            return self.coordinator.discharge_rate
        elif key == "max_battery_soc":
            return self.coordinator.max_battery_soc
        elif key == "min_battery_soc":
            return self.coordinator.min_battery_soc
        elif key == "min_profit":
            return self.coordinator.min_profit
        return None

    @property
    def native_min_value(self):
        key = self._key
        if key in ("charge_rate", "discharge_rate", "min_profit"):
            return 0
        elif key in ("max_battery_soc", "min_battery_soc"):
            return 0
        return 0

    @property
    def native_max_value(self):
        key = self._key
        if key in ("charge_rate", "discharge_rate"):
            return 100
        elif key == "max_battery_soc":
            return 100
        elif key == "min_battery_soc":
            return 100
        elif key == "min_profit":
            return 1000
        return 100

    @property
    def native_step(self):
        return 1

    async def async_set_native_value(self, value):
        key = self._key
        # 1. Uppdatera self.config
        self.coordinator.config[key] = value
        # 2. Spara till entry.options (persistent lagring)
        hass = self.coordinator.hass
        entry = self.config_entry
        # Skapa ny options-dict med uppdaterat värde
        new_options = dict(entry.options)
        new_options[key] = value
        hass.config_entries.async_update_entry(entry, options=new_options)
        # 3. Uppdatera coordinator-attribut
        if key == "charge_rate":
            self.coordinator.charge_rate = value
            if hasattr(self.coordinator, 'async_update_sensors'):
                await self.coordinator.async_update_sensors()
        elif key == "discharge_rate":
            self.coordinator.discharge_rate = value
            if hasattr(self.coordinator, 'async_update_sensors'):
                await self.coordinator.async_update_sensors()
        elif key == "max_battery_soc":
            self.coordinator.max_battery_soc = value
            if hasattr(self.coordinator, 'async_update_sensors'):
                await self.coordinator.async_update_sensors()
        elif key == "min_battery_soc":
            self.coordinator.min_battery_soc = value
            if hasattr(self.coordinator, 'async_update_sensors'):
                await self.coordinator.async_update_sensors()
        elif key == "min_profit":
            self.coordinator.min_profit = value
            if hasattr(self.coordinator, 'async_update_sensors'):
                await self.coordinator.async_update_sensors()
        self.async_write_ha_state()
        if hasattr(self.coordinator, 'async_update_listeners'):
            await self.coordinator.async_update_listeners()