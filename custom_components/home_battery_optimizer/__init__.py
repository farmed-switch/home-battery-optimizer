from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.event import async_track_time_interval, async_track_state_change_event
from datetime import timedelta, datetime

from .coordinator import HomeBatteryOptimizerCoordinator

DOMAIN = "home_battery_optimizer"

async def async_setup(hass, config):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a config entry for Home Battery Optimizer."""
    hass.data.setdefault(DOMAIN, {})
    coordinator = HomeBatteryOptimizerCoordinator(hass, entry.data)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Store unsubscribe callbacks for listeners
    if "_unsub_listeners" not in hass.data[DOMAIN]:
        hass.data[DOMAIN]["_unsub_listeners"] = {}
    unsub_list = []
    hass.data[DOMAIN]["_unsub_listeners"][entry.entry_id] = unsub_list

    # Forward setup to sensor, switch, number and button platforms
    await hass.config_entries.async_forward_entry_setups(entry, ["sensor", "switch", "number", "button"])

    # --- Service handlers ---
    async def handle_force_update_schedule(call):
        """Force update the battery schedule sensor."""
        entity_id = f"sensor.{DOMAIN}_schedule"
        await hass.services.async_call(
            "homeassistant",
            "update_entity",
            {"entity_id": entity_id}
        )

    async def handle_force_charge(call):
        """Force turn on the charging switch."""
        entity_id = f"switch.battery_charging"
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id})

    async def handle_force_discharge(call):
        """Force turn on the discharging switch."""
        entity_id = f"switch.battery_discharging"
        await hass.services.async_call("switch", "turn_on", {"entity_id": entity_id})

    # Register services
    hass.services.async_register(DOMAIN, "force_update_schedule", handle_force_update_schedule)
    hass.services.async_register(DOMAIN, "force_charge", handle_force_charge)
    hass.services.async_register(DOMAIN, "force_discharge", handle_force_discharge)

    # --- Schemalägg automatisk uppdatering ---
    async def scheduled_update(now):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_update_sensors()
        await handle_force_update_schedule(None)

    # Starta första körningen kl 00:00
    now = datetime.now()
    first_run = now.replace(hour=0, minute=0, second=0, microsecond=0)
    if now > first_run:
        # Om vi redan passerat midnatt idag, ta nästa dag
        first_run = first_run + timedelta(days=1)
    delay = (first_run - now)
    async def start_periodic_updates(_):
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_update_sensors()
        await handle_force_update_schedule(None)
        # Kör sedan var 15:e minut
        async_track_time_interval(hass, scheduled_update, timedelta(minutes=15))
    hass.loop.call_later(delay.total_seconds(), lambda: hass.async_create_task(start_periodic_updates(None)))

    # --- Periodisk polling av switchar (charging/discharging) ---
    async def poll_switches(_):
        for eid in hass.states.async_entity_ids("switch"):
            if "charging" in eid or "discharging" in eid:
                await hass.services.async_call("homeassistant", "update_entity", {"entity_id": eid})
    async_track_time_interval(hass, poll_switches, timedelta(minutes=1))

    # --- Listen for state changes on battery, price, and SoC-related entities ---
    battery_entity = entry.data.get("battery_entity")
    price_entity = entry.data.get("nordpool_entity")
    soc_entities = [
        entry.data.get("battery_entity"),
        entry.data.get("target_soc_entity"),
    ]
    # Add more SoC-related entities if needed
    def _is_soc_related(entity_id):
        return entity_id in soc_entities and entity_id is not None

    async def _state_change_listener(event):
        # Defensive: Only run if entry_id is still present
        if entry.entry_id not in hass.data[DOMAIN]:
            return
        coordinator = hass.data[DOMAIN][entry.entry_id]
        await coordinator.async_update_sensors()
    if battery_entity:
        unsub = async_track_state_change_event(hass, [battery_entity], _state_change_listener)
        unsub_list.append(unsub)
    if price_entity:
        unsub = async_track_state_change_event(hass, [price_entity], _state_change_listener)
        unsub_list.append(unsub)
    # Listen for SoC-related entity changes (e.g. target_soc)
    for soc_entity in soc_entities:
        if soc_entity and soc_entity not in (battery_entity, price_entity):
            unsub = async_track_state_change_event(hass, [soc_entity], _state_change_listener)
            unsub_list.append(unsub)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Unsubscribe listeners if present
    unsub_list = hass.data.get(DOMAIN, {}).get("_unsub_listeners", {}).pop(entry.entry_id, [])
    for unsub in unsub_list:
        unsub()
    hass.data[DOMAIN].pop(entry.entry_id, None)
    return True