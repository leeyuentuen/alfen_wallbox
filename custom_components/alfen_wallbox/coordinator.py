"""Class representing a Alfen Wallbox update coordinator."""

import asyncio
from asyncio import timeout
from datetime import timedelta
import logging
from ssl import CERT_NONE

from aiohttp import ClientConnectionError

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import get_default_context

from .alfen import AlfenDevice
from .const import (
    CONF_REFRESH_CATEGORIES,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type AlfenConfigEntry = ConfigEntry[AlfenCoordinator]


class AlfenCoordinator(DataUpdateCoordinator[None]):
    """Alfen update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: AlfenConfigEntry) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

        self.entry = entry
        self.hass = hass
        self.device = None
        self.timeout = self.entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)

    async def _async_setup(self):
        """Set up the coordinator."""
        session = async_get_clientsession(self.hass, verify_ssl=False)

        # Default ciphers needed as of python 3.10
        context = get_default_context()

        context.set_ciphers("DEFAULT")
        context.check_hostname = False
        context.verify_mode = CERT_NONE

        self.device = AlfenDevice(
            session,
            self.entry.data[CONF_HOST],
            self.entry.data[CONF_NAME],
            self.entry.data[CONF_USERNAME],
            self.entry.data[CONF_PASSWORD],
            self.entry.options.get(CONF_REFRESH_CATEGORIES, DEFAULT_REFRESH_CATEGORIES),
            context,
        )
        if not await self.async_connect():
            raise UpdateFailed("Error communicating with API")

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            async with timeout(self.timeout):
                if not await self.device.async_update():
                    raise UpdateFailed("Error updating")
        except TimeoutError as exc:
            _LOGGER.warning("Update from %s timed out after %ss", self.entry.data[CONF_HOST], self.timeout)
            # Don't sleep - let the coordinator's update_interval handle retry timing
            # Sleeping here would block the entire coordinator
            raise UpdateFailed("Update timed out") from exc

    async def async_connect(self) -> bool:
        """Connect to the API endpoint."""

        try:
            async with timeout(self.timeout):
                return await self.device.init()
        except TimeoutError:
            _LOGGER.debug("Connection to %s timed out", self.entry.data[CONF_HOST])
            return False
        except ClientConnectionError as e:
            _LOGGER.debug(
                "ClientConnectionError to %s %s",
                self.entry.data[CONF_HOST],
                str(e),
            )
            return False
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error(
                "Unexpected error creating device %s %s",
                self.entry.data[CONF_HOST],
                str(e),
            )
            return False


async def options_update_listener(self, entry: AlfenConfigEntry):
    """Handle options update."""
    coordinator = entry.runtime_data
    coordinator.device.get_static_properties = True
    coordinator.device.category_options = entry.options.get(
        CONF_REFRESH_CATEGORIES, DEFAULT_REFRESH_CATEGORIES
    )

    coordinator.update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
