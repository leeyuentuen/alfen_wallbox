"""Charging insights derived from wallbox properties.

Pure Python (no Home Assistant imports) so it can be unit tested in isolation:
human-readable status messages for the socket main state, decoding of the
current-limiting factor, the solar / grid split of the charging power and a
small tracker for the current charging session.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Property IDs
# ---------------------------------------------------------------------------

PROP_MAIN_STATE_SOCKET_1 = "2501_1"
PROP_MAX_STATION_CURRENT = "2062_0"
PROP_LIMITING_FACTOR = "218F_1"
PROP_METER_ENERGY_SOCKET_1 = "2221_22"  # Wh
PROP_METER_POWER_SOCKET_1 = "2221_16"  # W
PROP_SMART_METER_POWER = "5221_16"  # W, net at the grid connection (+ = import)
PROP_SOLAR_CHARGING_MODE = "3280_1"  # 0 disabled, 1 comfort, 2 green

# ---------------------------------------------------------------------------
# Socket main state (2501_1)
# ---------------------------------------------------------------------------

SOCKET_MAIN_STATE: dict[int, tuple[str, str]] = {
    -1: ("illegal", "General error. Please contact your installer."),
    0: ("unknown", "Status unknown, please wait..."),
    1: ("booting", "Charging station is starting up."),
    2: ("available", "Charging station is available."),
    3: ("cable_connected", "Cable is connected."),
    4: ("cable_connected_timeout", "Cable is connected, but no authorization has been done."),
    5: ("ev_connected_authorized", "Vehicle is connected and charging session is authorized."),
    6: ("button_activated", "Button is activated."),
    7: ("nfc_available", "Card has been presented."),
    8: ("nfc_authorized", "Card has been authorized."),
    9: ("wait_for_ev_connect", "Waiting on vehicle to connect."),
    10: ("charging_pre_power_off", "Charging station is preparing to charge."),
    11: ("charging_power_off", "Charging station ready, waiting to charge."),
    12: ("charging_power_off_low_max_current", "Waiting for power."),
    13: ("charging_power_starting", "Charging session is starting."),
    14: ("charging_power_on", "Charging session active."),
    15: ("charging_power_on_simplified", "Normal charging session."),
    16: ("charging_wait_for_ev_connect", "Waiting on vehicle to reconnect."),
    17: ("charging_terminating", "Charging session is terminating, wait on vehicle."),
    18: ("charging_wake_up", "Charging station is restarting."),
    19: ("wait_for_disconnect_cp", "Please remove the cable."),
    20: ("wait_for_release_authorization", "Please swipe your card again."),
    21: ("charging_recover_from_outage", "Restart after power outage."),
    22: ("error", "General error. Please contact your installer."),
    23: ("error_message", "General error. Please contact your installer."),
    24: ("error_message_cable_not_supported", "The cable connected is not supported."),
    25: ("error_illegal_mode3", "General error. Please contact your installer."),
    26: ("error_too_many_restarts", "Charging session has restarted too many times."),
    27: ("error_charging", "General error. Please contact your installer."),
    28: ("error_charging_over_current", "Overcurrent detected, please wait..."),
    29: ("error_charging_hf_contactor_switching", "Internal error. Please contact your installer."),
    30: ("error_s2_not_opened", "Vehicle stopped charging."),
    31: ("error_protective_earth", "Protective earth switch triggered."),
    32: ("error_relays", "Internal relay error."),
    33: ("error_low_supply_voltage", "Low supply voltage detected."),
    34: ("error_internal_voltage", "Internal voltage error."),
    35: ("error_power_meter", "Error with internal power meter."),
    36: ("error_temperature", "Temperature inside charging station too high or too low."),
    37: ("suspend", "Charging session has been paused."),
    38: ("inoperative", "Charging station is inoperative."),
    39: ("reserved", "General error. Please contact your installer."),
    40: ("error_charging_rcd_signaled", "The circuit breaker has been triggered."),
    41: ("charging_power_off_ventilating", "Charging session has been suspended by the vehicle."),
    42: ("charging_power_off_suspended", "Charging session has been suspended."),
    43: ("charging_power_off_phase_change", "Charging session will continue on a different phase."),
    44: ("wait_for_start_meter_value", "Waiting for start meter value."),
    45: ("wait_for_stop_meter_value", "Waiting for stop meter value."),
    46: ("error_socket_motor", "Error with locking the cable."),
    47: ("cable_connected_type_e", "Cable connected to Schuko socket."),
    48: ("cable_connected_timeout_type_e", "Schuko cable is connected, but has not been authorized."),
    49: ("charging_type_e", "Charging session active on the Schuko socket."),
    50: ("wait_for_disconnect_type_e", "Please remove the Schuko cable."),
    51: ("charging_suspend_type_e", "Charging session on Schuko socket has been suspended."),
    52: ("charging_low_max_current_type_e", "Waiting for power."),
    53: ("invalid_card", "Invalid card presented."),
    54: ("ev_connected_unauthorized", "Vehicle is connected, but not authorized to charge."),
    55: ("wait_for_disconnect_pp", "Please remove the cable."),
}

# Main states in which no vehicle session is in progress
IDLE_MAIN_STATES = frozenset({-1, 0, 1, 2, 38, 39})
# Main states in which power is flowing to the vehicle
CHARGING_MAIN_STATES = frozenset({13, 14, 15, 49})

# ---------------------------------------------------------------------------
# Current-limiting factor (218F_1)
# ---------------------------------------------------------------------------

LIMITING_FACTOR_FLAGS: dict[int, str] = {
    1: "socket_config",
    2: "station_external",
    4: "station_config",
    8: "cable",
    16: "simplified",
    32: "imbalance",
    64: "socket_cp",
    128: "derating",
    256: "ze_simplified",
    512: "start",
    1024: "suspend",
    2048: "socket_type_e",
    4096: "powerboard",
    8192: "socket_dsc_safe",
    16384: "socket_dsc",
    32768: "alb_active",
    65536: "scn",
    131072: "ems_socket",
    262144: "solar_charging",
    524288: "boot_wait_time",
}

LIMITING_GROUP_VEHICLE = frozenset({8, 16, 64, 256, 2048})
LIMITING_GROUP_LOAD_BALANCING = frozenset({32768, 65536, 131072, 262144})
# Limits that simply reflect the user's or installer's own configuration
LIMITING_EXPECTED = frozenset({0, 1, 2, 4, 512, 1024, 524288})


def decode_limiting_factor(value: Any) -> list[int]:
    """Return the individual limiting-factor flags contained in ``value``.

    The wallbox normally reports a single flag; combined bitmasks are split.
    """
    try:
        number = int(value)
    except (TypeError, ValueError):
        return []
    if number <= 0:
        return []
    if number in LIMITING_FACTOR_FLAGS:
        return [number]
    return [flag for flag in LIMITING_FACTOR_FLAGS if number & flag]


def limiting_group(flags: list[int]) -> str | None:
    """Classify limiting flags: load_balancing, vehicle, installation or None."""
    if any(flag in LIMITING_GROUP_LOAD_BALANCING for flag in flags):
        return "load_balancing"
    if any(flag in LIMITING_GROUP_VEHICLE for flag in flags):
        return "vehicle"
    if any(flag not in LIMITING_EXPECTED for flag in flags):
        return "installation"
    return None


# ---------------------------------------------------------------------------
# Solar / grid split
# ---------------------------------------------------------------------------


def solar_grid_split(charging_w: float | None, meter_w: float | None) -> tuple[float, float]:
    """Split charging power into (solar, grid) watts.

    ``meter_w`` is the smart meter's net power at the grid connection (positive =
    importing). While exporting, all charging power is solar; while importing,
    the imported part counts as grid power.
    """
    if charging_w is None or meter_w is None or charging_w <= 0:
        return 0.0, 0.0
    solar = charging_w if meter_w < 0 else max(charging_w - meter_w, 0.0)
    return solar, charging_w - solar


# ---------------------------------------------------------------------------
# Charging session
# ---------------------------------------------------------------------------

# Cap gaps between updates when integrating the solar / grid energy (seconds)
MAX_SPLIT_INTERVAL = 120


def _float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def prop_value(properties: dict[str, Any], prop_id: str) -> Any:
    """Return the value of a property, or None."""
    prop = properties.get(prop_id)
    return prop.get("value") if isinstance(prop, dict) else None


@dataclass
class ChargingSession:
    """The current (or last) charging session of socket 1."""

    active: bool = False
    start: datetime.datetime | None = None
    end: datetime.datetime | None = None
    start_energy_wh: float | None = None
    energy_kwh: float | None = None
    max_power_w: float | None = None
    solar_wh: float = 0.0
    grid_wh: float = 0.0
    _last_update: datetime.datetime | None = field(default=None, repr=False)

    @property
    def duration_seconds(self) -> int | None:
        """Return the duration of the current / last session."""
        if self.start is None:
            return None
        end = self.end or datetime.datetime.now(datetime.UTC)
        return max(0, int((end - self.start).total_seconds()))

    @property
    def green_share(self) -> float | None:
        """Return the solar share (%) of the energy charged in this session."""
        total = self.solar_wh + self.grid_wh
        return round(self.solar_wh / total * 100, 1) if total > 0 else None

    def update(
        self,
        properties: dict[str, Any],
        now: datetime.datetime,
        resume_from: tuple[datetime.datetime, float] | None = None,
    ) -> None:
        """Update from the latest properties.

        A session starts when the socket leaves an idle state (vehicle connected)
        and ends when it returns to one. ``resume_from`` (start, meter Wh) is used
        when a session is already running when tracking starts, e.g. after a
        Home Assistant restart.
        """
        state = _int(prop_value(properties, PROP_MAIN_STATE_SOCKET_1))
        if state is None:
            return
        energy_wh = _float(prop_value(properties, PROP_METER_ENERGY_SOCKET_1))
        power_w = _float(prop_value(properties, PROP_METER_POWER_SOCKET_1))
        connected = state not in IDLE_MAIN_STATES

        if connected and not self.active:
            start, start_energy = resume_from if resume_from else (now, energy_wh)
            self.active = True
            self.start, self.end = start, None
            self.start_energy_wh = start_energy
            self.energy_kwh = 0.0
            self.max_power_w = power_w or 0.0
            self.solar_wh = self.grid_wh = 0.0
            self._last_update = now
        elif not connected and self.active:
            self.active = False
            self.end = now

        if not self.active:
            return
        if energy_wh is not None and self.start_energy_wh is not None:
            self.energy_kwh = round(max(0.0, energy_wh - self.start_energy_wh) / 1000, 3)
        if power_w is not None:
            self.max_power_w = max(self.max_power_w or 0.0, power_w)
        if self._last_update is not None:
            seconds = min((now - self._last_update).total_seconds(), MAX_SPLIT_INTERVAL)
            solar_w, grid_w = solar_grid_split(
                power_w, _float(prop_value(properties, PROP_SMART_METER_POWER))
            )
            self.solar_wh += solar_w * seconds / 3600
            self.grid_wh += grid_w * seconds / 3600
        self._last_update = now


def charging_status(properties: dict[str, Any]) -> str | None:
    """Return a human-readable status for socket 1."""
    state = _int(prop_value(properties, PROP_MAIN_STATE_SOCKET_1))
    if state is None:
        return None
    connected = state not in IDLE_MAIN_STATES
    # Charging paused by setting the maximum station current to 0
    if connected and _int(prop_value(properties, PROP_MAX_STATION_CURRENT)) == 0:
        return "Charging session has been paused."
    if state in CHARGING_MAIN_STATES:
        mode = _int(prop_value(properties, PROP_SOLAR_CHARGING_MODE))
        if mode == 1:
            return "Solar charging using comfort mode."
        if mode == 2:
            return "Solar charging using green mode."
    return SOCKET_MAIN_STATE.get(state, ("unknown", "Status unknown, please wait..."))[1]
