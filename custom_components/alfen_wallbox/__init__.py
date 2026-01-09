"""Alfen Wallbox integration."""

import logging
from typing import Any

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_REFRESH_CATEGORIES,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
)
from .coordinator import AlfenConfigEntry, AlfenCoordinator, options_update_listener

PLATFORMS = [
    Platform.BINARY_SENSOR,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
    Platform.TEXT,
]

_LOGGER = logging.getLogger(__name__)


async def async_migrate_entry(
    hass: HomeAssistant, config_entry: AlfenConfigEntry
) -> bool:
    """Migrate old entry."""
    name = config_entry.data.get(CONF_NAME, "Unknown")
    host = config_entry.data.get(CONF_HOST, "Unknown")
    log_id = f"{name}@{host}"

    _LOGGER.debug("[%s] Migrating from version %s", log_id, config_entry.version)

    if config_entry.version == 1:
        scan_interval = config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        options = {
            CONF_SCAN_INTERVAL: scan_interval,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_REFRESH_CATEGORIES: DEFAULT_REFRESH_CATEGORIES,
        }
        data = {
            CONF_HOST: config_entry.data.get(CONF_HOST),
            CONF_NAME: config_entry.data.get(CONF_NAME),
            CONF_USERNAME: config_entry.data.get(CONF_USERNAME),
            CONF_PASSWORD: config_entry.data.get(CONF_PASSWORD),
        }

        hass.config_entries.async_update_entry(
            config_entry,
            version=2,
            data=data,
            options=options,
        )

        _LOGGER.debug("[%s] Migration to version %s successful", log_id, config_entry.version)

    return True


async def async_setup_entry(
    hass: HomeAssistant, config_entry: AlfenConfigEntry
) -> bool:
    """Set up Alfen from a config entry."""
    await er.async_migrate_entries(
        hass, config_entry.entry_id, async_migrate_entity_entry
    )

    coordinator = AlfenCoordinator(hass, config_entry)
    await coordinator.async_config_entry_first_refresh()

    config_entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(config_entry, PLATFORMS)

    config_entry.async_on_unload(
        config_entry.add_update_listener(options_update_listener)
    )
    return True


async def async_unload_entry(
    hass: HomeAssistant, config_entry: AlfenConfigEntry
) -> bool:
    """Unload a config entry."""
    coordinator = config_entry.runtime_data
    _LOGGER.debug("[%s] async_unload_entry", coordinator.device.log_id)

    await coordinator.device.logout()

    # Close the dedicated ClientSession
    if coordinator._session and not coordinator._session.closed:
        await coordinator._session.close()

    return await hass.config_entries.async_unload_platforms(config_entry, PLATFORMS)


@callback
def async_migrate_entity_entry(
    entity_entry: er.RegistryEntry,
) -> dict[str, Any] | None:
    """Migrate a Alfen entity entry."""

    # Migrate uptime_hours sensor to add device_class: duration (2025-11-03)
    if (
        entity_entry.domain == "sensor"
        and entity_entry.unique_id.endswith("_uptime_hours")
        and entity_entry.device_class != "duration"
    ):
        _LOGGER.debug(
            "Migrating %s to add device_class=duration", entity_entry.entity_id
        )
        return {"device_class": "duration"}

    # Remove device_class from uptime sensor (it returns a string, not numeric) (2025-11-03)
    if (
        entity_entry.domain == "sensor"
        and entity_entry.unique_id.endswith("_uptime")
        and not entity_entry.unique_id.endswith("_uptime_hours")  # Don't match uptime_hours
        and entity_entry.device_class == "duration"
    ):
        _LOGGER.debug(
            "Migrating %s to remove device_class (returns string not numeric)", entity_entry.entity_id
        )
        return {"device_class": None}

    return None
