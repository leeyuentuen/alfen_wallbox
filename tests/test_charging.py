"""Tests for the charging-profile helpers (charge control, max power, schedule)."""

from __future__ import annotations

import datetime
from zoneinfo import ZoneInfo

import pytest

from custom_components.alfen_wallbox import charging
from custom_components.alfen_wallbox.alfen import ChargingProfileError, validate_slots
from custom_components.alfen_wallbox.charging import TimeSlot


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        (4275036468, -19930828),  # max power, unsigned form
        (4275396292, -19571004),  # boost
        (4282845288, -12122008),  # pause
        (-19930828, -19930828),
        ("234202401", 234202401),
        ("nope", None),
        (None, None),
    ],
)
def test_normalize_profile_id(raw, expected):
    """Unsigned 32-bit IDs are converted to the signed IDs the app uses."""
    assert charging.normalize_profile_id(raw) == expected


@pytest.mark.parametrize(
    ("power", "phases", "expected"),
    [
        (11, 3, (15.9, 3)),
        (22.1, 3, (32.0, 3)),
        (7.4, 1, (32.2, 1)),
        (3.7, 3, (16.1, 1)),  # 5.4 A per phase < 6 A -> single phase
        (1.4, 3, (6.1, 1)),
    ],
)
def test_power_to_current(power, phases, expected):
    """kW to amps uses the app's rounding and single-phase fallback."""
    assert charging.power_to_current(power, phases) == expected


def test_current_to_power():
    """Amps x phases x 230 V."""
    assert charging.current_to_power(16, 3) == 11.0
    assert charging.current_to_power(32, 1) == 7.4


def test_active_phases():
    """Phases count when above 80 V; fall back to the installation setting."""
    assert charging.active_phases([230, 231, 229]) == 3
    assert charging.active_phases([230, 0, 0.5]) == 1
    assert charging.active_phases([], fallback=1) == 1
    assert charging.active_phases(["x"]) == 3


def test_build_schedule_day_request_matches_app_format():
    """Day profiles mirror the app: ID per weekday, stack 11-day, anchor 2024-04-0N."""
    tz = ZoneInfo("Europe/Amsterdam")
    request = charging.build_schedule_day_request(
        2, [TimeSlot(79200, 86400, 16, 3), TimeSlot(3600, 7200, 10, 1)], tz
    )
    assert request["connectorId"] == 0
    profile = request["csChargingProfiles"]
    assert profile["chargingProfileId"] == 234202403  # Wednesday
    assert profile["stackLevel"] == 8
    assert profile["chargingProfileKind"] == "Recurring"
    assert profile["recurrencyKind"] == "Weekly"
    assert profile["chargingProfilePurpose"] == "ChargingStationExternalConstraints"
    schedule = profile["chargingSchedule"]
    # Local midnight Wednesday 2024-04-03 (CEST) serialised as UTC like JS toISOString
    assert schedule["startSchedule"] == "2024-04-02T22:00:00.000Z"
    assert schedule["duration"] == 86400
    # Leading 0/1 periods mirror the app; OCPP needs the first period at 0
    assert schedule["chargingSchedulePeriod"] == [
        {"startPeriod": 0, "limit": 0, "numberPhases": 1},
        {"startPeriod": 1, "limit": 0, "numberPhases": 1},
        {"startPeriod": 3600, "limit": 10, "numberPhases": 1},
        {"startPeriod": 7200, "limit": 0, "numberPhases": 1},
        {"startPeriod": 79200, "limit": 16, "numberPhases": 3},
        {"startPeriod": 86400, "limit": 0, "numberPhases": 3},
    ]


def test_build_pause_and_apply_schedule_requests():
    """Pause = stack 1000 limit 0; apply schedule = stack 1 limit 0."""
    pause = charging.build_pause_request()["csChargingProfiles"]
    assert (pause["chargingProfileId"], pause["stackLevel"]) == (-12122008, 1000)
    apply = charging.build_apply_schedule_request()["csChargingProfiles"]
    assert (apply["chargingProfileId"], apply["stackLevel"]) == (234202408, 1)


def test_wrap_profile_request_is_idempotent():
    """Already wrapped requests are left alone."""
    wrapped = charging.wrap_profile_request({"chargingProfileId": 1})
    assert charging.wrap_profile_request(wrapped) is wrapped


EVE_RESPONSE = {
    "version": 2,
    "profile": {
        "connectorId": 0,
        "csChargingProfiles": {
            "chargingProfileId": 234202405,
            "chargingProfileKind": "Recurring",
            "recurrencyKind": "Weekly",
            "startSchedule": "2024-04-04T22:00:00.000Z",
            "startPeriod": [0, 1, 33300, 64800],
            "limit": [0.0, 0.0, 15.9, 0.0],
            "numberPhases": [1, 1, 3, 3],
        },
    },
}


