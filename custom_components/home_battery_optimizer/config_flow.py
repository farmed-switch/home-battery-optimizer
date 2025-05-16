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

        return self.async_show_form(
            step_id="user",
            data_schema=selector.SelectSelector(
                selector={
                    "type": "object",
                    "properties": {
                        "nordpool_entity": {
                            "type": "string",
                            "required": True,
                            "description": "Nordpool integration entity",
                        },
                        "battery_percentage": {
                            "type": "number",
                            "required": True,
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Battery percentage (0-100)",
                        },
                    },
                }
            ),
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

        return self.async_show_form(
            step_id="init",
            data_schema=selector.SelectSelector(
                selector={
                    "type": "object",
                    "properties": {
                        "nordpool_entity": {
                            "type": "string",
                            "required": True,
                            "description": "Nordpool integration entity",
                        },
                        "battery_percentage": {
                            "type": "number",
                            "required": True,
                            "minimum": 0,
                            "maximum": 100,
                            "description": "Battery percentage (0-100)",
                        },
                    },
                }
            ),
        )