"""Test the Alfen Wallbox integration initialization."""

from unittest.mock import AsyncMock, Mock, patch

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox import async_migrate_entity_entry
from custom_components.alfen_wallbox.const import DOMAIN


async def test_setup_entry_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test successful setup of a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert mock_config_entry.runtime_data is not None
    assert hasattr(mock_config_entry.runtime_data, "device")


async def test_setup_entry_device_init_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test setup failure when device initialization fails."""
    mock_alfen_device.init.return_value = False
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test unloading a config entry."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    mock_alfen_device.logout.assert_called_once()


async def test_config_entry_migration_v1_to_v2(
    hass: HomeAssistant,
) -> None:
    """Test migration from version 1 to version 2."""
    # Create v1 config entry with scan_interval in data
    v1_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Wallbox",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_SCAN_INTERVAL: 10,  # This should move to options
        },
    )
    v1_entry.add_to_hass(hass)

    with patch(
        "custom_components.alfen_wallbox.coordinator.AlfenDevice", autospec=True
    ) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.init = AsyncMock(return_value=True)
        mock_device.async_update = AsyncMock(return_value=True)
        mock_device.get_static_properties = False

        assert await hass.config_entries.async_setup(v1_entry.entry_id)
        await hass.async_block_till_done()

    # Check migration occurred
    assert v1_entry.version == 2
    assert CONF_SCAN_INTERVAL not in v1_entry.data
    assert CONF_SCAN_INTERVAL in v1_entry.options
    assert v1_entry.options[CONF_SCAN_INTERVAL] == 10


async def test_platforms_loaded(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test that all platforms are loaded."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups"
    ) as mock_forward:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify platforms were set up
        mock_forward.assert_called_once()
        platforms_arg = mock_forward.call_args[0][1]

        expected_platforms = [
            Platform.BINARY_SENSOR,
            Platform.BUTTON,
            Platform.NUMBER,
            Platform.SELECT,
            Platform.SENSOR,
            Platform.SWITCH,
            Platform.TEXT,
        ]

        assert set(platforms_arg) == set(expected_platforms)


async def test_update_listener_registered(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test that update listener is registered."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify update listener was added
    assert len(mock_config_entry.update_listeners) > 0


async def test_entity_migration_uptime_hours(hass: HomeAssistant) -> None:
    """Test entity migration adds device_class to uptime_hours sensor."""
    # Create a mock entity entry for uptime_hours sensor without device_class
    mock_entry = Mock(spec=er.RegistryEntry)
    mock_entry.entity_id = "sensor.test_wallbox_uptime_hours"
    mock_entry.unique_id = "test_wallbox_uptime_hours"
    mock_entry.platform = DOMAIN
    mock_entry.domain = "sensor"
    mock_entry.device_class = None  # No device_class set

    # Call migration function
    result = async_migrate_entity_entry(mock_entry)

    # Verify migration adds device_class
    assert result is not None
    assert result == {"device_class": "duration"}


async def test_entity_migration_uptime_hours_already_migrated(
    hass: HomeAssistant,
) -> None:
    """Test entity migration skips already migrated uptime_hours sensor."""
    # Create a mock entity entry with device_class already set
    mock_entry = Mock(spec=er.RegistryEntry)
    mock_entry.entity_id = "sensor.test_wallbox_uptime_hours"
    mock_entry.unique_id = "test_wallbox_uptime_hours"
    mock_entry.platform = DOMAIN
    mock_entry.domain = "sensor"
    mock_entry.device_class = "duration"  # Already has device_class

    # Call migration function
    result = async_migrate_entity_entry(mock_entry)

    # Verify no migration needed
    assert result is None


async def test_entity_migration_uptime_removes_device_class(hass: HomeAssistant) -> None:
    """Test entity migration removes device_class from uptime sensor (returns string)."""
    # Create a mock entity entry for uptime sensor WITH device_class (from earlier version)
    mock_entry = Mock(spec=er.RegistryEntry)
    mock_entry.entity_id = "sensor.test_wallbox_uptime"
    mock_entry.unique_id = "test_wallbox_uptime"
    mock_entry.platform = DOMAIN
    mock_entry.domain = "sensor"
    mock_entry.device_class = "duration"  # Has device_class but shouldn't

    # Call migration function
    result = async_migrate_entity_entry(mock_entry)

    # Verify migration removes device_class
    assert result is not None
    assert result == {"device_class": None}


async def test_entity_migration_uptime_without_device_class(
    hass: HomeAssistant,
) -> None:
    """Test entity migration skips uptime sensor without device_class."""
    # Create a mock entity entry without device_class (correct state)
    mock_entry = Mock(spec=er.RegistryEntry)
    mock_entry.entity_id = "sensor.test_wallbox_uptime"
    mock_entry.unique_id = "test_wallbox_uptime"
    mock_entry.platform = DOMAIN
    mock_entry.domain = "sensor"
    mock_entry.device_class = None  # Correct - no device_class

    # Call migration function
    result = async_migrate_entity_entry(mock_entry)

    # Verify no migration needed
    assert result is None


async def test_entity_migration_other_sensors(hass: HomeAssistant) -> None:
    """Test entity migration skips other sensors."""
    # Create a mock entity entry for a different sensor
    mock_entry = Mock(spec=er.RegistryEntry)
    mock_entry.entity_id = "sensor.test_wallbox_temperature"
    mock_entry.unique_id = "test_wallbox_temperature"
    mock_entry.platform = DOMAIN
    mock_entry.domain = "sensor"
    mock_entry.device_class = None

    # Call migration function
    result = async_migrate_entity_entry(mock_entry)

    # Verify no migration for other sensors
    assert result is None
