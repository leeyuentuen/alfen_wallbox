"""Test the Alfen Wallbox sensor platform."""

from unittest.mock import MagicMock

import pytest

from custom_components.alfen_wallbox.const import DOMAIN, ID, VALUE
from custom_components.alfen_wallbox.sensor import (
    ALFEN_SENSOR_TYPES,
    AlfenMainSensor,
    AlfenSensor,
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
        "2501_2": {ID: "2501_2", VALUE: 11, "cat": "states"},
        "2060_0": {ID: "2060_0", VALUE: 3600000, "cat": "generic"},  # 1 hour in ms
        "2221_22": {ID: "2221_22", VALUE: 15500, "cat": "meter1"},  # 15.5 kWh in W
        "2511_3": {ID: "2511_3", VALUE: 5000, "cat": "states"},  # 50% duty cycle
        "2187_0": {ID: "2187_0", VALUE: 1705334400000, "cat": "generic"},  # timestamp
        "2059_0": {ID: "2059_0", VALUE: 1705334400000, "cat": "generic"},
        "312E_0": {ID: "312E_0", VALUE: 3, "cat": "generic2"},
        "2501_4": {ID: "2501_4", VALUE: 193, "cat": "states"},
        "2501_3": {ID: "2501_3", VALUE: 5, "cat": "states"},
        "2501_1": {ID: "2501_1", VALUE: 14, "cat": "states"},
        "3600_1": {ID: "3600_1", VALUE: 3, "cat": "ocpp"},
        "2540_0": {ID: "2540_0", VALUE: 2, "cat": "MbusTCP"},
        "3190_1": {ID: "3190_1", VALUE: 11, "cat": "display"},
        "3190_2": {ID: "3190_2", VALUE: 0, "cat": "display"},
        "205E_0": {ID: "205E_0", VALUE: 1, "cat": "generic"},
        "5221_3": {ID: "5221_3", VALUE: 230.0, "cat": "meter2"},
        "5221_4": {ID: "5221_4", VALUE: 230.0, "cat": "meter2"},
        "5221_5": {ID: "5221_5", VALUE: 230.0, "cat": "meter2"},
        "212F_1": {ID: "212F_1", VALUE: 10.0, "cat": "meter1"},
        "212F_2": {ID: "212F_2", VALUE: 10.0, "cat": "meter1"},
        "212F_3": {ID: "212F_3", VALUE: 10.0, "cat": "meter1"},
    }
    coordinator.device.latest_tag = None
    coordinator.device.get_number_of_sockets = MagicMock(return_value=1)
    coordinator.device.device_info = {
        "identifiers": {(DOMAIN, "test")},
        "name": "Test Wallbox",
    }
    mock_entry.runtime_data = coordinator
    return coordinator


async def test_sensor_setup(hass, mock_entry, mock_coordinator):
    """Test sensor entity setup."""
    async_add_entities = MagicMock()

    await async_setup_entry(hass, mock_entry, async_add_entities)

    assert async_add_entities.called


async def test_sensor_uptime_conversion(mock_entry, mock_coordinator):
    """Test uptime sensor converts milliseconds to HH:MM:SS."""
    uptime_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "uptime")
    entity = AlfenSensor(mock_entry, uptime_desc)

    value = entity.native_value

    # 3600000 ms = 1 hour
    assert value == "1:00:00"


async def test_sensor_uptime_seconds(mock_entry, mock_coordinator):
    """Test uptime seconds sensor."""
    # Set uptime to 2 hours 30 minutes (9000 seconds = 9000000 milliseconds)
    mock_coordinator.device.properties["2060_0"] = {
        ID: "2060_0",
        VALUE: 9000000,  # 9000 seconds in milliseconds
        "cat": "generic",
    }

    uptime_seconds_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "uptime_seconds")
    entity = AlfenSensor(mock_entry, uptime_seconds_desc)

    value = entity.native_value

    # 9000000 ms / 1000 = 9000 seconds
    assert value == 9000


async def test_sensor_uptime_hours(mock_entry, mock_coordinator):
    """Test uptime hours sensor."""
    # Set uptime to 2 days + 5 hours
    mock_coordinator.device.properties["2060_0"] = {
        ID: "2060_0",
        VALUE: (2 * 24 * 60 * 60 * 1000) + (5 * 60 * 60 * 1000),
        "cat": "generic",
    }

    uptime_hours_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "uptime_hours")
    entity = AlfenSensor(mock_entry, uptime_hours_desc)

    value = entity.native_value

    # 2 days * 24 + 5 hours = 53 hours
    assert value == 53


