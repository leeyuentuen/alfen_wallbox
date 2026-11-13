"""Charging-profile helpers: charge control, maximum power and weekly schedule.

Pure Python (no Home Assistant imports) so it can be unit tested in isolation.
The request formats, profile IDs, stack levels and the power/phase maths match
the Alfen Eve Connect app, so profiles written by Home Assistant are shown in the
app and vice versa.
"""

from __future__ import annotations

from dataclasses import dataclass
import datetime
from typing import Any

from .const import (
    ACTIVE_PHASE_VOLTAGE_THRESHOLD,
    BOOST_DURATION_SECONDS,
    DEFAULT_NUMBER_OF_PHASES,
    MIN_CHARGE_CURRENT,
    NOMINAL_PHASE_VOLTAGE,
    PROFILE_ID_APPLY_SCHEDULE,
    PROFILE_ID_BOOST,
    PROFILE_ID_MAX_POWER,
    PROFILE_ID_PAUSE,
    PROFILE_IDS_SCHEDULE_DAYS,
    PROFILE_PURPOSE_EXTERNAL,
    SCHEDULE_ANCHOR_YEAR_MONTH,
)

SECONDS_PER_DAY = 86400

# ---------------------------------------------------------------------------
# Profile IDs
# ---------------------------------------------------------------------------


def normalize_profile_id(value: Any) -> int | None:
    """Return a profile ID as a signed 32-bit integer.

    The wallbox reports negative IDs either signed (-19930828) or as their
    unsigned 32-bit representation (4275036468) depending on the endpoint.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number >= 2**31:
        number -= 2**32
    return number


def schedule_weekday_for_profile_id(profile_id: int | None) -> int | None:
    """Return the weekday (0=Monday) of an Eve Connect day profile, else None."""
    if profile_id in PROFILE_IDS_SCHEDULE_DAYS:
        return PROFILE_IDS_SCHEDULE_DAYS.index(profile_id)
    return None


# ---------------------------------------------------------------------------
# Power maths (identical rounding to Eve Connect)
# ---------------------------------------------------------------------------


def _round1(value: float) -> float:
    return round(value + 0.0, 1)


def power_to_current(power_kw: float, phases: int) -> tuple[float, int]:
    """Convert a total power in kW into ``(amps per phase, phases)``.

    Like the app, a power too low to reach the 6 A minimum on every phase is
    applied on a single phase instead.
    """
    phases = max(1, int(phases))
    total_amps = _round1(power_kw * 1000 / NOMINAL_PHASE_VOLTAGE)
    per_phase = _round1(total_amps / phases)
    if per_phase < MIN_CHARGE_CURRENT:
        return total_amps, 1
    return per_phase, phases


def current_to_power(amps: float, phases: int) -> float:
    """Convert amps per phase and phase count into kW (one decimal)."""
    return _round1(float(amps) * max(1, int(phases)) * NOMINAL_PHASE_VOLTAGE / 1000)


def active_phases(voltages: list[Any], fallback: int | None = None) -> int:
    """Count phases whose voltage is above the app's 80 V presence threshold."""
    count = 0
    for voltage in voltages:
        try:
            if float(voltage) > ACTIVE_PHASE_VOLTAGE_THRESHOLD:
                count += 1
        except (TypeError, ValueError):
            continue
    if count:
        return count
    if fallback in (1, 2, 3):
        return int(fallback)
    return DEFAULT_NUMBER_OF_PHASES


# ---------------------------------------------------------------------------
# Request builders
# ---------------------------------------------------------------------------


def _wrap(profile: dict[str, Any]) -> dict[str, Any]:
    return {"connectorId": 0, "csChargingProfiles": profile}


def wrap_profile_request(profile: dict[str, Any]) -> dict[str, Any]:
    """Wrap a bare OCPP profile in the envelope the wallbox expects."""
    if "csChargingProfiles" in profile:
        return profile
    return _wrap(profile)


def build_max_power_request(amps: float, phases: int) -> dict[str, Any]:
    """Build the "preferred maximum power" profile (Power tab in the app)."""
    return _wrap(
        {
            "chargingProfileId": PROFILE_ID_MAX_POWER,
            "chargingProfileKind": "Relative",
            "chargingProfilePurpose": PROFILE_PURPOSE_EXTERNAL,
            "stackLevel": 0,
            "useLocalTime": True,
            "useRandomisedDelay": False,
            "chargingSchedule": {
                "chargingRateUnit": "A",
                "chargingSchedulePeriod": [
                    {"startPeriod": 0, "limit": amps, "numberPhases": phases}
                ],
            },
        }
    )


