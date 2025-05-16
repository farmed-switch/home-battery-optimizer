from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector

from .const import DOMAIN

class HomeBatteryOptimizerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Home Battery Optimizer",
                data=user_input,
            )

        data_schema = {
            "nordpool_entity": selector.EntitySelector(
                selector.EntitySelectorConfig(
                    integration="nordpool",
                    domain="sensor"
                )
            ),
            "battery_entity": selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            "default_charge_rate": selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%/h")
            ),
            "default_discharge_rate": selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%/h")
            ),
        }

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

        data_schema = {
            "nordpool_entity": selector.EntitySelector(
                selector.EntitySelectorConfig(
                    integration="nordpool",
                    domain="sensor"
                )
            ),
            "battery_entity": selector.EntitySelector(
                selector.EntitySelectorConfig(
                    domain="sensor"
                )
            ),
            "default_charge_rate": selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%/h")
            ),
            "default_discharge_rate": selector.NumberSelector(
                selector.NumberSelectorConfig(min=0, max=100, step=1, unit_of_measurement="%/h")
            ),
        }

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
        )