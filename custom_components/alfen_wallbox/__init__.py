"""Alfen Wallbox integration."""

import asyncio
import logging

from aiohttp import ClientConnectionError
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady

from .alfen import AlfenDevice
from .const import DOMAIN, TIMEOUT
from homeassistant.util.ssl import get_default_context, get_default_no_verify_context

PLATFORMS = [
    Platform.SENSOR,
    Platform.SELECT,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.TEXT
]

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Alfen Wallbox component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Set up Alfen Wallbox from a config entry."""
    conf = config_entry.data

    # if CONF_SCAN_INTERVAL not in conf, then we give 5
    device = await alfen_setup(
        hass, conf[CONF_HOST], conf[CONF_NAME], conf[CONF_USERNAME], conf[CONF_PASSWORD], conf[CONF_SCAN_INTERVAL] if CONF_SCAN_INTERVAL in conf else 5
    )
    if not device:
        return False

    device.initilize = True
    await device.async_update()
    device.get_number_of_socket()
    device.get_licenses()


    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][config_entry.entry_id] = device

    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)
    device.initilize = False
    return True


async def async_unload_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry: %s", config_entry)

    unload_ok = await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)

    hass.data[DOMAIN].pop(config_entry.entry_id)

    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


async def alfen_setup(hass: HomeAssistant, host: str, name: str, username: str, password: str, scan_interval:int) -> AlfenDevice | None:
    """Create a Alfen instance only once."""

    try:
        with timeout(TIMEOUT):
            device = AlfenDevice(hass, host, name, username, password, scan_interval)
            await device.init()
    except asyncio.TimeoutError:
        _LOGGER.debug("Connection to %s timed out", host)
        raise ConfigEntryNotReady
    except ClientConnectionError as e:
        _LOGGER.debug("ClientConnectionError to %s %s", host, str(e))
        raise ConfigEntryNotReady
    except Exception as e:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error creating device %s %s", host, str(e))
        return None

    return device
