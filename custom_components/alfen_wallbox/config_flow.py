"""Config flow for the Alfen Wallbox platform."""
import asyncio
import logging

from aiohttp import ClientError
from async_timeout import timeout
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_USERNAME, CONF_PASSWORD

from .alfen import AlfenDevice

from .const import DOMAIN, TIMEOUT

_LOGGER = logging.getLogger(__name__)


@config_entries.HANDLERS.register(DOMAIN)
class FlowHandler(config_entries.ConfigFlow):
    """Handle a config flow."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    async def _create_entry(self, host: str, name: str, username: str, password: str) -> None:
        """Register new entry."""
        # Check if ip already is registered
        for entry in self._async_current_entries():
            if entry.data[CONF_HOST] == host:
                return self.async_abort(reason="already_configured")

        return self.async_create_entry(title=host, data={CONF_HOST: host, CONF_NAME: name, CONF_USERNAME: username, CONF_PASSWORD: password})

    async def _create_device(self, host: str, name: str, username: str, password: str):
        """Create device."""

        try:
            device = AlfenDevice(
                self.hass, host, name, username, password
            )
            with timeout(TIMEOUT):
                await device.init()
        except asyncio.TimeoutError:
            return self.async_abort(reason="device_timeout")
        except ClientError:
            _LOGGER.exception("ClientError")
            return self.async_abort(reason="device_fail")
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected error creating device")
            return self.async_abort(reason="device_fail")

        return await self._create_entry(host, name, username, password)

    async def async_step_user(self, user_input=None):
        """User initiated config flow."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=vol.Schema({
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME, default="admin"): str,
                    vol.Optional(CONF_PASSWORD, default=""): str,
                    vol.Optional(CONF_NAME): str
                })
            )
        return await self._create_device(user_input[CONF_HOST], user_input[CONF_NAME], user_input[CONF_USERNAME], user_input[CONF_PASSWORD])

    async def async_step_import(self, user_input):
        """Import a config entry."""
        host = user_input.get(CONF_HOST)
        if not host:
            return await self.async_step_user()
        return await self._create_device(host, user_input[CONF_NAME], user_input[CONF_USERNAME], user_input[CONF_PASSWORD])
