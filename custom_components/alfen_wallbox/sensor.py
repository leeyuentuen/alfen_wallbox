import logging
from typing import Final
from dataclasses import dataclass

import voluptuous as vol
from .entity import AlfenEntity
from homeassistant import const
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfElectricCurrent, UnitOfElectricPotential, UnitOfEnergy, UnitOfInformation, UnitOfPower, UnitOfSpeed, UnitOfTemperature

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import Entity
from homeassistant.components.sensor import (
    DEVICE_CLASS_ENERGY,
    DEVICE_CLASS_POWER,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from homeassistant.helpers import config_validation as cv, entity_platform

from . import DOMAIN as ALFEN_DOMAIN


from .alfen import AlfenDevice
from .const import (
    SERVICE_REBOOT_WALLBOX,
    SERVICE_SET_CURRENT_LIMIT,
    SERVICE_ENABLE_RFID_AUTHORIZATION_MODE,
    SERVICE_DISABLE_RFID_AUTHORIZATION_MODE,
    SERVICE_SET_CURRENT_PHASE,
    SERVICE_ENABLE_PHASE_SWITCHING,
    SERVICE_DISABLE_PHASE_SWITCHING,
    SERVICE_SET_GREEN_SHARE,
    SERVICE_SET_COMFORT_POWER,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenSensorDescriptionMixin:
    """Define an entity description mixin for sensor entities."""

    api_param: str
    unit: str


@dataclass
class AlfenSensorDescription(
    SensorEntityDescription,  AlfenSensorDescriptionMixin
):
    """Class to describe an Alfen sensor entity."""


STATUS_DICT: Final[dict[str, int]] = {
    0: "Unknown",
    1: "Off",
    2: "Booting",
    3: "Booting Check Mains",
    4: "Available",
    5: "Prep. Authorising",
    6: "Prep. Authorised",
    7: "Prep. Cable connected",
    8: "Prep EV Connected",
    9: "Charging Preparing",
    10: "Vehicle connected",
    11: "Charging Active Normal",
    12: "Charging Active Simplified",
    13: "Charging Suyspended Over Current",
    14: "Charging Suspended HF Switching",
    15: "Charging Suspended EV Disconnected",
    16: "Finish Wait Vehicle",
    17: "Finished Wait Disconnect",
    18: "Error Protective Earth",
    19: "Error Powerline Fault",
    20: "Error Contactor Fault",
    21: "Error Charging",
    22: "Error Power Failure",
    23: "Error Temperature",
    24: "Error Illegal CP Value",
    25: "Error Illegal PP Value",
    26: "Error Too Many Restarts",
    27: "Error",
    28: "Error Message",
    29: "Error Message Not Authorised",
    30: "Error Message Cable Not Supported",
    31: "Error Message S2 Not Opened",
    32: "Error Message Time Out",
    33: "Reserved",
    34: "Inoperative",
    35: "Load Balancing Limited",
    36: "Load Balancing Forced Off",
    38: "Not Charging",
    39: "Solar Charging Wait",
    41: "Solar Charging",
    42: "Charge Point Ready, Waiting For Power",
    43: "Partial Solar Charging",
}

ALFEN_SENSOR_TYPES: Final[tuple[AlfenSensorDescription, ...]] = (
    AlfenSensorDescription(
        key="status",
        name="Status Code",
        icon="mdi:ev-station",
        api_param="2501_2",
        unit=None,
    ),
    AlfenSensorDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:timer-outline",
        api_param="2060_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="bootups",
        name="Bootups",
        icon="mdi:reload",
        api_param="2056_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="voltage_l1",
        name="Voltage L1",
        icon="mdi:flash",
        api_param="2221_3",
        unit=UnitOfElectricPotential.VOLT,
    ),
    AlfenSensorDescription(
        key="voltage_l2",
        name="Voltage L2",
        icon="mdi:flash",
        api_param="2221_4",
        unit=UnitOfElectricPotential.VOLT,
    ),
    AlfenSensorDescription(
        key="voltage_l3",
        name="Voltage L3",
        icon="mdi:flash",
        api_param="2221_5",
        unit=UnitOfElectricPotential.VOLT,
    ),
    AlfenSensorDescription(
        key="current_l1",
        name="Current L1",
        icon="mdi:current-ac",
        api_param="2221_A",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="current_l2",
        name="Current L2",
        icon="mdi:current-ac",
        api_param="2221_B",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="current_l3",
        name="Current L3",
        icon="mdi:current-ac",
        api_param="2221_C",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="active_power_total",
        name="Active Power Total",
        icon="mdi:circle-slice-3",
        api_param="2221_16",
        unit=UnitOfPower.WATT,
    ),
    AlfenSensorDescription(
        key="meter_reading",
        name="Meter Reading",
        icon=None,
        api_param="2221_22",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
    ),
    AlfenSensorDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:thermometer",
        api_param="2201_0",
        unit=UnitOfTemperature.CELSIUS,
    ),
    AlfenSensorDescription(
        key="current_limit",
        name="Current Limit",
        icon="mdi:current-ac",
        api_param="2129_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="auth_mode",
        name="Authorization Mode",
        icon=None,
        api_param="2126_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="alb_safe_current",
        name="Active Load Balancing Safe Current",
        icon="mdi:current-ac",
        api_param="2068_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="alb_phase_connection",
        name="Active Load Balancing Phase Connection",
        icon=None,
        api_param="2069_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="max_station_current",
        name="Maximum Smart Meter current",
        icon="mdi:current-ac",
        api_param="2062_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="load_balancing_mode",
        name="Load Balancing Mode",
        icon=None,
        api_param="2064_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="main_static_lb_max_current",
        name="Main Static Load Balancing Max Current",
        icon="mdi:current-ac",
        api_param="212B_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="main_active_lb_max_current",
        name="Main Active Load Balancing Max Current",
        icon="mdi:current-ac",
        api_param="212D_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="charging_box_identifier",
        name="Charging Box Identifier",
        icon=None,
        api_param="2053_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="boot_reason",
        name="System Boot Reason",
        icon=None,
        api_param="2057_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="max_smart_meter_current",
        name="Max Smart Meter Current",
        icon="mdi:current-ac",
        api_param="2067_0",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="p1_measurements_1",
        name="P1 Meter Phase 1 Current",
        icon="mdi:current-ac",
        api_param="212F_1",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="p1_measurements_2",
        name="P1 Meter Phase 2 Current",
        icon="mdi:current-ac",
        api_param="212F_2",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="p1_measurements_3",
        name="P1 Meter Phase 3 Current",
        icon="mdi:current-ac",
        api_param="212F_3",
        unit=UnitOfElectricCurrent.AMPERE,
    ),
    AlfenSensorDescription(
        key="gprs_apn_name",
        name="GPRS APN Name",
        icon="mdi:antenna",
        api_param="2100_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_apn_user",
        name="GPRS APN User",
        icon="mdi:antenna",
        api_param="2101_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_apn_password",
        name="GPRS APN Password",
        icon="mdi:antenna",
        api_param="2102_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_sim_imsi",
        name="GPRS SIM IMSI",
        icon="mdi:antenna",
        api_param="2104_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_sim_iccid",
        name="GPRS SIM Serial",
        icon="mdi:antenna",
        api_param="",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_provider",
        name="GPRS Provider",
        icon="mdi:antenna",
        api_param="",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_wired_server_domain_and_port",
        name="Wired Url Server Domain And Port",
        icon="mdi:cable-data",
        api_param="2071_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_wired_server_path",
        name="Wired Url Wired Server Path",
        icon="mdi:cable-data",
        api_param="2071_2",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_dhcp_address_1",
        name="GPRS DHCP Address",
        icon="mdi:antenna",
        api_param="2072_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_netmask_address_1",
        name="GPRS Netmask",
        icon="mdi:antenna",
        api_param="2073_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_gateway_address_1",
        name="GPRS Gateway Address",
        icon="mdi:antenna",
        api_param="2074_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_ip_address_1",
        name="GPRS IP Address",
        icon="mdi:antenna",
        api_param="2075_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_short_name",
        name="Backoffice Short Name",
        icon=None,
        api_param="2076_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_gprs_server_domain_and_port",
        name="GPRS Url Server Domain And Port",
        icon="mdi:antenna",
        api_param="2078_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_gprs_server_path",
        name="GPRS Url Server Path",
        icon="mdi:antenna",
        api_param="2078_2",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_gprs_dns_1",
        name="GPRS DNS 1",
        icon="mdi:antenna",
        api_param="2079_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_gprs_dns_2",
        name="GPRS DNS 2",
        icon="mdi:antenna",
        api_param="2080_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="gprs_signal_strength",
        name="GPRS Signal",
        icon="mdi:antenna",
        api_param="2110_0",
        unit=const.SIGNAL_STRENGTH_DECIBELS,
    ),
    AlfenSensorDescription(
        key="comm_dhcp_address_2",
        name="Wired DHCP",
        icon="mdi:cable-data",
        api_param="207A_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_netmask_address_2",
        name="Wired Netmask",
        icon="mdi:cable-data",
        api_param="207B_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_gateway_address_2",
        name="Wired Gateway Address",
        icon="mdi:cable-data",
        api_param="207C_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_ip_address_2",
        name="Wired IP Address",
        icon="mdi:cable-data",
        api_param="207D_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_wired_dns_1",
        name="Wired DNS 1",
        icon="mdi:cable-data",
        api_param="207E_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_wired_dns_2",
        name="Wired DNS 2",
        icon="mdi:cable-data",
        api_param="207F_1",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_protocol_name",
        name="Protocol Name",
        icon=None,
        api_param="2081_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="comm_protocol_version",
        name="Protocol Version",
        icon=None,
        api_param="2082_0",
        unit=None,
    ),
    AlfenSensorDescription(
        key="lb_solar_charging_green_share",
        name="Solar Charging Green Share %",
        icon=None,
        api_param="3280_2",
        unit=const.PERCENTAGE,
    ),
    AlfenSensorDescription(
        key="lb_solar_charging_comfort_level",
        name="Solar Charging Comfort Level w",
        icon=None,
        api_param="3280_3",
        unit=UnitOfPower.WATT,
    ),
)


