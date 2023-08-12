from homeassistant.helpers import entity_platform
from .const import ID, SERVICE_SET_COMFORT_POWER, SERVICE_SET_CURRENT_LIMIT, SERVICE_SET_GREEN_SHARE, VALUE
from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberEntityDescription, NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from . import DOMAIN as ALFEN_DOMAIN
from homeassistant.core import HomeAssistant
import logging
from typing import Final
from dataclasses import dataclass
from .entity import AlfenEntity
from .alfen import AlfenDevice
from homeassistant.const import (
    PERCENTAGE,
    UnitOfElectricCurrent,
    UnitOfPower,
    UnitOfTime,
)

import voluptuous as vol

from homeassistant.helpers import config_validation as cv


_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenNumberDescriptionMixin:
    """Define an entity description mixin for select entities."""
    assumed_state: bool
    state: float
    api_param: str
    custom_mode: str


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
        native_max_value=32,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2068_0",
    ),
    AlfenNumberDescription(
        key="ps_connector_max_limit",
        name="Power Connector Max Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2129_0",
    ),
    AlfenNumberDescription(
        key="max_station_current",
        name="Max. Station Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2062_0",
    ),
    AlfenNumberDescription(
        key="lb_max_smart_meter_current",
        name="Load Balancing Max. Meter Current",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.CURRENT,
        native_min_value=0,
        native_max_value=32,
        native_step=1,
        custom_mode=None,
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="2067_0",
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
    ),
    AlfenNumberDescription(
        key="lb_solar_charging_comfort_level",
        name="Solar Comfort Level",
        state=None,
        icon="mdi:current-ac",
        assumed_state=False,
        device_class=NumberDeviceClass.POWER_FACTOR,
        native_min_value=1400,
        native_max_value=3500,
        native_step=100,
        custom_mode=None,
        unit_of_measurement=UnitOfPower.WATT,
        api_param="3280_3",
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
        unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        api_param="21B9_0",
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
    ),

)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Alfen select entities from a config entry."""
    device = hass.data[ALFEN_DOMAIN][entry.entry_id]
    numbers = [AlfenNumber(device, description)
               for description in ALFEN_NUMBER_TYPES]

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

    def __init__(
        self,
        device: AlfenDevice,
        description: AlfenNumberDescription,
    ) -> None:
        """Initialize the Alfen Number entity."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{description.name}"
        self._attr_unique_id = f"{self._device.id}_{description.key}"
        self._attr_assumed_state = description.assumed_state
        self._attr_device_class = description.device_class
        self._attr_icon = description.icon
        if description.custom_mode is None:  # issue with pre Home Assistant Core 2023.6 versions
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

    @property
    def native_value(self) -> float | None:
        """Return the entity value to represent the entity state."""
        for prop in self._device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE]
        return None

    async def async_set_native_value(self, value: float) -> None:
        """Update the current value."""
        await self.update_state(self.entity_description.api_param, int(value))
        self._attr_native_value = self._get_current_option()
        self.async_write_ha_state()

    def _get_current_option(self) -> str | None:
        """Return the current option."""
        for prop in self._device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE]
        return None

    async def async_set_current_limit(self, limit):
        """Set the current limit."""
        await self._device.set_current_limit(limit)
        await self.async_set_native_value(limit)

    async def async_set_green_share(self, value):
        """Set the green share."""
        await self._device.set_green_share(value)
        await self.async_set_native_value(value)


    async def async_set_comfort_power(self, value):
        """Set the comfort power."""
        await self._device.set_comfort_power(value)
        await self.async_set_native_value(value)