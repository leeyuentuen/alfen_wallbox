"""Support for Alfen Eve Single Proline Wallbox."""

from dataclasses import dataclass
import datetime
from typing import Final

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    SIGNAL_STRENGTH_DECIBELS,
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfFrequency,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import CAT, ID, SERVICE_REBOOT_WALLBOX, VALUE
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity


@dataclass
class AlfenSensorDescriptionMixin:
    """Define an entity description mixin for sensor entities."""

    api_param: str
    unit: str
    round_digits: int | None


@dataclass
class AlfenSensorDescription(SensorEntityDescription, AlfenSensorDescriptionMixin):
    """Class to describe an Alfen sensor entity."""


STATUS_DICT: Final[dict[int, str]] = {
    0: "Unknown",
    1: "Off",
    2: "Booting",
    3: "Check Mains",
    4: "Available",
    5: "Authorizing",
    6: "Authorized",
    7: "Cable connected",
    8: "EV Connected",
    9: "Preparing Charging",
    10: "Wait Vehicle Charging",
    11: "Charging Normal",
    12: "Charging Simplified",
    13: "Suspended Over-Current",
    14: "Suspended HF Switching",
    15: "Suspended EV Disconnected",
    16: "Finish Wait Vehicle",
    17: "Finish Wait Disconnect",
    18: "Error Protective Earth",
    19: "Error Power Failure",
    20: "Error Contactor Fault",
    21: "Error Charging",
    22: "Error Power Failure",
    23: "Error Error Temperature",
    24: "Error Illegal CP Value",
    25: "Error Illegal PP Value",
    26: "Error Too Many Restarts",
    27: "Error",
    28: "Error Message",
    29: "Error Message Not Authorised",
    30: "Error Message Cable Not Supported",
    31: "Error Message S2 Not Opened",
    32: "Error Message Time-Out",
    33: "Reserved",
    34: "In Operative",
    35: "Load Balancing Limited",
    36: "Load Balancing Forced Off",
    38: "Not Charging",
    39: "Solar Charging Wait",
    40: "Charging Non Charging",
    41: "Solar Charging",
    42: "Charge Point Ready, Waiting For Power",
    43: "Partial Solar Charging",
}

DISPLAY_ERROR_DICT: Final[dict[int, str]] = {
    0: "No Error",
    1: "Not able to charge. Please call for support.",
    2: "Charging not started yet, to continue please reconnect cable",
    3: "Too many retries. Please check your charging cable",
    4: "One moment please... Your charging session will resume shortly.",
    5: "One moment please... Your charging session will resume shortly.",
    6: "One moment please... Your charging session will resume shortly.",
    7: "S2 not open. Please reconnect cable.",
    101: "Error in installation. Please check installation",
    102: "Not able to charge. Please call for support.",
    103: "Input voltage too low, not able to charge.",
    104: "Not able to charge. Please call for support.",
    105: "Not able to charge. Please call for support.",
    106: "Not able to charge. Please call for support.",
    108: "Not displayed",
    109: "Not displayed",
    201: "Error in installation. Please check installation or call for support.",
    202: "Input voltage too low, not able to charge. Please call your installer.",
    203: "Inside temperature high. Charging will resume shortly.",
    204: "Temporary set to unavailable.",
    206: "Temporary set to unavailable. Contact CPO or try again later.",
    208: "Not displayed",
    209: "Not displayed",
    210: "Not displayed",
    211: "Not able to lock cable. Please call for support.",
    212: "Error in installation. Please check installation or call for support.",
    213: "Not displayed",
    301: "One moment please your charging session will resume shortly.",
    302: "One moment please your charging session will resume shortly.",
    303: "One moment please your charging session will resume shortly.",
    304: "Charging not started yet to continue please reconnect cable.",
    401: "Inside temperature high. Charging will resume shortly.",
    402: "Inside temperature low. Charging will resume shortly.",
    404: "Not able to lock cable. Please reconnect cable.",
    405: "Cable not supported. Please try connecting your cable again.",
    406: "No communication with vehicle. Please check your charging cable.",
    407: "Not displayed",
}

MODE_3_STAT_DICT: Final[dict[int, str]] = {
    160: "STATE_A",
    161: "STATE_A1",
    162: "STATE_A1",
    177: "STATE_B1",
    178: "STATE_B2",
    193: "STATE_C1",
    194: "STATE_C2",
    209: "STATE_D1",
    210: "STATE_D2",
    14: "STATE_E",
    240: "STATE_F",
}

ALLOWED_PHASE_DICT: Final[dict[int, str]] = {1: "1 Phase", 3: "3 Phases"}

POWER_STATES_DICT: Final[dict[int, str]] = {
    0: "Unknown",
    1: "Inactive",
    2: "Connected ISO15118",
    3: "Wait for EV Connect",
    4: "EV Connected",
    5: "Active",
    6: "Wait for S2 Close",
    7: "Wait for S2 Open",
    8: "Suspended",
    9: "Ventilating",
    10: "Wakeup State E",
    11: "Wakeup State B1",
    12: "Error",
    13: "Error EV Detect",
    14: "Wait for EV Disconnect",
    15: "Prepared",
    16: "Connected ISO15118 Error",
    17: "Count",
}