async def test_sensor_meter_reading_conversion(mock_entry, mock_coordinator):
    """Test meter reading converts W to kWh."""
    meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "meter_reading_socket_1")
    entity = AlfenSensor(mock_entry, meter_desc)

    value = entity.native_value

    # 15500 W / 1000 = 15.5 kWh
    assert value == 15.5


async def test_sensor_pwm_duty_cycle(mock_entry, mock_coordinator):
    """Test PWM duty cycle converts to percentage."""
    pwm_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "comm_car_pwm_duty_cycle_socket_1")
    entity = AlfenSensor(mock_entry, pwm_desc)

    value = entity.native_value

    # 5000 / 100 = 50%
    assert value == 50.0


async def test_sensor_timestamp_conversion(mock_entry, mock_coordinator):
    """Test timestamp sensors convert to datetime."""
    last_modify_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "last_modify_datetime")
    entity = AlfenSensor(mock_entry, last_modify_desc)

    value = entity.native_value

    # Should be formatted as DD/MM/YYYY HH:MM:SS
    assert "/" in value
    assert ":" in value


async def test_sensor_allowed_phase_dict(mock_entry, mock_coordinator):
    """Test allowed phase dictionary lookup."""
    phase_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "ps_connector_1_max_allowed_phase"
    )
    entity = AlfenSensor(mock_entry, phase_desc)

    value = entity.native_value

    # 3 should map to "3 Phases"
    assert value == "3 Phases"


async def test_sensor_mode3_state(mock_entry, mock_coordinator):
    """Test mode 3 state dictionary lookup."""
    mode3_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "mode_3_state_socket_1")
    entity = AlfenSensor(mock_entry, mode3_desc)

    value = entity.native_value

    # 193 should map to a state
    assert isinstance(value, str)


async def test_sensor_power_state(mock_entry, mock_coordinator):
    """Test power state dictionary lookup."""
    power_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "power_state_socket_1")
    entity = AlfenSensor(mock_entry, power_desc)

    value = entity.native_value

    # 5 should map to "Active"
    assert value == "Active"


async def test_sensor_main_state(mock_entry, mock_coordinator):
    """Test main state dictionary lookup."""
    main_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "main_state_socket_1")
    entity = AlfenSensor(mock_entry, main_desc)

    value = entity.native_value

    # 14 should map to a state
    assert isinstance(value, str)


async def test_sensor_ocpp_boot_status(mock_entry, mock_coordinator):
    """Test OCPP boot notification status."""
    ocpp_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "ocpp_boot_notification_state")
    entity = AlfenSensor(mock_entry, ocpp_desc)

    value = entity.native_value

    # 3 should map to "Accepted"
    assert value == "Accepted"


async def test_sensor_modbus_connection_state(mock_entry, mock_coordinator):
    """Test Modbus connection state."""
    modbus_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "modbus_tcp_ip_connection_state"
    )
    entity = AlfenSensor(mock_entry, modbus_desc)

    value = entity.native_value

    # 2 should map to "Normal"
    assert value == "Normal"


async def test_sensor_display_state(mock_entry, mock_coordinator):
    """Test display state sensor."""
    display_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "ui_state_1")
    entity = AlfenSensor(mock_entry, display_desc)

    value = entity.native_value

    # 11 should map to "Charging Normal"
    assert value == "Charging Normal"


async def test_sensor_display_state_error(mock_entry, mock_coordinator):
    """Test display state with error."""
    mock_coordinator.device.properties["3190_1"] = {ID: "3190_1", VALUE: 28, "cat": "display"}

    display_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "ui_state_1")
    entity = AlfenSensor(mock_entry, display_desc)

    value = entity.native_value

    assert value == "See error Number"


async def test_sensor_display_error_number(mock_entry, mock_coordinator):
    """Test display error number formatting."""
    error_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "ui_error_number_1")
    entity = AlfenSensor(mock_entry, error_desc)

    value = entity.native_value

    # Should be formatted as "0: No Error"
    assert ":" in value
    assert "No Error" in value


async def test_sensor_status_dict(mock_entry, mock_coordinator):
    """Test status code dictionary lookup."""
    status_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "status_socket_1")
    entity = AlfenSensor(mock_entry, status_desc)

    value = entity.native_value

    # 11 should map to "Charging Normal"
    assert value == "Charging Normal"


async def test_sensor_smart_meter_l1(mock_entry, mock_coordinator):
    """Test smart meter L1 power calculation."""
    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_l1")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    # 230V * 10A = 2300W
    assert value == 2300.0


