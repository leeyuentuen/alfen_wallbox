"""Alfen Wallbox integration."""

import asyncio
from datetime import timedelta
import logging
from typing import Dict

from aiohttp import ClientConnectionError
from async_timeout import timeout

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_USERNAME,
    CONF_PASSWORD,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.typing import HomeAssistantType

from .alfen import AlfenDevice

from .const import (
    DOMAIN,
    TIMEOUT,
)

PLATFORMS = [Platform.SENSOR, Platform.SELECT]
SCAN_INTERVAL = timedelta(seconds=60)

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: Dict) -> bool:
    """Set up the Alfen Wallbox component."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistantType, entry: ConfigEntry):
    conf = entry.data
    device = await alfen_setup(
        hass, conf[CONF_HOST], conf[CONF_NAME], conf[CONF_USERNAME], conf[CONF_PASSWORD]
    )
    if not device:
        return False
    hass.data.setdefault(DOMAIN, {}).update({entry.entry_id: device})
    for component in PLATFORMS:
        hass.async_create_task(
            hass.config_entries.async_forward_entry_setup(entry, component)
        )

    """device_registry = await dr.async_get_registry(hass)
    device_registry.async_get_or_create(**device.device_info)"""
    return True


async def async_unload_entry(hass, config_entry):
    """Unload a config entry."""
    _LOGGER.debug("async_unload_entry: %s", config_entry)

    unload_ok = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(config_entry, component)
                for component in PLATFORMS
            ]
        )
    )
    hass.data[DOMAIN].pop(config_entry.entry_id)
    if not hass.data[DOMAIN]:
        hass.data.pop(DOMAIN)

    return unload_ok


async def alfen_setup(hass, host, name, username, password):
    """Create a Alfen instance only once."""

    session = hass.helpers.aiohttp_client.async_get_clientsession()
    try:
        with timeout(TIMEOUT):
            device = AlfenDevice(host, name, session, username, password)
            await device.init()
    except asyncio.TimeoutError:
        _LOGGER.debug("Connection to %s timed out", host)
        raise ConfigEntryNotReady
    except ClientConnectionError:
        _LOGGER.debug("ClientConnectionError to %s", host)
        raise ConfigEntryNotReady
    except Exception:  # pylint: disable=broad-except
        _LOGGER.error("Unexpected error creating device %s", host)
        return None

    return device
