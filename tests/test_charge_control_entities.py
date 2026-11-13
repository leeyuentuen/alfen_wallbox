"""Tests for the charge control, maximum power and schedule entities."""

from unittest.mock import AsyncMock, MagicMock

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.alfen_wallbox.alfen import ChargingProfileError
from custom_components.alfen_wallbox.charging import TimeSlot
from custom_components.alfen_wallbox.number import AlfenMaxPowerNumber
from custom_components.alfen_wallbox.select import AlfenChargeControlSelect
from custom_components.alfen_wallbox.sensor import AlfenScheduleDaySensor
from custom_components.alfen_wallbox.switch import AlfenChargingScheduleSwitch

# Flat-array layout as returned by the wallbox for a Monday day profile:
# one slot 10:00-16:00 at 10.4 A on one phase (2.4 kW)
MONDAY_PROFILE = {
    "chargingProfileId": 234202401,
    "chargingProfileKind": "Recurring",
    "recurrencyKind": "Weekly",
    "startPeriod": [0, 1, 36000, 57600],
    "limit": [0.0, 0.0, 10.4, 0.0],
    "numberPhases": [1, 1, 1, 1],
}


@pytest.fixture(name="entry")
def entry_fixture():
    """Config entry whose coordinator has a mocked device."""
    entry = MagicMock()
    device = MagicMock()
    device.id = "alfen_test"
    device.name = "Test Wallbox"
    device.charging_profiles = []
    entry.runtime_data.device = device
    return entry


async def test_charge_control_select(entry):
    """The select reflects pause / boost and switches between them."""
    device = entry.runtime_data.device
    device.charge_control = "charging"
    device.boost_ends_at = None
    device.set_charge_control = AsyncMock()
    select = AlfenChargeControlSelect(entry)

    assert select.unique_id == "alfen_test_charge_control"
    assert select.options == ["Charging", "Paused", "Boost"]
    assert select.current_option == "Charging"
    device.charge_control = "boost"
    assert select.current_option == "Boost"

    await select.async_select_option("Paused")
    device.set_charge_control.assert_awaited_once_with("paused")

    device.set_charge_control = AsyncMock(side_effect=ChargingProfileError("Wallbox rejected add"))
    with pytest.raises(HomeAssistantError, match="rejected"):
        await select.async_select_option("Boost")


async def test_max_power_number(entry):
    """The number shows the preferred maximum (or the station maximum) in kW."""
    device = entry.runtime_data.device
    device.min_station_power = 1.4
    device.max_station_power = 11.0
    device.max_power = None
    device.active_phases = 3
    device.set_max_power = AsyncMock()
    number = AlfenMaxPowerNumber(entry)

    assert (number.native_min_value, number.native_max_value) == (1.4, 11.0)
    assert number.native_value == 11.0  # not limited
    device.max_power = 7.4
    assert number.native_value == 7.4
    assert number.extra_state_attributes == {"limited": True, "active_phases": 3}

    await number.async_set_native_value(5.0)
    device.set_max_power.assert_awaited_once_with(5.0)


async def test_schedule_switch_and_services(entry):
    """The schedule switch toggles the schedule and serves the schedule services."""
    device = entry.runtime_data.device
    device.schedule_enabled = False
    device.get_schedule = MagicMock(return_value={day: [] for day in range(7)})
    device.set_schedule_enabled = AsyncMock()
    device.make_timeslot = MagicMock(side_effect=lambda **kwargs: kwargs)
    device.add_schedule_slot = AsyncMock()
    device.set_schedule_day = AsyncMock()
    device.clear_schedule = AsyncMock()
    switch = AlfenChargingScheduleSwitch(entry)

    assert switch.is_on is False
    await switch.async_turn_on()
    device.set_schedule_enabled.assert_awaited_once_with(True)

    await switch.async_add_schedule_timeslot("22:00", "06:00", days=["Monday", "Friday"], max_power=7.4)
    weekdays, slot = device.add_schedule_slot.call_args.args
    assert weekdays == [0, 4]
    assert slot == {"start": 79200, "end": 21600, "power_kw": 7.4, "current": None}
    assert device.add_schedule_slot.call_args.kwargs == {"replace": False}

    await switch.async_set_schedule_day("Sunday", [{"start": "01:00", "end": "05:00", "max_current": 10}])
    weekday, slots = device.set_schedule_day.call_args.args
    assert weekday == 6
    assert slots == [{"start": 3600, "end": 18000, "power_kw": None, "current": 10}]

    await switch.async_clear_charging_schedule(["Saturday"])
    device.clear_schedule.assert_awaited_with([5])
    await switch.async_clear_charging_schedule()
    device.clear_schedule.assert_awaited_with(None)

    device.add_schedule_slot = AsyncMock(side_effect=ChargingProfileError("conflicts"))
    with pytest.raises(HomeAssistantError, match="conflicts"):
        await switch.async_add_schedule_timeslot("10:00", "11:00")
    with pytest.raises(HomeAssistantError):
        await switch.async_add_schedule_timeslot("25:00", "11:00")


def test_schedule_day_sensor(entry):
    """Day sensors list the slots of their weekday with the power."""
    entry.runtime_data.device.charging_profiles = [MONDAY_PROFILE]
    monday = AlfenScheduleDaySensor(entry, "Monday", 0)
    tuesday = AlfenScheduleDaySensor(entry, "Tuesday", 1)
    assert monday.native_value == "10:00-16:00 (2.4 kW)"
    assert monday.extra_state_attributes["slots"][0]["current_a"] == 10.4
    assert tuesday.native_value == "No schedule"
    assert tuesday.extra_state_attributes == {"scheduled": False, "slots": []}


def test_timeslot_power():
    """A slot's power follows amps x phases x 230 V."""
    assert TimeSlot(0, 3600, 16, 3).power_kw == 11.0
