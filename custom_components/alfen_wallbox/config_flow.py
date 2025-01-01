"""Config flow for the Alfen Wallbox platform."""

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    CONN_CLASS_LOCAL_POLL,
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import (
    CATEGORIES,
    CONF_REFRESH_CATEGORIES,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

DEFAULT_OPTIONS = {
    CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
    CONF_TIMEOUT: DEFAULT_TIMEOUT,
    CONF_REFRESH_CATEGORIES: DEFAULT_REFRESH_CATEGORIES,
}


class AlfenOptionsFlowHandler(OptionsFlow):
    """Handle Alfen options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Manage the options flow."""
        if user_input is not None:
            return self.async_create_entry(data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=300)),
                    vol.Required(
                        CONF_TIMEOUT,
                        default=self.config_entry.options.get(
                            CONF_TIMEOUT, DEFAULT_TIMEOUT
                        ),
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=30)),
                    vol.Required(
                        CONF_REFRESH_CATEGORIES,
                        default=self.config_entry.options.get(
                            CONF_REFRESH_CATEGORIES, DEFAULT_REFRESH_CATEGORIES
                        ),
                    ): cv.multi_select(CATEGORIES),
                },
            ),
        )


class AlfenFlowHandler(ConfigFlow, domain=DOMAIN):
    """Handle a config flow."""

    VERSION = 2
    CONNECTION_CLASS = CONN_CLASS_LOCAL_POLL

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> AlfenOptionsFlowHandler:
        """Options callback for Reolink."""
        return AlfenOptionsFlowHandler()

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is not None:
            result = await self.async_validate_input(user_input)
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Required(CONF_USERNAME, default="admin"): str,
                    vol.Required(CONF_PASSWORD): str,
                    vol.Required(CONF_NAME): str,
                }
            ),
        )

    async def async_validate_input(self, user_input) -> ConfigFlowResult | None:
        """Validate the input using the Devialet API."""

        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == user_input[CONF_HOST]:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(
            title=user_input[CONF_HOST],
            data={
                CONF_HOST: user_input[CONF_HOST],
                CONF_NAME: user_input[CONF_NAME],
                CONF_USERNAME: user_input[CONF_USERNAME],
                CONF_PASSWORD: user_input[CONF_PASSWORD],
            },
            options=DEFAULT_OPTIONS,
        )
