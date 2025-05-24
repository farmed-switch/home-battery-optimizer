import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv

from .const import DOMAIN

class HomeBatteryOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Home Battery Optimizer",
                data=user_input,
            )

        data_schema = vol.Schema({
            vol.Required("nordpool_entity"): cv.string,  # Ange entity_id som text
            vol.Required("battery_entity"): cv.string,   # Ange entity_id som text
            vol.Required("solar_entity"): cv.string,     # Solelproduktion
            vol.Required("consumption_entity"): cv.string, # Hushållsförbrukning
            vol.Required("battery_power_entity"): cv.string, # Batteriladdning/-urladdning
        })

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
        )

    @callback
    def async_get_options_flow(self, config_entry):
        return HomeBatteryOptimizerOptionsFlow(config_entry)

class HomeBatteryOptimizerOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        data_schema = vol.Schema({
            vol.Required("nordpool_entity", default=self.config_entry.data.get("nordpool_entity", "")): cv.string,
            vol.Required("battery_entity", default=self.config_entry.data.get("battery_entity", "")): cv.string,
            vol.Required("solar_entity", default=self.config_entry.data.get("solar_entity", "")): cv.string,
            vol.Required("consumption_entity", default=self.config_entry.data.get("consumption_entity", "")): cv.string,
            vol.Required("battery_power_entity", default=self.config_entry.data.get("battery_power_entity", "")): cv.string,
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )