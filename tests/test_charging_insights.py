"""Tests for the charging insight sensors (status, limit, session, solar split)."""

import datetime
from unittest.mock import MagicMock

import pytest

from custom_components.alfen_wallbox import charging_insights
from custom_components.alfen_wallbox.binary_sensor import AlfenChargingRestrictedBinarySensor
from custom_components.alfen_wallbox.charging_insights import ChargingSession
from custom_components.alfen_wallbox.const import ID, VALUE
from custom_components.alfen_wallbox.sensor import (
    SESSION_SENSOR_KINDS,
    SOLAR_SPLIT_SENSORS,
    AlfenChargingLimitSensor,
    AlfenChargingStatusSensor,
    AlfenSessionSensor,
    AlfenSolarSplitSensor,
)


def _props(**values):
    return {key: {ID: key, VALUE: value, "cat": "x"} for key, value in values.items()}


@pytest.fixture(name="mock_entry")
def mock_entry_fixture():
    """Mock config entry with a coordinator and device."""
    entry = MagicMock()
    device = MagicMock()
    device.id = "alfen_test"
    device.name = "Test Wallbox"
    device.properties = {}
    device.session = ChargingSession()
    entry.runtime_data.device = device
    return entry


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def test_main_state_table_complete():
    """Every socket main state (-1..55) has a message."""
    assert set(charging_insights.SOCKET_MAIN_STATE) == set(range(-1, 56))


@pytest.mark.parametrize(
    ("properties", "expected"),
    [
        ({"2501_1": 2}, "Charging station is available."),
        ({"2501_1": 14}, "Charging session active."),
        ({"2501_1": 14, "3280_1": 2}, "Solar charging using green mode."),
        ({"2501_1": 14, "3280_1": 1}, "Solar charging using comfort mode."),
        ({"2501_1": 11, "2062_0": 0}, "Charging session has been paused."),
        ({"2501_1": 2, "2062_0": 0}, "Charging station is available."),  # nothing connected
        ({"2501_1": 99}, "Status unknown, please wait..."),
        ({}, None),
    ],
)
def test_charging_status(properties, expected):
    """Status text follows the main state, the solar mode and a paused station."""
    assert charging_insights.charging_status(_props(**properties)) == expected


def test_limiting_factor_decoding():
    """Single flags and combined bitmasks are decoded and grouped."""
    assert charging_insights.decode_limiting_factor(8) == [8]
    assert charging_insights.limiting_group([8]) == "vehicle"
    assert charging_insights.limiting_group([32768]) == "load_balancing"
    assert charging_insights.limiting_group([128]) == "installation"
    assert charging_insights.limiting_group([1]) is None  # configured maximum
    assert charging_insights.decode_limiting_factor(1 | 64) == [1, 64]
    assert charging_insights.decode_limiting_factor("x") == []
    assert charging_insights.decode_limiting_factor(0) == []


def test_solar_grid_split():
    """Exporting -> all solar; importing -> the import is grid."""
    assert charging_insights.solar_grid_split(7000, -2500) == (7000, 0)
    assert charging_insights.solar_grid_split(7000, 3000) == (4000, 3000)
    assert charging_insights.solar_grid_split(7000, 9000) == (0, 7000)
    assert charging_insights.solar_grid_split(0, -2500) == (0, 0)
    assert charging_insights.solar_grid_split(7000, None) == (0, 0)


def test_session_lifecycle_and_green_share():
    """A session starts on connect, accumulates energy and ends on disconnect."""
    session = ChargingSession()
    t0 = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    session.update(_props(**{"2501_1": 2, "2221_22": 1_000_000}), t0)
    assert session.active is False

    props = {"2501_1": 14, "2221_22": 1_000_000, "2221_16": 4000, "5221_16": -1000}
    session.update(_props(**props), t0)
    assert session.active is True

    # 100 s all solar, then 100 s half grid
    session.update(_props(**{**props, "2221_22": 1_000_111}), t0 + datetime.timedelta(seconds=100))
    props.update({"5221_16": 2000, "2221_22": 1_000_222, "2221_16": 4000})
    session.update(_props(**props), t0 + datetime.timedelta(seconds=200))
    assert session.energy_kwh == 0.222
    assert session.max_power_w == 4000
    assert session.green_share == 75.0

    session.update(_props(**{"2501_1": 2}), t0 + datetime.timedelta(seconds=300))
    assert session.active is False
    assert session.duration_seconds == 300
    assert session.energy_kwh == 0.222  # last session stays visible