async def test_sensor_smart_meter_l2(mock_entry, mock_coordinator):
    """Test smart meter L2 power calculation."""
    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_l2")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    assert value == 2300.0


async def test_sensor_smart_meter_l3(mock_entry, mock_coordinator):
    """Test smart meter L3 power calculation."""
    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_l3")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    assert value == 2300.0


async def test_sensor_smart_meter_total(mock_entry, mock_coordinator):
    """Test smart meter total power calculation."""
    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_total")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    # (230 * 10) * 3 phases = 6900W
    assert value == 6900.0


async def test_sensor_transaction_no_tag(mock_entry, mock_coordinator):
    """Test transaction sensor with no tag data."""
    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charging"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # Should return None when no latest_tag
    assert value is None


async def test_sensor_transaction_charging_kwh(mock_entry, mock_coordinator):
    """Test transaction charging kWh calculation."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "start", "kWh"): "10.5",
        ("socket 1", "mv", "kWh"): "15.5",
    }

    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charging"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # 15.5 - 10.5 = 5.0
    assert value == 5.0


async def test_sensor_transaction_charging_stopped(mock_entry, mock_coordinator):
    """Test transaction charging when stopped."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "start", "kWh"): "10.5",
        ("socket 1", "mv", "kWh"): "15.5",
        ("socket 1", "stop", "kWh"): "16.0",  # Stop >= mv means charging stopped
    }

    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charging"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # Should return 0 when stopped
    assert value == 0


async def test_sensor_transaction_last_charge_kwh(mock_entry, mock_coordinator):
    """Test transaction last charge kWh calculation."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "last_start", "kWh"): "10.0",
        ("socket 1", "stop", "kWh"): "25.5",
    }

    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charged"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # 25.5 - 10.0 = 15.5
    assert value == 15.5


async def test_sensor_transaction_charging_time(mock_entry, mock_coordinator):
    """Test transaction charging time calculation."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "start", "date"): "2024-01-15 10:00:00",
        ("socket 1", "mv", "date"): "2024-01-15 11:30:00",
    }

    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charging_time"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # 1.5 hours = 90 minutes
    assert value == 90.0


async def test_sensor_transaction_charging_time_stopped(mock_entry, mock_coordinator):
    """Test transaction charging time when stopped."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "start", "date"): "2024-01-15 10:00:00",
        ("socket 1", "mv", "date"): "2024-01-15 11:30:00",
        ("socket 1", "stop", "date"): "2024-01-15 12:00:00",  # Stop > start means stopped
    }

    transaction_desc = next(
        d for d in ALFEN_SENSOR_TYPES if d.key == "custom_transaction_socket_1_charging_time"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # Should return 0 when stopped
    assert value == 0


async def test_sensor_transaction_last_charge_time(mock_entry, mock_coordinator):
    """Test transaction last charge time calculation."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "last_start", "date"): "2024-01-15 10:00:00",
        ("socket 1", "stop", "date"): "2024-01-15 13:00:00",
    }

    transaction_desc = next(
        d
        for d in ALFEN_SENSOR_TYPES
        if d.key == "custom_transaction_socket_1_charged_time"
    )
    entity = AlfenSensor(mock_entry, transaction_desc)

    value = entity.native_value

    # 3 hours = 180 minutes
    assert value == 180.0


async def test_sensor_tag_socket_1(mock_entry, mock_coordinator):
    """Test tag sensor for socket 1."""
    mock_coordinator.device.latest_tag = {
        ("socket 1", "start", "tag"): "ABC123",
    }

    tag_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "custom_tag_socket_1")
    entity = AlfenSensor(mock_entry, tag_desc)

    value = entity.native_value

    assert value == "ABC123"


async def test_sensor_tag_no_tag(mock_entry, mock_coordinator):
    """Test tag sensor with no tag."""
    tag_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "custom_tag_socket_1")
    entity = AlfenSensor(mock_entry, tag_desc)

    value = entity.native_value

    # Should return "No Tag" when no latest_tag
    assert value == "No Tag"


async def test_sensor_extra_state_attributes(mock_entry, mock_coordinator):
    """Test extra state attributes."""
    description = ALFEN_SENSOR_TYPES[0]
    entity = AlfenSensor(mock_entry, description)

    attrs = entity.extra_state_attributes

    assert attrs is not None
    assert "category" in attrs


async def test_sensor_missing_property(mock_entry, mock_coordinator):
    """Test sensor with missing property."""
    mock_coordinator.device.properties = {}

    description = ALFEN_SENSOR_TYPES[0]
    entity = AlfenSensor(mock_entry, description)

    value = entity.native_value

    assert value is None