def build_boost_request(amps: float, start: datetime.datetime) -> dict[str, Any]:
    """Build the 3-hour boost profile that overrides solar / schedule limits."""
    return _wrap(
        {
            "chargingProfileId": PROFILE_ID_BOOST,
            "chargingProfileKind": "Absolute",
            "chargingProfilePurpose": PROFILE_PURPOSE_EXTERNAL,
            "stackLevel": 1000,
            "useRandomisedDelay": False,
            "chargingSchedule": {
                "startSchedule": to_iso_z(start),
                "chargingRateUnit": "A",
                "duration": BOOST_DURATION_SECONDS,
                "chargingSchedulePeriod": [
                    {
                        "startPeriod": 0,
                        "limit": amps,
                        "numberPhases": DEFAULT_NUMBER_OF_PHASES,
                    }
                ],
            },
        }
    )


def build_pause_request() -> dict[str, Any]:
    """Build the zero-current profile used to pause charging."""
    return _wrap(
        {
            "chargingProfileId": PROFILE_ID_PAUSE,
            "chargingProfileKind": "Relative",
            "chargingProfilePurpose": PROFILE_PURPOSE_EXTERNAL,
            "stackLevel": 1000,
            "useLocalTime": True,
            "useRandomisedDelay": False,
            "chargingSchedule": {
                "chargingRateUnit": "A",
                "chargingSchedulePeriod": [{"startPeriod": 0, "limit": 0}],
            },
        }
    )


def build_apply_schedule_request() -> dict[str, Any]:
    """Build the profile that blocks charging outside scheduled time slots."""
    return _wrap(
        {
            "chargingProfileId": PROFILE_ID_APPLY_SCHEDULE,
            "chargingProfileKind": "Relative",
            "chargingProfilePurpose": PROFILE_PURPOSE_EXTERNAL,
            "stackLevel": 1,
            "useLocalTime": True,
            "useRandomisedDelay": False,
            "chargingSchedule": {
                "chargingRateUnit": "A",
                "chargingSchedulePeriod": [
                    {
                        "startPeriod": 0,
                        "limit": 0,
                        "numberPhases": DEFAULT_NUMBER_OF_PHASES,
                    }
                ],
            },
        }
    )