async def async_setup_platform(
        hass: HomeAssistant,
        config: ConfigEntry,
        async_add_entities: AddEntitiesCallback,
        discovery_info=None):
    pass


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback):
    """Set up using config_entry."""
    device = hass.data[ALFEN_DOMAIN][entry.entry_id]

    sensors = [
        AlfenSensor(device, description) for description in ALFEN_SENSOR_TYPES
    ]

    async_add_entities(sensors)
    async_add_entities([AlfenMainSensor(device)])

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_REBOOT_WALLBOX,
        {},
        "async_reboot_wallbox",
    )

    platform.async_register_entity_service(
        SERVICE_SET_CURRENT_LIMIT,
        {
            vol.Required("limit"): cv.positive_int,
        },
        "async_set_current_limit",
    )

    platform.async_register_entity_service(
        SERVICE_SET_CURRENT_PHASE,
        {
            vol.Required("phase"): str,
        },
        "async_set_current_phase",
    )

    platform.async_register_entity_service(
        SERVICE_ENABLE_RFID_AUTHORIZATION_MODE,
        {},
        "async_enable_rfid_auth_mode",
    )

    platform.async_register_entity_service(
        SERVICE_DISABLE_RFID_AUTHORIZATION_MODE,
        {},
        "async_disable_rfid_auth_mode",
    )

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

    platform.async_register_entity_service(
        SERVICE_SET_GREEN_SHARE,
        {
            vol.Required("value"): cv.positive_int,
        },
        "async_set_green_share",
    )

    platform.async_register_entity_service(
        SERVICE_SET_COMFORT_POWER,
        {
            vol.Required("value"): cv.positive_int,
        },
        "async_set_comfort_power",
    )