async def test_sensor_dict_lookup_invalid_value(mock_entry, mock_coordinator):
    """Test dict lookup with invalid value."""
    mock_coordinator.device.properties["2501_2"] = {ID: "2501_2", VALUE: 9999, "cat": "states"}

    status_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "status_socket_1")
    entity = AlfenSensor(mock_entry, status_desc)

    value = entity.native_value

    # Should handle unknown status code
    assert isinstance(value, (str, int))


async def test_sensor_smart_meter_zero_voltage(mock_entry, mock_coordinator):
    """Test smart meter with zero voltage."""
    mock_coordinator.device.properties["5221_3"] = {ID: "5221_3", VALUE: 0.0, "cat": "meter2"}
    mock_coordinator.device.properties["212F_1"] = {ID: "212F_1", VALUE: 10.0, "cat": "meter1"}

    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_l1")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    # 0V * 10A = 0W
    assert value == 0.0


async def test_sensor_smart_meter_zero_current(mock_entry, mock_coordinator):
    """Test smart meter with zero current."""
    mock_coordinator.device.properties["5221_3"] = {ID: "5221_3", VALUE: 230.0, "cat": "meter2"}
    mock_coordinator.device.properties["212F_1"] = {ID: "212F_1", VALUE: 0.0, "cat": "meter1"}

    smart_meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "smart_meter_l1")
    entity = AlfenSensor(mock_entry, smart_meter_desc)

    value = entity.native_value

    # 230V * 0A = 0W
    assert value == 0.0


async def test_sensor_uptime_zero(mock_entry, mock_coordinator):
    """Test uptime sensor with zero value."""
    mock_coordinator.device.properties["2060_0"] = {ID: "2060_0", VALUE: 0, "cat": "generic"}

    uptime_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "uptime")
    entity = AlfenSensor(mock_entry, uptime_desc)

    value = entity.native_value

    assert value == "0:00:00"


async def test_sensor_meter_reading_zero(mock_entry, mock_coordinator):
    """Test meter reading with zero value."""
    mock_coordinator.device.properties["2221_22"] = {ID: "2221_22", VALUE: 0, "cat": "meter1"}

    meter_desc = next(d for d in ALFEN_SENSOR_TYPES if d.key == "meter_reading_socket_1")
    entity = AlfenSensor(mock_entry, meter_desc)

    value = entity.native_value

    assert value == 0.0


async def test_main_sensor_name_includes_device_prefix(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor name includes device prefix."""
    status_desc = ALFEN_SENSOR_TYPES[0]  # "status_socket_1"
    entity = AlfenMainSensor(mock_entry, status_desc)

    # Name should include device name prefix
    assert entity.name == "Test Wallbox Status Code Socket 1"
    assert entity._attr_name == "Test Wallbox Status Code Socket 1"


async def test_main_sensor_unique_id(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor has correct unique_id."""
    status_desc = ALFEN_SENSOR_TYPES[0]
    entity = AlfenMainSensor(mock_entry, status_desc)

    # Unique ID should be device_id-sensor
    assert entity.unique_id == "alfen_test-sensor"


async def test_main_sensor_state_value(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor returns correct state value."""
    status_desc = ALFEN_SENSOR_TYPES[0]
    entity = AlfenMainSensor(mock_entry, status_desc)

    # State should be "Charging Normal" (status code 11)
    assert entity.state == "Charging Normal"


async def test_main_sensor_icon(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor has correct icon."""
    status_desc = ALFEN_SENSOR_TYPES[0]
    entity = AlfenMainSensor(mock_entry, status_desc)

    assert entity.icon == "mdi:car-electric"


async def test_main_sensor_extra_state_attributes(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor returns extra state attributes."""
    status_desc = ALFEN_SENSOR_TYPES[0]
    entity = AlfenMainSensor(mock_entry, status_desc)

    attrs = entity.extra_state_attributes

    assert attrs is not None
    assert "category" in attrs
    assert attrs["category"] == "states"


async def test_main_sensor_naming_consistency_with_alfen_sensor(mock_entry, mock_coordinator):
    """Test that AlfenMainSensor naming is consistent with AlfenSensor."""
    status_desc = ALFEN_SENSOR_TYPES[0]

    main_sensor = AlfenMainSensor(mock_entry, status_desc)
    regular_sensor = AlfenSensor(mock_entry, status_desc)

    # Both should include device name prefix
    assert "Test Wallbox" in main_sensor.name
    assert "Test Wallbox" in regular_sensor.name

    # Both should have the description name in their name
    assert "Status Code Socket 1" in main_sensor.name
    assert "Status Code Socket 1" in regular_sensor.name
