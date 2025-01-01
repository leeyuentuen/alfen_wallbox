"""Support for Alfen Eve Proline Wallbox."""

from dataclasses import dataclass
import logging
from typing import Final

import voluptuous as vol

from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.const import (
    CURRENCY_EURO,
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv, entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAT,
    ID,
    LICENSE_HIGH_POWER,
    SERVICE_SET_COMFORT_POWER,
    SERVICE_SET_CURRENT_LIMIT,
    SERVICE_SET_GREEN_SHARE,
    VALUE,
)
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenNumberDescriptionMixin:
    """Define an entity description mixin for select entities."""

    assumed_state: bool
    state: float
    api_param: str
    custom_mode: str
    round_digits: int | None


@dataclass
class AlfenNumberDescription(NumberEntityDescription, AlfenNumberDescriptionMixin):
    """Class to describe an Alfen select entity."""


ALFEN_NUMBER_TYPES: Final[tuple[AlfenNumberDescription, ...]] = (
    AlfenNumberDescription(
        key="alb_safe_current",
        name="Load Balancing Safe Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=1,
        native_max_value=16,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2068_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="main_normal_max_current_socket_1",
        name="Power Connector Max Current Socket 1",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2129_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="max_station_current",
        name="Max. Station Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2062_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="lb_max_smart_meter_current",
        name="Load Balancing Max. Meter Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=40,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2067_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="lb_solar_charging_green_share",
        name="Solar Green Share",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=PERCENTAGE,
        api_param="3280_2",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="lb_solar_charging_comfort_level",
        name="Solar Comfort Level",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=1350,
        native_max_value=11000,
        native_step=50,
        custom_mode=None,
        unit_of_measurement=UnitOfPower.WATT,
        api_param="3280_3",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="dp_light_intensity",
        name="Display Light Intensity %",
        state=None,
        icon="mdi:lightbulb",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=100,
        native_step=10,
        custom_mode=None,
        unit_of_measurement=PERCENTAGE,
        api_param="2061_2",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ps_installation_max_imbalance_current",
        name="Installation Max. Imbalance Current between phases",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=10,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2174_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="lb_Charging_profiles_random_delay",
        name="Load Balancing Charging profiles random delay",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="21B9_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="auth_re_authorize_after_power_outage",
        name="Auth. Re-authorize after Power Outage (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2169_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="auth_connection_timeout",
        name="Auth. Connection Timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2169_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ws_wired_socket_timeout",
        name="WS Wired websocket timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208B_1",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ws_mobile_socket_timeout",
        name="WS Mobile websocket timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208B_2",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ocpp_wired_ocpp_send_timeout",
        name="OCPP Wired OCPP send timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208D_1",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ocpp_mobile_ocpp_send_timeout",
        name="OCPP Mobile OCPP send timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208D_2",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ocpp_wired_ocpp_reply_timeout",
        name="OCPP Wired OCPP reply timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208E_1",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ocpp_mobile_ocpp_reply_timeout",
        name="OCPP Mobile OCPP reply timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="208E_1",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="heartbeat_interval",
        name="Heartbeat interval (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=9000,
        native_step=100,
        custom_mode=NumberMode.BOX,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2086_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="price_start_tariff",
        name="Price Start Tariff",
        state=None,
        icon="mdi:currency-eur",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=5,
        native_step=0.01,
        custom_mode=NumberMode.BOX,
        unit_of_measurement=CURRENCY_EURO,
        api_param="3262_2",
        round_digits=2,
    ),
    AlfenNumberDescription(
        key="price_price_per_kwh",
        name="Price per kWh",
        state=None,
        icon="mdi:currency-eur",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=5,
        native_step=0.01,
        custom_mode=NumberMode.BOX,
        unit_of_measurement=CURRENCY_EURO,
        api_param="3262_3",
        round_digits=2,
    ),
    AlfenNumberDescription(
        key="price_price_per_minute",
        name="Price per minute",
        state=None,
        icon="mdi:currency-eur",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=5,
        native_step=0.01,
        custom_mode=NumberMode.BOX,
        unit_of_measurement=CURRENCY_EURO,
        api_param="3262_4",
        round_digits=2,
    ),
    AlfenNumberDescription(
        key="price_price_other",
        name="Price other",
        state=None,
        icon="mdi:currency-eur",
        assumed_state=False,
        device_class=None,
        native_min_value=-5,
        native_max_value=5,
        native_step=0.01,
        custom_mode=NumberMode.BOX,
        unit_of_measurement=CURRENCY_EURO,
        api_param="3262_6",
        round_digits=2,
    ),
    AlfenNumberDescription(
        key="ev_disconnection_timeout",
        name="Car Disconnection Timeout (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2136_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ev_non_charging_report_threshold",
        name="Car Time to Report Not Charging (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2184_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="ev_auto_stop_transaction_time",
        name="Car Time to Unlock Not Charging (s)",
        state=None,
        icon="mdi:timer-sand",
        assumed_state=False,
        device_class=None,
        native_min_value=0,
        native_max_value=30,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfTime.SECONDS,
        api_param="2168_0",
        round_digits=None,
    ),
    AlfenNumberDescription(
        key="main_external_max_current_socket_1",
        name="Power Connector External Max Current Socket 1",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="212A_0",
        round_digits=None,
    ),
)

