from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

DOMAIN = "home_battery_optimizer"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Home Battery Optimizer integration."""
    hass.data.setdefault(DOMAIN, {})
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Home Battery Optimizer."""
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Lägg till sensor-plattformen
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setup(entry, "sensor")
    )
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True