"""Support for Alfen Eve Single Proline Wallbox."""

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity
import voluptuous as vol

from . import charging
from .alfen import ChargingProfileError
from .const import (
    CAT,
    LICENSE_HIGH_POWER,
    SERVICE_ADD_SCHEDULE_TIMESLOT,
    SERVICE_CLEAR_CHARGING_SCHEDULE,
    SERVICE_DISABLE_PHASE_SWITCHING,
    SERVICE_ENABLE_PHASE_SWITCHING,
    SERVICE_SET_SCHEDULE_DAY,
    VALUE,
    WEEKDAYS,
)
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity

# The wallbox has no pause command: it stops charging when the maximum station
# current (2062_0) is 0. The charging switch writes that value and restores the
# current that was configured before pausing.
MAX_STATION_CURRENT_API_PARAM = "2062_0"
PAUSE_CURRENT = 0
# Resuming without a remembered current uses the maximum the wallbox supports,
# which is 40 A when the high power socket license is present.
DEFAULT_RESUME_CURRENT = 16
HIGH_POWER_RESUME_CURRENT = 40


@dataclass(frozen=True)
class AlfenSwitchDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    api_param: str


@dataclass(frozen=True)
class AlfenSwitchDescription(SwitchEntityDescription, AlfenSwitchDescriptionMixin):
    """Class to describe an Alfen binary sensor entity."""


