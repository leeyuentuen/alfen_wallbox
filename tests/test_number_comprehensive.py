"""Comprehensive tests for Alfen Wallbox number platform."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.alfen_wallbox.const import DOMAIN, ID, LICENSE_HIGH_POWER, VALUE
from custom_components.alfen_wallbox.number import (
    ALFEN_NUMBER_DUAL_SOCKET_TYPES,
    ALFEN_NUMBER_TYPES,
    AlfenNumber,
    async_setup_entry,
)


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
        "2129_0": {ID: "2129_0", VALUE: 16, "cat": "generic"},
        "3280_2": {ID: "3280_2", VALUE: 50, "cat": "generic2"},
        "3280_3": {ID: "3280_3", VALUE: 3000, "cat": "generic2"},
        "3262_2": {ID: "3262_2", VALUE: 1.50, "cat": "generic2"},  # Decimal value
        "3129_0": {ID: "3129_0", VALUE: 16, "cat": "generic"},  # Socket 2
    }
    coordinator.device.set_value = AsyncMock()
    coordinator.device.set_current_limit = AsyncMock()
    coordinator.device.set_green_share = AsyncMock()
    coordinator.device.set_comfort_power = AsyncMock()
    coordinator.device.get_number_of_sockets = MagicMock(return_value=1)
    coordinator.device.get_licenses = MagicMock(return_value=[])
    coordinator.device.max_allowed_phases = 3
    coordinator.device.device_info = {
        "identifiers": {(DOMAIN, "test")},
        "name": "Test Wallbox",
    }
    mock_entry.runtime_data = coordinator
    return coordinator


async def test_number_dual_socket_setup(hass, mock_entry, mock_coordinator):
    """Test number setup with dual socket wallbox."""
    mock_coordinator.device.get_number_of_sockets = MagicMock(return_value=2)

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Should be called twice - once for single socket, once for dual socket entities
    assert async_add_entities.call_count == 2


async def test_number_single_socket_setup(hass, mock_entry, mock_coordinator):
    """Test number setup with single socket wallbox."""
    mock_coordinator.device.get_number_of_sockets = MagicMock(return_value=1)

    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_entry, async_add_entities)

    # Should be called once for single socket entities only
    assert async_add_entities.call_count == 1


async def test_number_high_power_license_override(mock_entry, mock_coordinator):
    """Test that high power license overrides max current to 40A."""
    mock_coordinator.device.get_licenses = MagicMock(return_value=[LICENSE_HIGH_POWER])

    # Get current limit description
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    # Max value should be overridden to 40A
    assert entity._attr_max_value == 40
    assert entity._attr_native_max_value == 40


async def test_number_without_high_power_license(mock_entry, mock_coordinator):
    """Test that without high power license, max current stays at 16A."""
    mock_coordinator.device.get_licenses = MagicMock(return_value=[])

    # Get current limit description
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    # Max value should remain at default 16A
    assert entity._attr_max_value == 16
    assert entity._attr_native_max_value == 16


async def test_number_comfort_level_single_phase(mock_entry, mock_coordinator):
    """Test comfort level max value adjustment for single phase."""
    mock_coordinator.device.max_allowed_phases = 1

    # Get comfort level description
    comfort_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "lb_solar_charging_comfort_level")
    entity = AlfenNumber(mock_entry, comfort_desc)

    # Get value which triggers max value adjustment
    value = entity.native_value

    # For single phase, max should be adjusted to 3300
    assert entity._attr_max_value == 3300
    assert entity._attr_native_max_value == 3300


async def test_number_comfort_level_three_phase(mock_entry, mock_coordinator):
    """Test comfort level max value for three phase."""
    mock_coordinator.device.max_allowed_phases = 3

    # Get comfort level description
    comfort_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "lb_solar_charging_comfort_level")
    entity = AlfenNumber(mock_entry, comfort_desc)

    # Get value which triggers max value check
    value = entity.native_value

    # For three phase, max should remain at description default (11000)
    assert entity._attr_max_value == comfort_desc.native_max_value
    assert entity._attr_native_max_value == comfort_desc.native_max_value


async def test_number_decimal_rounding(mock_entry, mock_coordinator):
    """Test that decimal values are properly rounded."""
    # Get price description with round_digits=2
    price_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "price_start_tariff")
    entity = AlfenNumber(mock_entry, price_desc)

    value = entity.native_value

    # Value should be rounded to 2 decimal places
    assert value == 1.50
    assert isinstance(value, float)


async def test_number_async_set_native_value_integer(mock_entry, mock_coordinator):
    """Test setting integer value."""
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_set_native_value(20)

    mock_coordinator.device.set_value.assert_called_once_with("2129_0", 20)


async def test_number_async_set_native_value_rounded(mock_entry, mock_coordinator):
    """Test setting rounded decimal value."""
    price_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "price_start_tariff")
    entity = AlfenNumber(mock_entry, price_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_set_native_value(1.995)

    # Should be rounded to 2 decimal places
    mock_coordinator.device.set_value.assert_called_once_with("3262_2", 2.0)


async def test_number_async_set_current_limit_service(mock_entry, mock_coordinator):
    """Test async_set_current_limit service method."""
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_set_current_limit(25)

    mock_coordinator.device.set_current_limit.assert_called_once_with(25)


async def test_number_async_set_green_share_service(mock_entry, mock_coordinator):
    """Test async_set_green_share service method."""
    green_share_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "lb_solar_charging_green_share")
    entity = AlfenNumber(mock_entry, green_share_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_set_green_share(75)

    mock_coordinator.device.set_green_share.assert_called_once_with(75)


async def test_number_async_set_comfort_power_service(mock_entry, mock_coordinator):
    """Test async_set_comfort_power service method."""
    comfort_desc = next(d for d in ALFEN_NUMBER_TYPES if d.key == "lb_solar_charging_comfort_level")
    entity = AlfenNumber(mock_entry, comfort_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_set_comfort_power(4000)

    mock_coordinator.device.set_comfort_power.assert_called_once_with(4000)


async def test_number_async_update(mock_entry, mock_coordinator):
    """Test async_update method."""
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    with patch.object(entity, 'async_write_ha_state'):
        await entity.async_update()

    # Should update the native value
    assert entity._attr_native_value == 16


async def test_number_extra_state_attributes_available(mock_entry, mock_coordinator):
    """Test extra state attributes when property exists."""
    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    attrs = entity.extra_state_attributes

    assert attrs is not None
    assert "category" in attrs
    assert attrs["category"] == "generic"


async def test_number_extra_state_attributes_missing(mock_entry, mock_coordinator):
    """Test extra state attributes when property is missing."""
    mock_coordinator.device.properties = {}

    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    attrs = entity.extra_state_attributes

    assert attrs is None


async def test_number_native_value_missing_property(mock_entry, mock_coordinator):
    """Test native_value when property doesn't exist."""
    mock_coordinator.device.properties = {}

    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.api_param == "2129_0")
    entity = AlfenNumber(mock_entry, current_limit_desc)

    value = entity.native_value

    assert value is None


async def test_number_dual_socket_entity(mock_entry, mock_coordinator):
    """Test dual socket specific number entity."""
    # Get socket 2 description
    socket2_desc = ALFEN_NUMBER_DUAL_SOCKET_TYPES[0]
    entity = AlfenNumber(mock_entry, socket2_desc)

    value = entity.native_value

    assert value == 16
    assert entity.entity_description.api_param == "3129_0"


async def test_number_mode_slider_default(mock_entry, mock_coordinator):
    """Test that slider mode is default when custom_mode is None."""
    from homeassistant.components.number import NumberMode

    current_limit_desc = next(d for d in ALFEN_NUMBER_TYPES if d.custom_mode is None)
    entity = AlfenNumber(mock_entry, current_limit_desc)

    assert entity._attr_mode == NumberMode.SLIDER


async def test_number_mode_box_custom(mock_entry, mock_coordinator):
    """Test that custom mode is used when specified."""
    from homeassistant.components.number import NumberMode

    # Find a description with custom NumberMode.BOX
    box_mode_desc = next(d for d in ALFEN_NUMBER_TYPES if d.custom_mode == NumberMode.BOX)
    entity = AlfenNumber(mock_entry, box_mode_desc)

    assert entity._attr_mode == NumberMode.BOX