ALFEN_NUMBER_DUAL_SOCKET_TYPES: Final[tuple[AlfenNumberDescription, ...]] = (
    AlfenNumberDescription(
        key="main_normal_max_current_socket_2",
        name="Power Connector Max Current Socket 2",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=16,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="3129_0",
        round_digits=None,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen select entities from a config entry."""
    numbers = [AlfenNumber(entry, description) for description in ALFEN_NUMBER_TYPES]

    async_add_entities(numbers)

    coordinator = entry.runtime_data
    if coordinator.device.number_socket == 2:
        numbers = [
            AlfenNumber(entry, description)
            for description in ALFEN_NUMBER_DUAL_SOCKET_TYPES
        ]
        async_add_entities(numbers)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_SET_CURRENT_LIMIT,
        {
            vol.Required("limit"): cv.positive_int,
        },
        "async_set_current_limit",
    )

    platform.async_register_entity_service(
        SERVICE_SET_GREEN_SHARE,
        {
            vol.Required(VALUE): cv.positive_int,
        },
        "async_set_green_share",
    )

    platform.async_register_entity_service(
        SERVICE_SET_COMFORT_POWER,
        {
            vol.Required(VALUE): cv.positive_int,
        },
        "async_set_comfort_power",
    )


class AlfenNumber(AlfenEntity, NumberEntity):
    """Define an Alfen select entity."""

    _attr_has_entity_name = True
    _attr_name = None
    _attr_should_poll = False
    entity_description: AlfenNumberDescription

    def __init__(
        self,
        entry: AlfenConfigEntry,
        description: AlfenNumberDescription,
    ) -> None:
        """Initialize the Alfen Number entity."""
        super().__init__(entry)
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self.coordinator.device.id}_{description.key}"
        self._attr_assumed_state = description.assumed_state
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon
        if (
            description.custom_mode is None
        ):  # issue with pre Home Assistant Core 2023.6 versions
            self._attr_mode = NumberMode.SLIDER
        else:
            self._attr_mode = description.custom_mode
        self._attr_native_unit_of_measurement = description.unit_of_measurement
        self._attr_native_value = description.state
        self.entity_description = description

        if description.native_min_value is not None:
            self._attr_min_value = description.native_min_value
            self._attr_native_min_value = description.native_min_value
        if description.native_max_value is not None:
            self._attr_max_value = description.native_max_value
            self._attr_native_max_value = description.native_max_value
        if description.native_step is not None:
            self._attr_native_step = description.native_step

        # override the amps and set them on 32A if there is a license for it
        override_amps_api_key = ["2068_0", "2129_0", "2062_0", "3129_0"]
        # check if device licenses has the high power socket license
        if LICENSE_HIGH_POWER in self.coordinator.device.licenses:
            if description.api_param in override_amps_api_key:
                self._attr_max_value = 40
                self._attr_native_max_value = 40

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        return self._get_current_option()

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        if self.entity_description.round_digits is not None:
            await self.coordinator.device.set_value(
                self.entity_description.api_param,
                round(float(value), self.entity_description.round_digits),
            )
        else:
            await self.coordinator.device.set_value(
                self.entity_description.api_param, int(value)
            )
        self._set_current_option()

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return {"category": prop[CAT]}
        return None

    def _get_current_option(self) -> str | None:
        """Return the current option."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                _LOGGER.debug("%s Value: %s", self.entity_description.name, prop[VALUE])

                if self.entity_description.round_digits is not None:
                    return round(prop[VALUE], self.entity_description.round_digits)

                # change comfort level depends on max allowed phase
                if self.entity_description.key == "lb_solar_charging_comfort_level":
                    if self.coordinator.device.max_allowed_phases == 3:
                        self._attr_max_value = self.entity_description.native_max_value
                        self._attr_native_max_value = (
                            self.entity_description.native_max_value
                        )
                    else:
                        self._attr_max_value = 3300
                        self._attr_native_max_value = 3300

                return prop[VALUE]
        return None

    def _set_current_option(self):
        """Set the current option."""
        self._attr_native_value = self._get_current_option()
        self.async_write_ha_state()

    async def async_set_current_limit(self, limit):
        """Set the current limit."""
        await self.coordinator.device.set_current_limit(limit)
        self._set_current_option()

    async def async_set_green_share(self, value):
        """Set the green share."""
        await self.coordinator.device.set_green_share(value)
        self._set_current_option()

    async def async_set_comfort_power(self, value):
        """Set the comfort power."""
        await self.coordinator.device.set_comfort_power(value)
        self._set_current_option()

    async def async_update(self):
        """Get the latest data and updates the states."""
        self._set_current_option()