ALFEN_SWITCH_TYPES: Final[tuple[AlfenSwitchDescription, ...]] = (
    AlfenSwitchDescription(
        key="lb_enable_phase_switching",
        name="Load Balancing Enable Phase Switching",
        api_param="2185_0",
    ),
    AlfenSwitchDescription(
        key="dp_light_auto_dim",
        name="Display Light Auto Dim",
        api_param="2061_1",
    ),
    AlfenSwitchDescription(
        key="lb_solar_charging_boost",
        name="Solar Charging Boost Socket 1",
        api_param="3280_4",
    ),
    AlfenSwitchDescription(
        key="lb_solar_charging_boost_socket_2",
        name="Solar Charging Boost Socket 2",
        api_param="3280_5",
    ),
    AlfenSwitchDescription(
        key="auth_white_list",
        name="Auth. Whitelist",
        api_param="213B_0",
    ),
    AlfenSwitchDescription(
        key="auth_local_list",
        name="Auth. Local List",
        api_param="213D_0",
    ),
    AlfenSwitchDescription(
        key="auth_restart_after_power_outage",
        name="Auth. Restart after Power Outage",
        api_param="215E_0",
    ),
    AlfenSwitchDescription(
        key="auth_remote_transaction_request",
        name="Auth. Remote Transaction requests",
        api_param="209B_0",
    ),
    AlfenSwitchDescription(
        key="proxy_enabled",
        name="Proxy Enabled",
        api_param="2117_0",
    ),
    AlfenSwitchDescription(
        key="active_load_balancing",
        name="Active Load Balancing",
        api_param="2064_0",
    ),
    AlfenSwitchDescription(
        key="wifi_enabled",
        name="WiFi Enabled",
        api_param="3284_0",
    ),
    AlfenSwitchDescription(
        key="wifi_ap_start_on_boot",
        name="WiFi AP Start on Boot",
        api_param="3291_0",
    ),
    AlfenSwitchDescription(
        key="wifi_ap_enabled",
        name="WiFi AP Enabled",
        api_param="3292_0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen switch entities from a config entry."""

    switches: list[AlfenEntity] = [
        AlfenSwitchSensor(entry, description) for description in ALFEN_SWITCH_TYPES
    ]
    switches.append(AlfenChargingScheduleSwitch(entry))
    switches.append(AlfenChargingSwitch(entry))

    async_add_entities(switches)

    platform = entity_platform.current_platform.get()
    if platform is not None:
        platform.async_register_entity_service(
            SERVICE_ENABLE_PHASE_SWITCHING,
            {},
            "async_enable_phase_switching",
        )

        platform.async_register_entity_service(
            SERVICE_DISABLE_PHASE_SWITCHING,
            {},
            "async_disable_phase_switching",
        )

        # Weekly charging schedule (target: the Charging Schedule switch)
        timeslot = vol.Schema(
            {
                vol.Required("start"): cv.string,
                vol.Required("end"): cv.string,
                vol.Optional("max_power"): vol.All(vol.Coerce(float), vol.Range(min=1.4, max=44)),
                vol.Optional("max_current"): vol.All(vol.Coerce(float), vol.Range(min=1, max=80)),
            }
        )
        platform.async_register_entity_service(
            SERVICE_SET_SCHEDULE_DAY,
            {
                vol.Required("day"): vol.In(WEEKDAYS),
                vol.Optional("timeslots", default=[]): vol.All(cv.ensure_list, [timeslot]),
            },
            "async_set_schedule_day",
        )
        platform.async_register_entity_service(
            SERVICE_ADD_SCHEDULE_TIMESLOT,
            {
                vol.Required("start_time"): cv.string,
                vol.Required("end_time"): cv.string,
                vol.Optional("days", default=[]): vol.All(cv.ensure_list, [vol.In(WEEKDAYS)]),
                vol.Optional("max_power"): vol.All(vol.Coerce(float), vol.Range(min=1.4, max=44)),
                vol.Optional("max_current"): vol.All(vol.Coerce(float), vol.Range(min=1, max=80)),
                vol.Optional("replace", default=False): cv.boolean,
            },
            "async_add_schedule_timeslot",
        )
        platform.async_register_entity_service(
            SERVICE_CLEAR_CHARGING_SCHEDULE,
            {vol.Optional("days", default=[]): vol.All(cv.ensure_list, [vol.In(WEEKDAYS)])},
            "async_clear_charging_schedule",
        )


class AlfenSwitchSensor(AlfenEntity, SwitchEntity):
    """Define an Alfen binary sensor."""

    entity_description: AlfenSwitchDescription

    def __init__(self, entry: AlfenConfigEntry, description: AlfenSwitchDescription) -> None:
        """Initialize."""
        super().__init__(entry)

        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{self.coordinator.device.id}_{description.key}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.api_param in self.coordinator.device.properties

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.entity_description.api_param in self.coordinator.device.properties:
            prop = self.coordinator.device.properties[self.entity_description.api_param]
            return prop[VALUE] in [1, 3]

        return False

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        if self.entity_description.api_param in self.coordinator.device.properties:
            return {
                "category": self.coordinator.device.properties[self.entity_description.api_param][
                    CAT
                ],
            }
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Do the turning on.
        on_value = 3 if self.entity_description.api_param == "2064_0" else 1
        await self.coordinator.device.set_value(self.entity_description.api_param, on_value)
        # set_value() triggers immediate coordinator refresh via callback - no need to call async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.device.set_value(self.entity_description.api_param, 0)
        # set_value() triggers immediate coordinator refresh via callback - no need to call async_update()

    async def async_enable_phase_switching(self):
        """Enable phase switching."""
        await self.coordinator.device.set_phase_switching(True)
        await self.async_turn_on()

    async def async_disable_phase_switching(self):
        """Disable phase switching."""
        await self.coordinator.device.set_phase_switching(False)
        await self.async_turn_off()


@dataclass
class AlfenChargingSwitchExtraStoredData(ExtraStoredData):
    """Extra data to restore the charging switch."""

    resume_current: int | None

    def as_dict(self) -> dict[str, Any]:
        """Return a serializable representation."""
        return {"resume_current": self.resume_current}


class AlfenChargingSwitch(AlfenEntity, SwitchEntity, RestoreEntity):
    """Switch that pauses and resumes charging.

    Setting the maximum station current to 0 stops the wallbox from charging.
    This switch remembers the current that was configured before pausing, so
    resuming does not silently change the charging speed.
    """

    _attr_icon = "mdi:ev-station"

    def __init__(self, entry: AlfenConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry)

        self._attr_name = f"{self.coordinator.device.name} Charging"
        self._attr_unique_id = f"{self.coordinator.device.id}_charging"
        self._resume_current: int | None = None

    @property
    def available(self) -> bool:
        """Return True if the maximum station current is known."""
        return MAX_STATION_CURRENT_API_PARAM in self.coordinator.device.properties

    @property
    def is_on(self) -> bool:
        """Return True when charging is allowed."""
        return self._max_station_current > PAUSE_CURRENT

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the current that is restored when charging resumes."""
        return {"resume_current": self._resume_current}

    @property
    def extra_restore_state_data(self) -> AlfenChargingSwitchExtraStoredData:
        """Return the data to restore after a restart."""
        return AlfenChargingSwitchExtraStoredData(self._resume_current)

    async def async_added_to_hass(self) -> None:
        """Restore the current that was configured before pausing."""
        await super().async_added_to_hass()

        if (extra := await self.async_get_last_extra_data()) is not None:
            self._resume_current = extra.as_dict().get("resume_current")

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Resume charging with the current that was configured before pausing."""
        await self.coordinator.device.set_value(
            MAX_STATION_CURRENT_API_PARAM,
            self._resume_current or self._default_resume_current,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause charging by setting the maximum station current to 0."""
        current = self._max_station_current
        if current > PAUSE_CURRENT:
            self._resume_current = current

        await self.coordinator.device.set_value(MAX_STATION_CURRENT_API_PARAM, PAUSE_CURRENT)

    @property
    def _default_resume_current(self) -> int:
        """Return the current to resume with when none was remembered."""
        if LICENSE_HIGH_POWER in self.coordinator.device.get_licenses():
            return HIGH_POWER_RESUME_CURRENT

        return DEFAULT_RESUME_CURRENT

    @property
    def _max_station_current(self) -> int:
        """Return the maximum station current reported by the wallbox."""
        prop = self.coordinator.device.properties.get(MAX_STATION_CURRENT_API_PARAM)
        return int(prop[VALUE]) if prop else PAUSE_CURRENT


class AlfenChargingScheduleSwitch(AlfenEntity, SwitchEntity):
    """Apply the weekly charging schedule.

    When on, the wallbox only charges inside the configured time slots. The
    attributes list the slots per weekday; the schedule services act on this entity.
    """

    _attr_icon = "mdi:calendar-clock"
    _attr_translation_key = "charging_schedule_enabled"

    def __init__(self, entry: AlfenConfigEntry) -> None:
        """Initialize."""
        super().__init__(entry)
        device = self.coordinator.device
        self._attr_name = f"{device.name} Charging Schedule"
        self._attr_unique_id = f"{device.id}_charging_schedule_enabled"

    @property
    def is_on(self) -> bool:
        """Return True when the schedule is applied."""
        return self.coordinator.device.schedule_enabled

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the slots per day so cards can show the schedule."""
        schedule = self.coordinator.device.get_schedule()
        return {
            WEEKDAYS[day].lower(): [slot.as_dict() for slot in slots]
            for day, slots in schedule.items()
        }

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Only charge inside the scheduled time slots."""
        await self.coordinator.device.set_schedule_enabled(True)

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Charge at any time again."""
        await self.coordinator.device.set_schedule_enabled(False)

    def _slot(self, start: str, end: str, max_power: float | None, max_current: float | None):
        return self.coordinator.device.make_timeslot(
            start=charging.hhmm_to_seconds(start),
            end=charging.hhmm_to_seconds(end),
            power_kw=max_power,
            current=max_current if max_power is None else None,
        )

    async def async_set_schedule_day(self, day: str, timeslots: list[dict[str, Any]]) -> None:
        """Replace all time slots of one weekday (an empty list clears it)."""
        try:
            slots = [
                self._slot(item["start"], item["end"], item.get("max_power"), item.get("max_current"))
                for item in timeslots
            ]
            await self.coordinator.device.set_schedule_day(WEEKDAYS.index(day), slots)
        except (ChargingProfileError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_add_schedule_timeslot(
        self,
        start_time: str,
        end_time: str,
        days: list[str] | None = None,
        max_power: float | None = None,
        max_current: float | None = None,
        replace: bool = False,
    ) -> None:
        """Add a time slot to the given days (every day when empty)."""
        weekdays = [WEEKDAYS.index(day) for day in days] if days else list(range(7))
        try:
            await self.coordinator.device.add_schedule_slot(
                weekdays, self._slot(start_time, end_time, max_power, max_current), replace=replace
            )
        except (ChargingProfileError, ValueError) as err:
            raise HomeAssistantError(str(err)) from err

    async def async_clear_charging_schedule(self, days: list[str] | None = None) -> None:
        """Remove the time slots of the given days (the whole schedule when empty)."""
        await self.coordinator.device.clear_schedule(
            [WEEKDAYS.index(day) for day in days] if days else None
        )
