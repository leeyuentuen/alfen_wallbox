"""Test the Alfen Wallbox coordinator."""

import asyncio
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectionError
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.coordinator import AlfenCoordinator


async def test_coordinator_successful_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test successful coordinator update."""
    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device

    # Call _async_update_data directly instead of async_config_entry_first_refresh
    await coordinator._async_update_data()

    assert mock_alfen_device.async_update.called


async def test_coordinator_update_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test coordinator handles timeout without blocking."""
    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    coordinator.timeout = 1  # Short timeout for test

    # Make device update hang
    async def slow_update():
        await asyncio.sleep(10)  # Longer than coordinator timeout
        return True

    mock_alfen_device.async_update = slow_update

    # This should raise UpdateFailed due to timeout, not hang
    with pytest.raises(UpdateFailed, match="Update timed out"):
        await coordinator._async_update_data()

    # Verify no blocking sleep was called (test completes quickly)


async def test_coordinator_update_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test coordinator handles update failure."""
    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_alfen_device.async_update.return_value = False

    with pytest.raises(UpdateFailed, match="Error updating"):
        await coordinator._async_update_data()


async def test_coordinator_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles connection errors during setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.alfen_wallbox.coordinator.AlfenDevice", autospec=True
    ) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.init = AsyncMock(side_effect=ClientConnectionError())
        mock_device.log_id = "Test Wallbox@192.168.1.100"

        coordinator = AlfenCoordinator(hass, mock_config_entry)

        result = await coordinator.async_connect()

        assert result is False


async def test_coordinator_async_connect_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test coordinator handles timeout during connection."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.alfen_wallbox.coordinator.AlfenDevice", autospec=True
    ) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.log_id = "Test Wallbox@192.168.1.100"

        async def slow_init():
            await asyncio.sleep(100)
            return True

        mock_device.init.side_effect = slow_init

        coordinator = AlfenCoordinator(hass, mock_config_entry)

        result = await coordinator.async_connect()

        assert result is False


async def test_coordinator_update_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test coordinator respects configured update interval."""
    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)

    # Check default interval (20 seconds)
    assert coordinator.update_interval == timedelta(seconds=20)


async def test_coordinator_device_properties(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test coordinator exposes device properties."""
    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device

    assert coordinator.device.name == "Test Wallbox"
    assert coordinator.device.host == "192.168.1.100"
    assert coordinator.device.info.model == "Test Model"


async def test_coordinator_options_update_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test coordinator responds to options updates."""
    from homeassistant.const import CONF_SCAN_INTERVAL

    from custom_components.alfen_wallbox.coordinator import options_update_listener

    mock_config_entry.add_to_hass(hass)

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Update options
    new_options = mock_config_entry.options.copy()
    new_options[CONF_SCAN_INTERVAL] = 10

    hass.config_entries.async_update_entry(mock_config_entry, options=new_options)

    # Call options update listener
    await options_update_listener(hass, mock_config_entry)

    # Verify interval was updated
    assert coordinator.update_interval == timedelta(seconds=10)
    assert coordinator.device.get_static_properties is True


async def test_coordinator_setup_creates_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_aiohttp_session,
    mock_ssl_context,
) -> None:
    """Test coordinator creates AlfenDevice on setup."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.alfen_wallbox.coordinator.AlfenDevice", autospec=True
    ) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.init = AsyncMock(return_value=True)

        coordinator = AlfenCoordinator(hass, mock_config_entry)
        await coordinator._async_setup()

        # Verify device was created with correct parameters
        mock_device_class.assert_called_once()
        assert coordinator.device == mock_device