class AlfenMainSensor(AlfenEntity):
    def __init__(self, device: AlfenDevice) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{device.name}"
        self._sensor = "sensor"

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id}-{self._sensor}"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:car-electric"

    @property
    def state(self):
        """Return the state of the sensor."""
        if self._device.status is not None:
            return self.status_as_str()
        return None

    async def async_reboot_wallbox(self):
        """Reboot the wallbox."""
        await self._device.reboot_wallbox()

    async def async_set_current_limit(self, limit):
        """Set the current limit."""
        await self._device.set_current_limit(limit)

    async def async_enable_rfid_auth_mode(self):
        """Enable RFID authorization mode."""
        await self._device.set_rfid_auth_mode(True)

    async def async_disable_rfid_auth_mode(self):
        """Disable RFID authorization mode."""
        await self._device.set_rfid_auth_mode(False)

    async def async_update(self):
        """Update the sensor."""
        await self._device.async_update()

    async def async_set_current_phase(self, phase):
        """Set the current phase."""
        await self._device.set_current_phase(phase)

    async def async_enable_phase_switching(self):
        """Enable phase switching."""
        await self._device.set_phase_switching(True)

    async def async_disable_phase_switching(self):
        """Disable phase switching."""
        await self._device.set_phase_switching(False)

    async def async_set_green_share(self, value):
        """Set the green share."""
        await self._device.set_green_share(value)

    async def async_set_comfort_power(self, value):
        """Set the comfort power."""
        await self._device.set_comfort_power(value)

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device.device_info

    def status_as_str(self):
        """Return the status as a string."""
        return STATUS_DICT.get(self._device.status.status, "Unknown")