def test_session_resumes_from_transaction_log():
    """A session already running at startup uses the logged start and meter value."""
    session = ChargingSession()
    start = datetime.datetime(2026, 11, 1, 8, 0, tzinfo=datetime.UTC)
    now = start + datetime.timedelta(hours=2)
    session.update(
        _props(**{"2501_1": 14, "2221_22": 1_010_000}), now, resume_from=(start, 1_000_000)
    )
    assert session.start == start
    assert session.energy_kwh == 10.0


def test_session_gap_is_capped():
    """A long gap between updates (e.g. timeouts) does not distort the energy split."""
    session = ChargingSession()
    t0 = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    props = _props(**{"2501_1": 14, "2221_16": 3600, "5221_16": -100})
    session.update(props, t0)
    session.update(props, t0 + datetime.timedelta(hours=1))
    assert session.solar_wh == pytest.approx(3600 * charging_insights.MAX_SPLIT_INTERVAL / 3600)


# ---------------------------------------------------------------------------
# Entities
# ---------------------------------------------------------------------------


def test_charging_status_sensor(mock_entry):
    """The status sensor shows the message and exposes the raw state."""
    mock_entry.runtime_data.device.properties = _props(**{"2501_1": 14})
    sensor = AlfenChargingStatusSensor(mock_entry)
    assert sensor.unique_id == "alfen_test-charging_status"
    assert sensor.native_value == "Charging session active."
    assert sensor.extra_state_attributes == {
        "state_code": 14,
        "state": "charging_power_on",
        "vehicle_connected": True,
        "charging": True,
    }
    mock_entry.runtime_data.device.properties = {}
    assert sensor.available is False


def test_charging_limit_sensor_and_restricted_binary_sensor(mock_entry):
    """The limit sensor names the factor; the binary sensor flags real restrictions."""
    device = mock_entry.runtime_data.device
    limit = AlfenChargingLimitSensor(mock_entry)
    restricted = AlfenChargingRestrictedBinarySensor(mock_entry)
    assert limit.available is False
    assert restricted.available is False

    device.properties = _props(**{"2501_1": 14, "218F_1": 32768})
    assert limit.native_value == "alb_active"
    assert limit.extra_state_attributes == {"group": "load_balancing", "flags": [32768]}
    assert restricted.is_on is True
    assert restricted.extra_state_attributes == {"reason": "load_balancing"}

    device.properties = _props(**{"2501_1": 14, "218F_1": 1})  # configured maximum
    assert restricted.is_on is False

    device.properties = _props(**{"2501_1": 2, "218F_1": 8})  # not charging
    assert restricted.is_on is False


def test_session_sensors(mock_entry):
    """Session sensors report energy (kWh), duration (s) and peak power (kW)."""
    session = mock_entry.runtime_data.device.session
    session.start = datetime.datetime(2026, 11, 1, 10, 0, tzinfo=datetime.UTC)
    session.end = session.start + datetime.timedelta(minutes=90)
    session.energy_kwh = 12.5
    session.max_power_w = 7400
    values = {kind: AlfenSessionSensor(mock_entry, kind).native_value for kind in SESSION_SENSOR_KINDS}
    assert values == {"energy": 12.5, "duration": 5400, "max_power": 7.4}


def test_solar_split_sensors(mock_entry):
    """Solar / grid power and green share; unavailable without a smart meter."""
    device = mock_entry.runtime_data.device
    sensors = {kind: AlfenSolarSplitSensor(mock_entry, kind) for kind in SOLAR_SPLIT_SENSORS}
    assert not any(sensor.available for sensor in sensors.values())

    device.properties = _props(**{"2221_16": 7000, "5221_16": 1750})
    device.session.solar_wh, device.session.grid_wh = 3000, 1000
    assert {kind: s.native_value for kind, s in sensors.items()} == {
        "solar_power": 5250,
        "grid_power": 1750,
        "green_share": 75.0,
        "session_green_share": 75.0,
    }
    assert sensors["solar_power"].unique_id == "alfen_test-solar_charging_power"
    assert sensors["session_green_share"].extra_state_attributes == {
        "solar_kwh": 3.0,
        "grid_kwh": 1.0,
    }
