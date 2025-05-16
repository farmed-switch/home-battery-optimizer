import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

class HomeBatteryOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        super().__init__()
        self.nordpool_entity = None
        self.battery_percentage = None

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            self.nordpool_entity = user_input["nordpool_entity"]
            self.battery_percentage = user_input["battery_percentage"]
            return self.async_create_entry(
                title="Home Battery Optimizer",
                data={
                    "nordpool_entity": self.nordpool_entity,
                    "battery_percentage": self.battery_percentage,
                },
            )

        data_schema = vol.Schema({
            vol.Required("nordpool_entity"): selector.TextSelector(),
            vol.Required("battery_percentage"): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100)
            ),
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
            vol.Required("nordpool_entity"): selector.TextSelector(),
            vol.Required("battery_percentage"): selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100)
            ),
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )