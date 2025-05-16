# Home Assistant Integration for Home Battery Optimizer

from homeassistant import ConfigEntries, Core
from homeassistant.core import HomeAssistant
from homeassistant.helpers import discovery

DOMAIN = "home_battery_optimizer"

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Home Battery Optimizer integration."""
    hass.data[DOMAIN] = {}
    await discovery.async_load_platform(hass, "sensor", DOMAIN, {}, config)
    await discovery.async_load_platform(hass, "switch", DOMAIN, {}, config)
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntries) -> bool:
    """Set up a config entry for Home Battery Optimizer."""
    hass.data[DOMAIN][entry.entry_id] = entry.data
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntries) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload(entry.entry_id)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unload_ok