MAIN_STATE_DICT: Final[dict[int, str]] = {
    -1: "Illegal",
    0: "Unknown",
    1: "Booting",
    2: "Available",
    3: "Cable Connected",
    4: "Cable Connected Timeout",
    5: "EV Connected",
    6: "Button Activated",
    7: "NFC Available",
    8: "NFC Authorised",
    9: "Wait for EV Connect",
    10: "Charging Test Relays",
    11: "Charging Power Off",
    12: "Charging Power Off Low Max Current",
    13: "Charging Power Starting",
    14: "Charging Power On",
    15: "Charging Power On Simplified",
    16: "Charging Wait for EV Reconnect",
    17: "Charging Terminating",
    18: "Charging Wakeup",
    19: "Wait for Disconnect",
    20: "Wait for Release Authorisation",
    21: "Charging Recover from Outage",
    22: "Error",
    23: "Error Message",
    24: "Error Message Cable not Supported",
    25: "Error Illegal Mode 3",
    26: "Error Too Many Restarts",
    27: "Error Charging",
    28: "Error Charging Overcurrent",
    29: "Error Charging HF Contactor Switching",
    30: "Error S2 Not Opened",
    31: "Error Protective Earth",
    32: "Error Relays",
    33: "Error Low Supply Voltage",
    34: "Error Internal Voltage",
    35: "Error Powermeter",
    36: "Error Temperature",
    37: "Suspended",
    38: "Inoperative",
    39: "Reserved",
    40: "Error Charging RCD Signaled",
    41: "Charging Power Off Ventilating",
    42: "Charging Power Off Suspended",
    43: "Charging Pwoer OFf Phase Change",
    44: "Wait for Start Metervalue",
    45: "Wait for Stop Metervalue",
    46: "Error Socket Motor",
    47: "Cable Conencted Type E",
    48: "Cable Connected Time out Type E",
    49: "Charging Type E",
    50: "Wait for Disconnect Type E",
    51: "Charging Suspended Type E",
    52: "Charging Low Max Current Type E",
    53: "Invalid Card",
    54: "EV Connected Unauthorized",
    55: "Wait for Disconnect PP",
}

MAIN_STATE__TMP_DICT: Final[dict[int, str]] = {
    0: "Unknown",
    1: "Available",
    2: "Authorising",
    4: "EV Connected",
    5: "Active",
    8: "Rejected",
    15: "Booting",
    16: "Cable Connected",
    17: "Count",
    19: "Cable Connected Authorising",
    20: "Cable Connected Authorised",
    24: "Cable Connected Rejected",
    48: "EV Connected",
    50: "EV Connected Authorising",
    52: "EV Connected Authorised",
    56: "EV Connected Rejected",
    65: "Cable Locked",
    66: "Cable Started",
    67: "Charging",
    68: "Charging Finishing",
    69: "Charging Finished",
    70: "Cable Unlock",
    71: "Suspended EV",
    72: "Suspended EVSE",
    79: "Wait for Cable Disconnect",
    128: "Timeout Waiting for Cable",
    129: "Timeout Waiting for EV Connect",
    130: "Timeout Waiting for Authorisation",
    131: "Timeout Waiting for S2",
    132: "Timeout Waiting for Cable Removal",
    159: "Offline",
    160: "Inoperative",
    161: "Reserved",
    192: "Error Mask",
    193: "Error Relay",
    194: "Error Temperature",
    195: "Error Overcurrent",
    196: "Error Socket Motor",
    197: "Error Illegal Mode 3",
    198: "Error Energy Meter",
    199: "Error Phase",
    200: "Error Internal RCD",
    201: "Error HF Switching",
    202: "Error Low Supply Voltage",
}

OCPP_BOOT_NOTIFICATION_STATUS_DICT: Final[dict[int, str]] = {
    0: "Not Sent",
    1: "Awaiting Reply",
    2: "Rejected",
    3: "Accepted",
    4: "Pending",
}

MODBUS_CONNECTION_STATES_DICT: Final[dict[int, str]] = {
    0: "Idle",
    1: "Initializing",
    2: "Normal",
    3: "Warning",
    4: "Error",
}