def test_unwrap_and_slots_flat_format():
    """The wallbox's flat-array response becomes one 09:15-18:00 slot on Friday."""
    profile = charging.unwrap_profile(EVE_RESPONSE)
    assert profile["chargingProfileId"] == 234202405
    assert charging.profile_slots(profile) == [TimeSlot(33300, 64800, 15.9, 3)]
    assert charging.profile_weekday(profile) == 4


def test_profile_weekday_from_anchor_for_unknown_ids():
    """Non-app weekly profiles use the anchor, robust to the UTC serialisation."""
    profile = {"chargingProfileId": 5, "startSchedule": "2024-03-31T22:00:00.000Z"}
    assert charging.profile_weekday(profile) == 0  # Monday local midnight in CEST
    profile = {"chargingProfileId": 5, "startSchedule": "2024-04-01T05:00:00.000Z"}
    assert charging.profile_weekday(profile) == 0  # Monday local midnight in UTC-5


def test_schedule_from_profiles_mixed_formats():
    """Daily, weekly-with-days and Eve day profiles are combined per weekday."""
    daily = {
        "recurrencyKind": "DAILY",
        "chargingSchedule": {
            "chargingSchedulePeriod": [
                {"startPeriod": 0, "limit": 6, "numberPhases": 1},
                {"startPeriod": 3600, "limit": 0, "numberPhases": 1},
            ]
        },
    }
    weekly = {**daily, "recurrencyKind": "WEEKLY", "daysOfWeek": ["Sunday"]}
    eve = charging.unwrap_profile(EVE_RESPONSE)
    schedule = charging.schedule_from_profiles([daily, weekly, eve])
    assert len(schedule[0]) == 1
    assert len(schedule[4]) == 2  # daily + Friday profile
    assert len(schedule[6]) == 2  # daily + weekly Sunday


def test_active_slot():
    """The slot containing 'now' is returned."""
    schedule = {day: [] for day in range(7)}
    schedule[0] = [TimeSlot(3600, 7200, 16, 3)]
    monday = datetime.datetime(2024, 1, 1, 1, 30)
    assert charging.active_slot(schedule, monday) == TimeSlot(3600, 7200, 16, 3)
    assert charging.active_slot(schedule, monday.replace(hour=3)) is None


def test_boost_end_and_max_power():
    """Boost ends 3 h after its start; max power profile maps back to kW."""
    boost = {"startSchedule": "2024-01-01T10:00:00.000Z", "duration": 10800}
    assert charging.boost_end(boost) == datetime.datetime(2024, 1, 1, 13, 0, tzinfo=datetime.UTC)
    max_power = {
        "chargingProfileKind": "Relative",
        "startPeriod": [0],
        "limit": [15.9],
        "numberPhases": [3],
    }
    assert charging.max_power_from_profile(max_power) == 11.0
    assert charging.max_power_from_profile({**max_power, "chargingProfileKind": "Recurring"}) is None


def test_hhmm_conversions():
    """HH:MM parsing and formatting, including 24:00."""
    assert charging.hhmm_to_seconds("06:30") == 23400
    assert charging.hhmm_to_seconds("24:00") == 86400
    assert charging.hhmm_to_seconds(datetime.time(22, 15)) == 80100
    assert charging.seconds_to_hhmm(86400) == "24:00"
    with pytest.raises(ValueError):
        charging.hhmm_to_seconds("25:00")


def test_validate_slots():
    """Overlaps, empty slots and more than 7 slots per day are rejected."""
    validate_slots([TimeSlot(0, 3600, 16, 3), TimeSlot(3600, 7200, 16, 3)])
    with pytest.raises(ChargingProfileError, match="conflicts"):
        validate_slots([TimeSlot(0, 3600, 16, 3), TimeSlot(1800, 7200, 16, 3)])
    with pytest.raises(ChargingProfileError, match="Invalid"):
        validate_slots([TimeSlot(7200, 3600, 16, 3)])
    with pytest.raises(ChargingProfileError, match="at most 7"):
        validate_slots([TimeSlot(i * 3600, i * 3600 + 60, 16, 3) for i in range(8)])


def test_schedule_day_request_round_trips_through_wallbox_format():
    """What we send parses back to the same slots as the app's stored profile."""
    request = charging.build_schedule_day_request(0, [TimeSlot(36000, 60300, 10.4, 1)], datetime.UTC)
    periods = request["csChargingProfiles"]["chargingSchedule"]["chargingSchedulePeriod"]
    stored = {
        "startPeriod": [p["startPeriod"] for p in periods],
        "limit": [p["limit"] for p in periods],
        "numberPhases": [p["numberPhases"] for p in periods],
    }
    # Exactly the layout Eve Connect left on a real wallbox
    assert stored == {
        "startPeriod": [0, 1, 36000, 60300],
        "limit": [0, 0, 10.4, 0],
        "numberPhases": [1, 1, 1, 1],
    }
    assert charging.profile_slots(stored) == [TimeSlot(36000, 60300, 10.4, 1)]