class AlfenSensor(AlfenEntity, SensorEntity):
    """Representation of a Alfen Sensor."""

    entity_description: AlfenSensorDescription

    def __init__(self,
                 device: AlfenDevice,
                 description: AlfenSensorDescription) -> None:
        """Initialize the sensor."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
        self.entity_description = description
        if self.entity_description.key == "active_power_total":
            _LOGGER.info(f"Initiating State sensors {self._attr_name}")
            self._attr_device_class = DEVICE_CLASS_POWER
            self._attr_state_class = SensorStateClass.MEASUREMENT
        elif self.entity_description.key == "uptime":
            _LOGGER.info(f"Initiating State sensors {self._attr_name}")
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        elif self.entity_description.key == "meter_reading":
            _LOGGER.info(f"Initiating State sensors {self._attr_name}")
            self._attr_device_class = DEVICE_CLASS_ENERGY
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING
        self._async_update_attrs()

    def _get_current_value(self):
        """Get the current value."""
        for prop in self._device.properties:
            if prop['id'] == self.entity_description.api_param:
                return prop['value']
        return None
#        return getattr(self._device.properties, self.entity_description.key)

    @callback
    def _async_update_attrs(self) -> None:
        """Update the state and attributes."""
        self._attr_native_value = self._get_current_value()

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self._device.id}-{self.entity_description.key}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return self.entity_description.icon

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return round(self.state, 2)

    @property
    def native_unit_of_measurement(self):
        """Return the unit the value is expressed in."""
        return self.entity_description.unit

    @property
    def state(self):
        """Return the state of the sensor."""
        for prop in self._device.properties:
            if prop['id'] == self.entity_description.api_param:
                return prop['value']

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self.entity_description.unit

    async def async_update(self):
        """Get the latest data and updates the states."""
        await self._device.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self._device.device_info