@dataclass(frozen=True)
class TimeSlot:
    """A charging time slot within one day (seconds since local midnight)."""

    start: int
    end: int
    amps: float
    phases: int

    @property
    def power_kw(self) -> float:
        """Return the slot's maximum power in kW."""
        return current_to_power(self.amps, self.phases)

    def overlaps(self, other: TimeSlot) -> bool:
        """Return True when two slots share any time."""
        return self.start < other.end and other.start < self.end

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-friendly representation."""
        return {
            "start": seconds_to_hhmm(self.start),
            "end": seconds_to_hhmm(self.end),
            "start_seconds": self.start,
            "end_seconds": self.end,
            "current_a": self.amps,
            "phases": self.phases,
            "power_kw": self.power_kw,
        }


def schedule_anchor(weekday: int, tzinfo: datetime.tzinfo) -> datetime.datetime:
    """Return local midnight of the reference weekday used by the app."""
    year, month = SCHEDULE_ANCHOR_YEAR_MONTH
    return datetime.datetime(year, month, weekday + 1, tzinfo=tzinfo)


def build_schedule_day_request(
    weekday: int, slots: list[TimeSlot], tzinfo: datetime.tzinfo
) -> dict[str, Any]:
    """Build the recurring weekly profile holding all slots of one weekday."""
    day_of_week = weekday + 1  # Monday = 1, like the app
    ordered = sorted(slots, key=lambda s: s.start)
    periods: list[dict[str, Any]] = []
    if ordered and ordered[0].start != 0:
        # OCPP requires the first period to start at 0 (the wallbox answers
        # 400 otherwise). The app does this by prepending an empty 00:00 slot,
        # which yields periods at 0 and 1 with limit 0; mirror that exactly.
        phases = ordered[0].phases
        periods.append({"startPeriod": 0, "limit": 0, "numberPhases": phases})
        periods.append({"startPeriod": 1, "limit": 0, "numberPhases": phases})
    for slot in ordered:
        periods.append(
            {"startPeriod": slot.start, "limit": slot.amps, "numberPhases": slot.phases}
        )
        periods.append(
            {
                "startPeriod": slot.end if slot.end != 0 else 1,
                "limit": 0,
                "numberPhases": slot.phases,
            }
        )
    return _wrap(
        {
            "chargingProfileId": PROFILE_IDS_SCHEDULE_DAYS[weekday],
            "chargingProfileKind": "Recurring",
            "recurrencyKind": "Weekly",
            "chargingProfilePurpose": PROFILE_PURPOSE_EXTERNAL,
            "stackLevel": 11 - day_of_week,
            "useLocalTime": True,
            "useRandomisedDelay": False,
            "chargingSchedule": {
                "chargingRateUnit": "A",
                "startSchedule": to_iso_z(schedule_anchor(weekday, tzinfo)),
                "duration": SECONDS_PER_DAY,
                "chargingSchedulePeriod": periods,
            },
        }
    )


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def unwrap_profile(response: Any) -> dict[str, Any] | None:
    """Return the inner csChargingProfiles dict of a ``?cpid=`` response."""
    if not isinstance(response, dict):
        return None
    inner = response.get("profile", response)
    if not isinstance(inner, dict):
        return None
    profile = inner.get("csChargingProfiles", inner)
    if not isinstance(profile, dict) or not profile:
        return None
    profile = dict(profile)
    profile_id = normalize_profile_id(profile.get("chargingProfileId"))
    if profile_id is not None:
        profile["chargingProfileId"] = profile_id
    return profile


def profile_periods(profile: dict[str, Any]) -> list[tuple[int, float, int]]:
    """Return ``(startPeriod, limit, numberPhases)`` tuples for any layout.

    * **Nested** (OCPP request format): ``chargingSchedule.chargingSchedulePeriod``
    * **Flat** (wallbox response format): parallel ``startPeriod``, ``limit`` and
      ``numberPhases`` arrays.
    """
    schedule = profile.get("chargingSchedule") or {}
    nested = schedule.get("chargingSchedulePeriod") if isinstance(schedule, dict) else None
    result: list[tuple[int, float, int]] = []
    if nested:
        for period in nested:
            try:
                result.append(
                    (
                        int(period["startPeriod"]),
                        float(period.get("limit") or 0),
                        int(period.get("numberPhases") or DEFAULT_NUMBER_OF_PHASES),
                    )
                )
            except (KeyError, TypeError, ValueError):
                continue
        return result

    starts = profile.get("startPeriod") or []
    if not isinstance(starts, list):
        return result
    limits = profile.get("limit") or []
    phases = profile.get("numberPhases") or []
    for idx, start in enumerate(starts):
        try:
            limit = float(limits[idx]) if idx < len(limits) and limits[idx] is not None else 0.0
            phase = int(phases[idx]) if idx < len(phases) and phases[idx] else DEFAULT_NUMBER_OF_PHASES
            result.append((int(start), limit, phase))
        except (TypeError, ValueError):
            continue
    return result


def profile_slots(profile: dict[str, Any]) -> list[TimeSlot]:
    """Return the active (limit > 0) windows of a daily/weekly profile."""
    periods = sorted(profile_periods(profile), key=lambda p: p[0])
    slots: list[TimeSlot] = []
    for idx, (start, limit, phases) in enumerate(periods):
        if limit <= 0:
            continue
        end = periods[idx + 1][0] if idx + 1 < len(periods) else SECONDS_PER_DAY
        slots.append(TimeSlot(start=start, end=min(end, SECONDS_PER_DAY), amps=limit, phases=phases))
    return slots


def profile_schedule_start(profile: dict[str, Any]) -> str | None:
    """Return a profile's ``startSchedule`` regardless of layout."""
    schedule = profile.get("chargingSchedule")
    if isinstance(schedule, dict) and schedule.get("startSchedule"):
        return schedule["startSchedule"]
    return profile.get("startSchedule")


def profile_duration(profile: dict[str, Any]) -> int | None:
    """Return a profile's duration in seconds, if any."""
    schedule = profile.get("chargingSchedule")
    value = schedule.get("duration") if isinstance(schedule, dict) else None
    if value is None:
        value = profile.get("duration")
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def profile_weekday(profile: dict[str, Any]) -> int | None:
    """Return the weekday (0=Monday) a weekly profile applies to.

    Eve Connect day profiles are identified by their ID. Other weekly profiles
    fall back to the weekday of their ``startSchedule`` anchor. The anchor is a
    local midnight serialised as UTC, so 12 hours are added before taking the
    weekday to land safely inside the intended day for any timezone.
    """
    weekday = schedule_weekday_for_profile_id(profile.get("chargingProfileId"))
    if weekday is not None:
        return weekday
    anchor = parse_iso(profile_schedule_start(profile))
    if anchor is None:
        return None
    if anchor.tzinfo is not None and anchor.utcoffset() == datetime.timedelta(0):
        anchor += datetime.timedelta(hours=12)
    return anchor.weekday()


