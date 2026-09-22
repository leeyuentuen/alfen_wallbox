"""Support for Alfen Eve Single Proline Wallbox."""

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import ExtraStoredData, RestoreEntity

from .const import CAT, SERVICE_DISABLE_PHASE_SWITCHING, SERVICE_ENABLE_PHASE_SWITCHING, VALUE
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity

# The wallbox has no pause command: it stops charging when the maximum station
# current (2062_0) is 0. The charging switch writes that value and restores the
# current that was configured before pausing.
MAX_STATION_CURRENT_API_PARAM = "2062_0"
PAUSE_CURRENT = 0
DEFAULT_RESUME_CURRENT = 16


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

    switches = [AlfenSwitchSensor(entry, description) for description in ALFEN_SWITCH_TYPES]
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
            self._resume_current or DEFAULT_RESUME_CURRENT,
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Pause charging by setting the maximum station current to 0."""
        current = self._max_station_current
        if current > PAUSE_CURRENT:
            self._resume_current = current

        await self.coordinator.device.set_value(MAX_STATION_CURRENT_API_PARAM, PAUSE_CURRENT)

    @property
    def _max_station_current(self) -> int:
        """Return the maximum station current reported by the wallbox."""
        prop = self.coordinator.device.properties.get(MAX_STATION_CURRENT_API_PARAM)
        return int(prop[VALUE]) if prop else PAUSE_CURRENT