ALFEN_SENSOR_TYPES: Final[tuple[AlfenSensorDescription, ...]] = (
    AlfenSensorDescription(
        key="status_socket_1",
        name="Status Code Socket 1",
        icon="mdi:ev-station",
        api_param="2501_2",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="uptime",
        name="Uptime",
        icon="mdi:timer-outline",
        api_param="2060_0",
        unit=UnitOfTime.DAYS,
        round_digits=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlfenSensorDescription(
        key="uptime_hours",
        name="Uptime Hours",
        icon="mdi:timer-outline",
        api_param="2060_0",
        unit=UnitOfTime.HOURS,
        round_digits=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlfenSensorDescription(
        key="last_modify_datetime",
        name="Last Modify Config datetime",
        icon="mdi:timer-outline",
        api_param="2187_0",
        unit=None,
        state_class=SensorDeviceClass.DATE,
        round_digits=None,
    ),
    # too much logging data
    # AlfenSensorDescription(
    #     key="system_date_time",
    #     name="System Datetime",
    #     icon="mdi:timer-outline",
    #     api_param="2059_0",
    #     unit=None,
    #     round_digits=None,
    # ),
    AlfenSensorDescription(
        key="bootups",
        name="Bootups",
        icon="mdi:reload",
        api_param="2056_0",
        unit=None,
        round_digits=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
    ),
    AlfenSensorDescription(
        key="frequency_socket_1",
        name="Frequency Socket 1",
        icon="mdi:information-outline",
        api_param="2221_12",
        unit=UnitOfFrequency.HERTZ,
        round_digits=0,
    ),
    AlfenSensorDescription(
        key="voltage_l1_socket_1",
        name="Voltage L1N Socket 1",
        icon="mdi:flash",
        api_param="2221_3",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="voltage_l2_socket_1",
        name="Voltage L2N Socket 1",
        icon="mdi:flash",
        api_param="2221_4",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="voltage_l3_socket_1",
        name="Voltage L3N Socket 1",
        icon="mdi:flash",
        api_param="2221_5",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # AlfenSensorDescription(
    #     key="voltage_l1l2_socket_1",
    #     name="Voltage L1L2 Socket 1",
    #     icon="mdi:flash",
    #     api_param="2221_6",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="voltage_l2l3_socket_1",
    #     name="Voltage L2L3 Socket 1",
    #     icon="mdi:flash",
    #     api_param="2221_7",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="voltage_l3l1_socket_1",
    #     name="Voltage L3L1 Socket 1",
    #     icon="mdi:flash",
    #     api_param="2221_8",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    AlfenSensorDescription(
        key="current_n_socket_1",
        name="Current N Socket 1",
        icon="mdi:current-ac",
        api_param="2221_9",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l1_socket_1",
        name="Current L1 Socket 1",
        icon="mdi:current-ac",
        api_param="2221_A",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l2_socket_1",
        name="Current L2 Socket 1",
        icon="mdi:current-ac",
        api_param="2221_B",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l3_socket_1",
        name="Current L3 Socket 1",
        icon="mdi:current-ac",
        api_param="2221_C",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_total_socket_1",
        name="Current total Socket 1",
        icon="mdi:current-ac",
        api_param="2221_D",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="active_power_total_socket_1",
        name="Active Power Total Socket 1",
        icon="mdi:circle-slice-3",
        api_param="2221_16",
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="meter_reading_socket_1",
        name="Meter Reading Socket 1",
        icon="mdi:counter",
        api_param="2221_22",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    AlfenSensorDescription(
        key="temperature",
        name="Temperature",
        icon="mdi:thermometer",
        api_param="2201_0",
        unit=UnitOfTemperature.CELSIUS,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.TEMPERATURE,
    ),
    AlfenSensorDescription(
        key="main_static_lb_max_current_socket_1",
        name="Main Static LB Max Current Socket 1",
        icon="mdi:current-ac",
        api_param="212B_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_active_lb_max_current_socket_1",
        name="Main Active LB Max Current Socket 1",
        icon="mdi:current-ac",
        api_param="212D_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="charging_box_identifier",
        name="Charging Box Identifier",
        icon="mdi:ev-station",
        api_param="2053_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="boot_reason",
        name="System Boot Reason",
        icon="mdi:reload",
        api_param="2057_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="p1_measurements_1",
        name="P1 Meter Phase 1 Current",
        icon="mdi:current-ac",
        api_param="212F_1",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="p1_measurements_2",
        name="P1 Meter Phase 2 Current",
        icon="mdi:current-ac",
        api_param="212F_2",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="p1_measurements_3",
        name="P1 Meter Phase 3 Current",
        icon="mdi:current-ac",
        api_param="212F_3",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="gprs_apn_name",
        name="GPRS APN Name",
        icon="mdi:antenna",
        api_param="2100_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_apn_user",
        name="GPRS APN User",
        icon="mdi:antenna",
        api_param="2101_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_apn_password",
        name="GPRS APN Password",
        icon="mdi:antenna",
        api_param="2102_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_sim_pin",
        name="GPRS SIM Pin",
        icon="mdi:antenna",
        api_param="2103_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_sim_imsi",
        name="GPRS SIM IMSI",
        icon="mdi:antenna",
        api_param="2104_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_sim_iccid",
        name="GPRS SIM Serial",
        icon="mdi:antenna",
        api_param="2105_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_provider",
        name="GPRS Provider",
        icon="mdi:antenna",
        api_param="2112_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_wired_server_domain_and_port",
        name="Wired Url Server Domain And Port",
        icon="mdi:cable-data",
        api_param="2071_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_wired_server_path",
        name="Wired Url Wired Server Path",
        icon="mdi:cable-data",
        api_param="2071_2",
        unit=None,
        round_digits=None,
    ),
    # AlfenSensorDescription(
    #     key="comm_dhcp_address_1",
    #     name="GPRS DHCP Address",
    #     icon="mdi:antenna",
    #     api_param="2072_1",
    #     unit=None,
    #     round_digits=None,
    # ),
    AlfenSensorDescription(
        key="comm_netmask_address_1",
        name="GPRS Netmask",
        icon="mdi:antenna",
        api_param="2073_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_gateway_address_1",
        name="GPRS Gateway Address",
        icon="mdi:antenna",
        api_param="2074_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_ip_address_1",
        name="GPRS IP Address",
        icon="mdi:antenna",
        api_param="2075_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_short_name",
        name="Backoffice Short Name",
        icon="mdi:antenna",
        api_param="2076_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_gprs_server_domain_and_port",
        name="GPRS Url Server Domain And Port",
        icon="mdi:antenna",
        api_param="2078_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_bo_url_gprs_server_path",
        name="GPRS Url Server Path",
        icon="mdi:antenna",
        api_param="2078_2",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_gprs_dns_1",
        name="GPRS DNS 1",
        icon="mdi:antenna",
        api_param="2079_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_gprs_dns_2",
        name="GPRS DNS 2",
        icon="mdi:antenna",
        api_param="2080_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="gprs_signal_strength",
        name="GPRS Signal",
        icon="mdi:antenna",
        api_param="2110_0",
        unit=SIGNAL_STRENGTH_DECIBELS,
        round_digits=None,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
    ),
    # AlfenSensorDescription(
    #     key="comm_dhcp_address_2",
    #     name="Wired DHCP",
    #     icon="mdi:cable-data",
    #     api_param="207A_1",
    #     unit=None,
    #     round_digits=None,
    # ),
    AlfenSensorDescription(
        key="comm_netmask_address_2",
        name="Wired Netmask",
        icon="mdi:cable-data",
        api_param="207B_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_gateway_address_2",
        name="Wired Gateway Address",
        icon="mdi:cable-data",
        api_param="207C_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_ip_address_2",
        name="Wired IP Address",
        icon="mdi:cable-data",
        api_param="207D_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_wired_dns_1",
        name="Wired DNS 1",
        icon="mdi:cable-data",
        api_param="207E_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_wired_dns_2",
        name="Wired DNS 2",
        icon="mdi:cable-data",
        api_param="207F_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_wired_mac",
        name="Wired MAC address",
        icon="mdi:cable-data",
        api_param="2052_1",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_protocol_name",
        name="Protocol Name",
        icon="mdi:information-outline",
        api_param="2081_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_protocol_version",
        name="Protocol Version",
        icon="mdi:information-outline",
        api_param="2082_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="object_id",
        name="Charger Number",
        icon="mdi:information-outline",
        api_param="2051_0",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_car_cp_voltage_high_socket_1",
        name="Car CP Voltage High Socket 1",
        icon="mdi:lightning-bolt",
        api_param="2511_0",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="comm_car_cp_voltage_low_socket_1",
        name="Car CP Voltage Low Socket 1",
        icon="mdi:lightning-bolt",
        api_param="2511_1",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="comm_car_pp_resistance_socket_1",
        name="Car PP resistance Socket 1",
        icon="mdi:resistor",
        api_param="2511_2",
        unit="Ω",
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AlfenSensorDescription(
        key="comm_car_pwm_duty_cycle_socket_1",
        name="Car PWM Duty Cycle Socket 1",
        icon="mdi:percent",
        api_param="2511_3",
        unit=PERCENTAGE,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
    ),
    AlfenSensorDescription(
        key="ps_connector_1_max_allowed_phase",
        name="Connector 1 Max Allowed of Phases",
        icon="mdi:scale-balance",
        unit=None,
        api_param="312E_0",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="ui_state_1",
        name="Display State Socket 1",
        icon="mdi:information-outline",
        unit=None,
        api_param="3190_1",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="ui_error_number_1",
        name="Display Error Number Socket 1",
        icon="mdi:information-outline",
        unit=None,
        api_param="3190_2",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="mode_3_state_socket_1",
        name="Mode3 State Socket 1",
        icon="mdi:information-outline",
        unit=None,
        api_param="2501_4",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="cpo_name",
        name="CPO Name",
        icon="mdi:information-outline",
        unit=None,
        api_param="2722_0",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="power_state_socket_1",
        name="Power State Socket 1",
        icon="mdi:information-outline",
        unit=None,
        api_param="2501_3",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="main_state_socket_1",
        name="Main State Socket 1",
        icon="mdi:information-outline",
        unit=None,
        api_param="2501_1",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="ocpp_boot_notification_state",
        name="OCPP Boot notification State",
        icon="mdi:information-outline",
        unit=None,
        api_param="3600_1",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="modbus_tcp_ip_connection_state",
        name="Modbus TCP/IP Connection State",
        icon="mdi:information-outline",
        unit=None,
        api_param="2540_0",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="main_active_max_current_socket_1",
        name="Main Active Max Current Socket 1",
        icon="mdi:current-ac",
        api_param="212C_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_start_max_current",
        name="Main Start Max Current",
        icon="mdi:current-ac",
        api_param="2128_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
    ),
    AlfenSensorDescription(
        key="main_external_max_current_socket_1",
        name="Main External Max Current Socket 1",
        icon="mdi:current-ac",
        api_param="212A_0",
        unit=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        round_digits=2,
    ),
    AlfenSensorDescription(
        key="smart_meter_l1",
        name="Smart Meter Power L1",
        icon="mdi:transmission-tower",
        api_param=None,
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="smart_meter_l2",
        name="Smart Meter Power L2",
        icon="mdi:transmission-tower",
        api_param=None,
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="smart_meter_l3",
        name="Smart Meter Power L3",
        icon="mdi:transmission-tower",
        api_param=None,
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="smart_meter_total",
        name="Smart Meter Power Total",
        icon="mdi:transmission-tower",
        api_param=None,
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="smart_meter_voltage_l1",
        name="Smart Meter Voltage L1N",
        icon="mdi:flash",
        api_param="5221_3",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="smart_meter_voltage_l2",
        name="Smart Meter Voltage L2N",
        icon="mdi:flash",
        api_param="5221_4",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="smart_meter_voltage_l3",
        name="Smart Meter Voltage L3N",
        icon="mdi:flash",
        api_param="5221_5",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # AlfenSensorDescription(
    #     key="smart_meter_voltage_l1L2",
    #     name="Smart Meter Voltage L1L2",
    #     icon="mdi:flash",
    #     api_param="5221_6",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="smart_meter_voltage_l2l3",
    #     name="Smart Meter Voltage L2L3 Socket 2",
    #     icon="mdi:flash",
    #     api_param="5221_7",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="smart_meter_voltage_l3l1",
    #     name="Smart Meter Voltage L3L1 Socket 2",
    #     icon="mdi:flash",
    #     api_param="5221_8",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    AlfenSensorDescription(
        key="smart_meter_active_power_total",
        name="Smart Meter Active Power Total",
        icon="mdi:flash",
        api_param="5221_16",
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="smart_meter_current_l1",
        name="Smart Meter Current L1",
        icon="mdi:current-ac",
        api_param="5221_A",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="smart_meter_current_l2",
        name="Smart Meter Current L2",
        icon="mdi:current-ac",
        api_param="5221_B",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="smart_meter_current_l3",
        name="Smart Meter Current L3",
        icon="mdi:current-ac",
        api_param="5221_C",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="smart_meter_current_total",
        name="Smart Meter Current total",
        icon="mdi:current-ac",
        api_param="5221_D",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="number_of_socket",
        name="Number of Socket",
        icon="mdi:information-outline",
        unit=None,
        api_param="205E_0",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="main_external_min_current_socket_1",
        name="Main External Min Current Socket 1",
        icon="mdi:current-ac",
        api_param="2160_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_station_active_max_current_socket_1",
        name="Main Station Active Max Current Socket 1",
        icon="mdi:current-ac",
        api_param="2161_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="custom_tag_socket_1",
        name="Tag Socket 1",
        icon="mdi:badge-account-outline",
        api_param=None,
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_1_charging",
        name="Transaction Socket 1 Charging",
        icon="mdi:battery-charging",
        api_param=None,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_1_charging_time",
        name="Transaction Socket 1 Charging Time",
        icon="mdi:clock",
        api_param=None,
        unit=UnitOfTime.MINUTES,
        round_digits=0,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_1_charged",
        name="Transaction Socket 1 Last Charge",
        icon="mdi:battery-charging",
        api_param=None,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_1_charged_time",
        name="Transaction Socket 1 Last Charge Time",
        icon="mdi:clock",
        api_param=None,
        unit=UnitOfTime.MINUTES,
        round_digits=0,
    ),
)

ALFEN_SENSOR_DUAL_SOCKET_TYPES: Final[tuple[AlfenSensorDescription, ...]] = (
    AlfenSensorDescription(
        key="ps_connector_2_max_allowed_phase",
        name="Connector 2 Max Allowed of Phases",
        icon="mdi:scale-balance",
        unit=None,
        api_param="312F_0",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="main_state_socket_2",
        name="Main State Socket 2",
        icon="mdi:information-outline",
        unit=None,
        api_param="2502_1",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="status_socket_2",
        name="Status Code Socket 2",
        icon="mdi:ev-station",
        api_param="2502_2",
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="power_state_socket_2",
        name="Power State Socket 2",
        icon="mdi:information-outline",
        unit=None,
        api_param="2502_3",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="mode_3_state_socket_2",
        name="Mode3 State Socket 2",
        icon="mdi:information-outline",
        unit=None,
        api_param="2502_4",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="comm_car_cp_voltage_high_socket_2",
        name="Car CP Voltage High Socket 2",
        icon="mdi:lightning-bolt",
        api_param="2512_0",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="comm_car_cp_voltage_low_socket_2",
        name="Car CP Voltage Low Socket 2",
        icon="mdi:lightning-bolt",
        api_param="2512_1",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="comm_car_pp_resistance_socket_2",
        name="Car PP resistance Socket 2",
        icon="mdi:resistor",
        api_param="2512_2",
        unit="Ω",
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
    ),
    AlfenSensorDescription(
        key="comm_car_pwm_duty_cycle_socket_2",
        name="Car PWM Duty Cycle Socket 2",
        icon="mdi:percent",
        api_param="2512_3",
        unit=PERCENTAGE,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER_FACTOR,
    ),
    AlfenSensorDescription(
        key="main_external_max_current_socket_2",
        name="Main External Max Current Socket 2",
        icon="mdi:current-ac",
        api_param="312A_0",
        unit=UnitOfElectricCurrent.AMPERE,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
        round_digits=2,
    ),
    AlfenSensorDescription(
        key="main_static_lb_max_current_socket_2",
        name="Main Static LB Max Current Socket 2",
        icon="mdi:current-ac",
        api_param="312B_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_active_lb_max_current_socket_2",
        name="Main Active LB Max Current Socket 2",
        icon="mdi:current-ac",
        api_param="312D_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_external_min_current_socket_2",
        name="Main External Min Current Socket 2",
        icon="mdi:current-ac",
        api_param="3160_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="main_active_max_current_socket_2",
        name="Main Active Max Current Socket 2",
        icon="mdi:current-ac",
        api_param="312C_0",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="ui_state_2",
        name="Display State Socket 2",
        icon="mdi:information-outline",
        unit=None,
        api_param="3191_1",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="ui_error_number_2",
        name="Display Error Number Socket 2",
        icon="mdi:information-outline",
        unit=None,
        api_param="3191_2",
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="frequency_socket_2",
        name="Frequency Socket 2",
        icon="mdi:information-outline",
        api_param="3221_12",
        unit=UnitOfFrequency.HERTZ,
        round_digits=0,
    ),
    AlfenSensorDescription(
        key="meter_reading_socket_2",
        name="Meter Reading Socket 2",
        icon="mdi:counter",
        api_param="3221_22",
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
        state_class=SensorStateClass.TOTAL_INCREASING,
        device_class=SensorDeviceClass.ENERGY,
    ),
    AlfenSensorDescription(
        key="active_power_total_socket_2",
        name="Active Power Total Socket 2",
        icon="mdi:circle-slice-3",
        api_param="3221_16",
        unit=UnitOfPower.WATT,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.POWER,
    ),
    AlfenSensorDescription(
        key="voltage_l1_socket_2",
        name="Voltage L1N Socket 2",
        icon="mdi:flash",
        api_param="3221_3",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="voltage_l2_socket_2",
        name="Voltage L2N Socket 2",
        icon="mdi:flash",
        api_param="3221_4",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    AlfenSensorDescription(
        key="voltage_l3_socket_2",
        name="Voltage L3N Socket 2",
        icon="mdi:flash",
        api_param="3221_5",
        unit=UnitOfElectricPotential.VOLT,
        round_digits=1,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.VOLTAGE,
    ),
    # AlfenSensorDescription(
    #     key="voltage_l1l2_socket_2",
    #     name="Voltage L1L2 Socket 2",
    #     icon="mdi:flash",
    #     api_param="3221_6",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="voltage_l2l3_socket_2",
    #     name="Voltage L2L3 Socket 2",
    #     icon="mdi:flash",
    #     api_param="3221_7",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    # AlfenSensorDescription(
    #     key="voltage_l3l1_socket_2",
    #     name="Voltage L3L1 Socket 2",
    #     icon="mdi:flash",
    #     api_param="3221_8",
    #     unit=UnitOfElectricPotential.VOLT,
    #     round_digits=1,
    #     state_class=SensorStateClass.MEASUREMENT,
    #     device_class=SensorDeviceClass.VOLTAGE,
    # ),
    AlfenSensorDescription(
        key="current_n_socket_2",
        name="Current N Socket 2",
        icon="mdi:current-ac",
        api_param="3221_9",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l1_socket_2",
        name="Current L1 Socket 2",
        icon="mdi:current-ac",
        api_param="3221_A",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l2_socket_2",
        name="Current L2 Socket 2",
        icon="mdi:current-ac",
        api_param="3221_B",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_l3_socket_2",
        name="Current L3 Socket 2",
        icon="mdi:current-ac",
        api_param="3221_C",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="current_total_socket_2",
        name="Current total Socket 2",
        icon="mdi:current-ac",
        api_param="3221_D",
        unit=UnitOfElectricCurrent.AMPERE,
        round_digits=2,
        state_class=SensorStateClass.MEASUREMENT,
        device_class=SensorDeviceClass.CURRENT,
    ),
    AlfenSensorDescription(
        key="custom_tag_socket_2",
        name="Tag Socket 2",
        icon="mdi:badge-account-outline",
        api_param=None,
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_2_stop",
        name="Transaction Socket 2 Stop",
        icon="mdi:badge-account-outline",
        api_param=None,
        unit=None,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_2_charging",
        name="Transaction Socket 2 Charging",
        icon="mdi:battery-charging",
        api_param=None,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_2_charging_time",
        name="Transaction Socket 2 Charging Time",
        icon="mdi:clock",
        api_param=None,
        unit=UnitOfTime.MINUTES,
        round_digits=0,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_2_charged",
        name="Transaction Socket 2 Last Charge",
        icon="mdi:battery-charging",
        api_param=None,
        unit=UnitOfEnergy.KILO_WATT_HOUR,
        round_digits=None,
    ),
    AlfenSensorDescription(
        key="custom_transaction_socket_2_charged_time",
        name="Transaction Socket 2 Last Charge Time",
        icon="mdi:clock",
        api_param=None,
        unit=UnitOfTime.MINUTES,
        round_digits=0,
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None,
):
    """Set up the Alfen sensor."""


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
):
    """Set up using config_entry."""
    sensors = [AlfenSensor(entry, description) for description in ALFEN_SENSOR_TYPES]

    async_add_entities(sensors)
    async_add_entities([AlfenMainSensor(entry, ALFEN_SENSOR_TYPES[0])])

    coordinator = entry.runtime_data
    if coordinator.device.number_socket == 2:
        sensors = [
            AlfenSensor(entry, description)
            for description in ALFEN_SENSOR_DUAL_SOCKET_TYPES
        ]
        async_add_entities(sensors)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_REBOOT_WALLBOX,
        {},
        "async_reboot_wallbox",
    )


class AlfenMainSensor(AlfenEntity):
    """Representation of a Alfen Main Sensor."""

    entity_description: AlfenSensorDescription

    def __init__(
        self, entry: AlfenConfigEntry, description: AlfenSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry)

        self._sensor = "sensor"
        self.entity_description = description

    @property
    def unique_id(self):
        """Return a unique ID."""
        return f"{self.coordinator.device.id}-{self._sensor}"

    @property
    def icon(self):
        """Return the icon."""
        return "mdi:car-electric"

    @property
    def state(self):
        """Return the state of the sensor."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                # exception
                # status only from socket 1
                if prop[ID] == "2501_2":
                    return STATUS_DICT.get(prop[VALUE], "Unknown")

                if self.entity_description.round_digits is not None:
                    return round(prop[VALUE], self.entity_description.round_digits)

                return prop[VALUE]

        return "Unknown"

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return {"category": prop[CAT]}
        return None

    async def async_reboot_wallbox(self):
        """Reboot the wallbox."""
        await self.coordinator.device.reboot_wallbox()

    async def async_update(self):
        """Update the sensor."""
        await self.coordinator.device.async_update()

    @property
    def device_info(self):
        """Return a device description for device registry."""
        return self.coordinator.device.device_info


class AlfenSensor(AlfenEntity, SensorEntity):
    """Representation of a Alfen Sensor."""

    entity_description: AlfenSensorDescription

    def __init__(
        self, entry: AlfenConfigEntry, description: AlfenSensorDescription
    ) -> None:
        """Initialize the sensor."""
        super().__init__(entry)

        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{self._attr_unique_id}-{description.key}"
        self.entity_description = description
        if description.state_class is not None:
            self._attr_state_class = description.state_class
        if description.device_class is not None:
            self._attr_device_class = description.device_class

        self._async_update_attrs()

    def _get_current_value(self) -> StateType | None:
        """Get the current value."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE]
        return None

    @callback
    def _async_update_attrs(self) -> None:
        """Update the state and attributes."""
        self._attr_native_value = self._get_current_value()

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return f"{self.coordinator.device.id}-{self.entity_description.key}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._attr_name

    @property
    def icon(self) -> str | None:
        """Return the icon of the sensor."""
        return self.entity_description.icon

    @property
    def native_value(self) -> StateType:
        """Return the state of the sensor."""
        return round(self.state, 2)

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit the value is expressed in."""
        return self.entity_description.unit

    def _processTransactionKWh(
        self, socket: str, entity_description: AlfenSensorDescription
    ):
        if self.coordinator.device.latest_tag is None:
            return "Unknown"
        ## calculate the usage
        startkWh = None
        mvkWh = None
        stopkWh = None
        lastkWh = None

        for key, value in self.coordinator.device.latest_tag.items():
            if key[0] == socket and key[1] == "start" and key[2] == "kWh":
                startkWh = value
                continue
            if key[0] == socket and key[1] == "mv" and key[2] == "kWh":
                mvkWh = value
                continue
            if key[0] == socket and key[1] == "stop" and key[2] == "kWh":
                stopkWh = value
                continue
            if key[0] == socket and key[1] == "last_start" and key[2] == "kWh":
                lastkWh = value
                continue

        # if the entity_key end with _charging, then we are calculating the charging
        if (
            startkWh is not None
            and mvkWh is not None
            and entity_description.key.endswith("_charging")
        ):
            # if we have stopkWh and it is higher then mvkWh, then we are not charging anymore and we should return 0
            if stopkWh is not None and float(stopkWh) >= float(mvkWh):
                return 0
            value = round(float(mvkWh) - float(startkWh), 2)
            if entity_description.round_digits is not None:
                return round(
                    value,
                    (
                        entity_description.round_digits
                        if entity_description.round_digits > 0
                        else None
                    ),
                )
            return value

        # if the entity_key end with _charged, then we are calculating the charged
        if (
            lastkWh is not None
            and stopkWh is not None
            and entity_description.key.endswith("_charged")
        ):
            if float(stopkWh) >= float(lastkWh):
                value = round(float(stopkWh) - float(lastkWh), 2)
                if entity_description.round_digits is not None:
                    return round(
                        value,
                        (
                            entity_description.round_digits
                            if entity_description.round_digits > 0
                            else None
                        ),
                    )
                return value
        return None

    def _processTransactionTime(
        self, socket: str, entity_description: AlfenSensorDescription
    ):
        if self.coordinator.device.latest_tag is None:
            return "Unknown"

        startDate = None
        mvDate = None
        stopDate = None
        lastDate = None

        for key, value in self.coordinator.device.latest_tag.items():
            if key[0] == "socket 1" and key[1] == "start" and key[2] == "date":
                startDate = value
                continue
            if key[0] == "socket 1" and key[1] == "mv" and key[2] == "date":
                mvDate = value
                continue
            if key[0] == "socket 1" and key[1] == "stop" and key[2] == "date":
                stopDate = value
                continue
            if key[0] == "socket 1" and key[1] == "last_start" and key[2] == "date":
                lastDate = value
                continue

        if (
            startDate is not None
            and mvDate is not None
            and entity_description.key.endswith("_charging_time")
        ):
            startDate = datetime.datetime.strptime(startDate, "%Y-%m-%d %H:%M:%S")
            mvDate = datetime.datetime.strptime(mvDate, "%Y-%m-%d %H:%M:%S")
            stopDate = datetime.datetime.strptime(stopDate, "%Y-%m-%d %H:%M:%S")

            # if there is a stopdate greater then startDate, then we are not charging anymore
            if stopDate is not None and stopDate > startDate:
                return 0

            # return the value in minutes
            value = round((mvDate - startDate).total_seconds() / 60, 2)
            if entity_description.round_digits is not None:
                return round(
                    value,
                    (
                        entity_description.round_digits
                        if entity_description.round_digits > 0
                        else None
                    ),
                )
            return value

        if (
            lastDate is not None
            and stopDate is not None
            and entity_description.key.endswith("_charged_time")
        ):
            lastDate = datetime.datetime.strptime(lastDate, "%Y-%m-%d %H:%M:%S")
            stopDate = datetime.datetime.strptime(stopDate, "%Y-%m-%d %H:%M:%S")

            if stopDate < lastDate:
                return None
            # return the value in minutes
            value = round((stopDate - lastDate).total_seconds() / 60, 2)
            if entity_description.round_digits is not None:
                return round(
                    value,
                    (
                        entity_description.round_digits
                        if entity_description.round_digits > 0
                        else None
                    ),
                )
            return value
        return None

    def _customTransactionCode(self, socker_number: int):
        if self.entity_description.key == f"custom_tag_socket_{socker_number}":
            if self.coordinator.device.latest_tag is None:
                return "No Tag"
            for key, value in self.coordinator.device.latest_tag.items():
                if (
                    key[0] == f"socket {socker_number}"
                    and key[1] == "start"
                    and key[2] == "tag"
                ):
                    return value
            return "No Tag"

        if self.entity_description.key in (
            f"custom_transaction_socket_{socker_number}_charging",
            f"custom_transaction_socket_{socker_number}_charged",
        ):
            value = self._processTransactionKWh(
                f"socket {socker_number}", self.entity_description
            )
            if value is not None:
                return value

        if self.entity_description.key in [
            f"custom_transaction_socket_{socker_number}_charging_time",
            f"custom_transaction_socket_{socker_number}_charged_time",
        ]:
            value = self._processTransactionTime(
                "socket " + str(socker_number), self.entity_description
            )
            if value is not None:
                return value
        return None

    @property
    def state(self) -> StateType:  # noqa: C901
        """Return the state of the sensor."""
        # state of none Api param
        if self.entity_description.api_param is None:
            voltage_l1 = None
            voltage_l2 = None
            voltage_l3 = None
            current_l1 = None
            current_l2 = None
            current_l3 = None

            for prop in self.coordinator.device.properties:
                if prop[ID] == "5221_3":
                    voltage_l1 = prop[VALUE]
                if prop[ID] == "5221_4":
                    voltage_l2 = prop[VALUE]
                if prop[ID] == "5221_5":
                    voltage_l3 = prop[VALUE]
                if prop[ID] == "212F_1":
                    current_l1 = prop[VALUE]
                if prop[ID] == "212F_2":
                    current_l2 = prop[VALUE]
                if prop[ID] == "212F_3":
                    current_l3 = prop[VALUE]

            if self.entity_description.key == "smart_meter_l1":
                if voltage_l1 is not None and current_l1 is not None:
                    return round(float(voltage_l1) * float(current_l1), 2)
            if self.entity_description.key == "smart_meter_l2":
                if voltage_l2 is not None and current_l2 is not None:
                    return round(float(voltage_l2) * float(current_l2), 2)
            if self.entity_description.key == "smart_meter_l3":
                if voltage_l3 is not None and current_l3 is not None:
                    return round(float(voltage_l3) * float(current_l3), 2)
            if self.entity_description.key == "smart_meter_total":
                if (
                    voltage_l1 is not None
                    and current_l1 is not None
                    and voltage_l2 is not None
                    and current_l2 is not None
                    and voltage_l3 is not None
                    and current_l3 is not None
                ):
                    return round(
                        (
                            float(voltage_l1) * float(current_l1)
                            + float(voltage_l2) * float(current_l2)
                            + float(voltage_l3) * float(current_l3)
                        ),
                        2,
                    )

        # Custom code for transaction and tag
        for socketNr in [1, 2]:
            value = self._customTransactionCode(socketNr)
            if value is not None:
                return value

        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                # some exception of return value

                # Display state status
                if self.entity_description.api_param in ("3190_1", "3191_1"):
                    if prop[VALUE] == 28:
                        return "See error Number"

                    return STATUS_DICT.get(prop[VALUE], "Unknown")

                # meter_reading from w to kWh
                if self.entity_description.api_param in ("2221_22", "3221_22"):
                    return round((prop[VALUE] / 1000), 2)

                # Car PWM Duty cycle %
                if self.entity_description.api_param == "2511_3":
                    return round(
                        (prop[VALUE] / 100), self.entity_description.round_digits
                    )

                # change milliseconds to HH:MM:SS
                if self.entity_description.key == "uptime":
                    return str(datetime.timedelta(milliseconds=prop[VALUE])).split(
                        ".", maxsplit=1
                    )[0]

                if self.entity_description.key == "uptime_hours":
                    result = 0
                    value = str(datetime.timedelta(milliseconds=prop[VALUE]))
                    days = value.split(" day")
                    if len(days) > 1:
                        result = int(days[0]) * 24
                        hours = days[1].split(", ")[1].split(":", maxsplit=1)[0]
                    else:
                        hours = value.split(":", maxsplit=1)[0]
                    result += int(hours)
                    return result

                # change milliseconds to d/m/y HH:MM:SS
                if self.entity_description.api_param in ("2187_0", "2059_0"):
                    return datetime.datetime.fromtimestamp(prop[VALUE] / 1000).strftime(
                        "%d/%m/%Y %H:%M:%S"
                    )

                # Allowed phase 1 or Allowed Phase 2
                if (self.entity_description.api_param == "312E_0") | (
                    self.entity_description.api_param == "312F_0"
                ):
                    return ALLOWED_PHASE_DICT.get(prop[VALUE], "Unknown")

                if self.entity_description.round_digits is not None:
                    return round(prop[VALUE], self.entity_description.round_digits)

                # mode3_state
                if self.entity_description.api_param in ("2501_4", "2502_4"):
                    return MODE_3_STAT_DICT.get(prop[VALUE], "Unknown")

                # Socket CPRO State
                if self.entity_description.api_param in ("2501_3", "2502_3"):
                    return POWER_STATES_DICT.get(prop[VALUE], "Unknown")

                # Main CSM State
                if self.entity_description.api_param in ("2501_1", "2502_1"):
                    return MAIN_STATE_DICT.get(prop[VALUE], "Unknown")

                # OCPP Boot notification
                if self.entity_description.api_param == "3600_1":
                    return OCPP_BOOT_NOTIFICATION_STATUS_DICT.get(
                        prop[VALUE], "Unknown"
                    )

                # OCPP Boot notification
                if self.entity_description.api_param == "2540_0":
                    return MODBUS_CONNECTION_STATES_DICT.get(prop[VALUE], "Unknown")

                # wallbox display message
                if self.entity_description.api_param in ("3190_2", "3191_2"):
                    return (
                        str(prop[VALUE])
                        + ": "
                        + DISPLAY_ERROR_DICT.get(prop[VALUE], "Unknown")
                    )

                # Status code
                if self.entity_description.api_param in ("2501_2", "2502_2"):
                    return STATUS_DICT.get(prop[VALUE], "Unknown")

                return prop[VALUE]
        return None

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return {"category": prop[CAT]}
        return None

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return self.entity_description.unit

    async def async_update(self):
        """Get the latest data and updates the states."""
        self._async_update_attrs()

    @property
    def device_info(self) -> DeviceInfo:
        """Return a device description for device registry."""
        return self.coordinator.device.device_info