_WEEKDAY_NAMES = {
    "Monday": 0,
    "Tuesday": 1,
    "Wednesday": 2,
    "Thursday": 3,
    "Friday": 4,
    "Saturday": 5,
    "Sunday": 6,
}


def profile_days(profile: dict[str, Any]) -> list[int]:
    """Return the weekdays (0=Monday) a schedule profile applies to."""
    recurrency = profile.get("recurrencyKind", "Daily")
    if recurrency in ("Weekly", "WEEKLY"):
        if profile.get("daysOfWeek"):
            return [_WEEKDAY_NAMES[d] for d in profile["daysOfWeek"] if d in _WEEKDAY_NAMES]
        weekday = profile_weekday(profile)
        if weekday is not None:
            return [weekday]
    return list(range(7))


def schedule_from_profiles(profiles: list[dict[str, Any]]) -> dict[int, list[TimeSlot]]:
    """Return the time slots per weekday (0=Monday) for schedule profiles."""
    schedule: dict[int, list[TimeSlot]] = {day: [] for day in range(7)}
    for profile in profiles:
        slots = profile_slots(profile)
        if not slots:
            continue
        for day in profile_days(profile):
            schedule[day].extend(slots)
    for slots in schedule.values():
        slots.sort(key=lambda slot: slot.start)
    return schedule


def active_slot(
    schedule: dict[int, list[TimeSlot]], now: datetime.datetime
) -> TimeSlot | None:
    """Return the slot that contains ``now`` (local time), if any."""
    seconds = now.hour * 3600 + now.minute * 60 + now.second
    for slot in schedule.get(now.weekday(), []):
        if slot.start <= seconds < slot.end:
            return slot
    return None


def split_slot(weekday: int, slot: TimeSlot) -> list[tuple[int, TimeSlot]]:
    """Split a slot that runs past midnight into today's and tomorrow's part."""
    if slot.end > slot.start:
        return [(weekday, slot)]
    parts = [(weekday, TimeSlot(slot.start, SECONDS_PER_DAY, slot.amps, slot.phases))]
    if slot.end > 0:
        parts.append(((weekday + 1) % 7, TimeSlot(0, slot.end, slot.amps, slot.phases)))
    return parts










def boost_end(profile: dict[str, Any] | None) -> datetime.datetime | None:
    """Return when a boost profile expires (UTC), or None when unknown."""
    if not profile:
        return None
    start = parse_iso(profile_schedule_start(profile))
    duration = profile_duration(profile) or BOOST_DURATION_SECONDS
    if start is None:
        return None
    if start.tzinfo is None:
        start = start.replace(tzinfo=datetime.UTC)
    return start + datetime.timedelta(seconds=duration)


def max_power_from_profile(profile: dict[str, Any] | None) -> float | None:
    """Return the preferred maximum power (kW) stored in the max-power profile."""
    if not profile or profile.get("chargingProfileKind", "Relative") != "Relative":
        return None
    periods = profile_periods(profile)
    if not periods:
        return None
    _, limit, phases = periods[0]
    return current_to_power(limit, phases)


# ---------------------------------------------------------------------------
# Time helpers
# ---------------------------------------------------------------------------


def to_iso_z(value: datetime.datetime) -> str:
    """Serialise like JavaScript's ``Date.toISOString()``."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=datetime.UTC)
    value = value.astimezone(datetime.UTC)
    return value.strftime("%Y-%m-%dT%H:%M:%S.") + f"{value.microsecond // 1000:03d}Z"


def parse_iso(value: Any) -> datetime.datetime | None:
    """Parse an ISO-8601 timestamp (accepting a trailing ``Z``)."""
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def seconds_to_hhmm(seconds: int) -> str:
    """Format seconds since midnight as HH:MM (24:00 for end of day)."""
    if seconds >= SECONDS_PER_DAY:
        return "24:00"
    hours, remainder = divmod(int(seconds), 3600)
    return f"{hours:02d}:{remainder // 60:02d}"


def hhmm_to_seconds(value: str | datetime.time) -> int:
    """Parse HH:MM[:SS] (or a time object) into seconds since midnight."""
    if isinstance(value, datetime.time):
        return value.hour * 3600 + value.minute * 60 + value.second
    text = str(value).strip()
    if text in ("24:00", "24:00:00"):
        return SECONDS_PER_DAY
    parts = [int(p) for p in text.split(":")]
    if len(parts) < 2 or not 0 <= parts[0] <= 23 or not 0 <= parts[1] <= 59:
        raise ValueError(f"Invalid time: {value}")
    return parts[0] * 3600 + parts[1] * 60 + (parts[2] if len(parts) > 2 else 0)
