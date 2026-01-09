"""Test the Alfen Wallbox entity base class."""

from unittest.mock import MagicMock

import pytest

from custom_components.alfen_wallbox.const import DOMAIN
from custom_components.alfen_wallbox.entity import AlfenEntity


@pytest.fixture(name="mock_entry")
def mock_entry_fixture():
    """Mock config entry."""
    entry = MagicMock()
    entry.entry_id = "test_entry"
    entry.data = {
        "host": "192.168.1.100",
        "username": "admin",
        "password": "secret",
        "name": "Test Wallbox",
    }
    return entry


@pytest.fixture(name="mock_coordinator")
def mock_coordinator_fixture(mock_entry):
    """Mock coordinator."""
    coordinator = MagicMock()
    coordinator.device = MagicMock()
    coordinator.device.id = "alfen_test"
    coordinator.device.name = "Test Wallbox"
    coordinator.device.properties = {
        "2501_2": {"id": "2501_2", "value": 11, "cat": "states"},
    }
    coordinator.device.info = MagicMock()
    coordinator.device.info.model = "NG920"
    coordinator.device.info.firmware_version = "5.12.0"
    coordinator.device.device_info = {
        "identifiers": {(DOMAIN, "test")},
        "name": "Test Wallbox",
    }
    coordinator.last_update_success = True
    mock_entry.runtime_data = coordinator
    return coordinator


async def test_entity_available_when_coordinator_successful(mock_entry, mock_coordinator):
    """Test that entity is available when coordinator update is successful."""
    mock_coordinator.last_update_success = True

    entity = AlfenEntity(mock_entry)

    assert entity.available is True


async def test_entity_available_when_coordinator_fails(mock_entry, mock_coordinator):
    """Test that entity remains available when coordinator update fails.

    This is the key behavior - entities should remain available and show
    last known values during brief network interruptions or timeouts.
    """
    # Simulate a failed update
    mock_coordinator.last_update_success = False

    entity = AlfenEntity(mock_entry)

    # Entity should still be available to show cached data
    assert entity.available is True


async def test_entity_available_with_empty_properties(mock_entry, mock_coordinator):
    """Test that entity is available even with empty properties dict.

    This tests the edge case where no data has been fetched yet.
    """
    mock_coordinator.device.properties = {}
    mock_coordinator.last_update_success = False

    entity = AlfenEntity(mock_entry)

    # Base entity availability doesn't depend on properties
    # Individual entity types can override if they need specific properties
    assert entity.available is True


async def test_entity_device_info(mock_entry, mock_coordinator):
    """Test that entity has correct device info."""
    entity = AlfenEntity(mock_entry)

    assert entity._attr_device_info is not None
    assert entity._attr_device_info["name"] == "Test Wallbox"
    assert entity._attr_device_info["manufacturer"] == "Alfen"
    assert entity._attr_device_info["model"] == "NG920"
    assert entity._attr_device_info["sw_version"] == "5.12.0"
    assert (DOMAIN, "Test Wallbox") in entity._attr_device_info["identifiers"]


async def test_entity_device_info_without_device_info(mock_entry, mock_coordinator):
    """Test that entity handles missing device info gracefully."""
    mock_coordinator.device.info = None

    entity = AlfenEntity(mock_entry)

    assert entity._attr_device_info is not None
    assert entity._attr_device_info["name"] == "Test Wallbox"
    assert entity._attr_device_info["manufacturer"] == "Alfen"
    assert entity._attr_device_info["model"] == "Unknown"
    assert entity._attr_device_info["sw_version"] == "Unknown"


async def test_entity_coordinator_reference(mock_entry, mock_coordinator):
    """Test that entity has reference to coordinator."""
    entity = AlfenEntity(mock_entry)

    assert entity.coordinator is mock_coordinator
    assert entity.coordinator.device.name == "Test Wallbox"
