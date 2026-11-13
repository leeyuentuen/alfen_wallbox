
# Alfen Wallbox - HomeAssistant Integration

This is a custom component to allow control of Alfen Wallboxes in [HomeAssistant](https://home-assistant.io).

The component is a fork of the [Garo Wallbox custom integration](https://github.com/sockless-coding/garo_wallbox) and [egnerfl custom integration](https://github.com/egnerfl/alfen_wallbox)

## Recent Improvements

### Wallbox Crash Prevention (January 2026)

**Configurable category fetching to prevent wallbox crashes:**
- 🛡️ **Prevents watchdog resets** - Configurable settings to eliminate memory/CPU spikes that cause wallbox crashes
- ⚡ **Configurable API load** - Adjust categories per cycle (1-15) and fetch delay (0-5s) if needed
- 🔄 **Smart rotation** - When reduced, categories rotate across multiple cycles
- ⚡ **Fast update cycles** - Default 20s interval with all categories fetched per cycle
- ✨ **User commands unaffected** - Value updates and commands processed immediately
- 📊 **Tunable settings** - Adjust via integration options if you experience instability

**Benefits:** By default, all categories are fetched every cycle for maximum responsiveness. If you experience wallbox instability, you can reduce categories per cycle or add fetch delays via integration options.

### Responsiveness Improvements (January 2026)

**Better responsiveness and reduced API load:**
- ⚡ **Forced refresh after value updates** - Changes now apply immediately instead of waiting for next cycle
- ⚡ **Optimized default scan interval** - Default 20s for responsive updates (configurable 1-300s)
- ⚡ **Smarter update scheduling** - Automatic immediate refresh when users change settings
- 🔧 Users can configure different intervals via integration options if needed

**Benefits:** User changes (like current limit adjustments) are now visible immediately. Lower API traffic means better stability and less interference with the wallbox's single-session limitation.

### Performance Optimizations (January 2026)

**Major performance and efficiency improvements:**
- ⚡ Eliminated 60-second blocking on timeout - faster recovery from network issues
- ⚡ Optimized property updates with dictionary comprehensions
- ⚡ Improved log parsing using regex patterns (faster, less CPU)
- ⚡ Limited log memory usage to prevent unbounded growth (deque with maxlen=500)
- ⚡ Better error handling with timing metrics and detailed logging
- ⚡ Reduced retry backoff from 5s to 2s for faster recovery

**Benefits:** Lower memory usage, faster updates, better resilience, improved observability. See [CHANGELOG.md](CHANGELOG.md) for details.

### Reliability Fixes (January 2026)

**10 critical bug fixes for reliability:**
- ✅ Fixed race conditions causing silent failures when setting values
- ✅ Eliminated deadlocks from improper lock handling
- ✅ Fixed bitwise OR bugs in validation logic (current limit, green share, comfort power)
- ✅ Added automatic retry for failed updates
- ✅ Improved error logging and visibility

Previously, users experienced "silent failures" when changing settings (e.g., max current) - values wouldn't update and required manual retry. This has been resolved.

> After reverse engineering the API myself I found out that there is already a Python libary wrapping the Alfen API.
> https://gitlab.com/LordGaav/alfen-eve/-/tree/develop/alfeneve
> 
> https://github.com/leeyuentuen/alfen_wallbox/wiki/API-paramID

## Installation

### Install using HACS (recommended)
If you do not have HACS installed yet visit https://hacs.xyz for installation instructions.

To add the this repository to HACS in your Home Assistant instance, use this My button:

[![Open your Home Assistant instance and open a repository inside the Home Assistant Community Store.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?repository=alfen_wallbox&owner=leeyuentuen&category=Integration)

After installation, please reboot and add Alfen Wallbox device to your Home Assistant instance, use this My button:

[![Open your Home Assistant instance and start setting up a new integration.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=alfen_wallbox)

<details>
<summary><b><svg xmlns="http://www.w3.org/2000/svg" width="1em" height="1em" viewBox="0 0 24 24"><path fill="currentColor" d="m13.75 10.19l.63.13l4.17 2.08c.7.23 1.16.92 1.1 1.66v.26l-.9 6.12c-.06.43-.25.83-.6 1.11c-.31.3-.72.45-1.15.45h-6.88c-.49 0-.94-.18-1.27-.53L2.86 15.5l.9-1c.24-.25.62-.39.98-.37h.29L9 15V4.5a2 2 0 0 1 2-2a2 2 0 0 1 2 2v5.69z"></path></svg> Manual configuration steps</b></summary>

> - In HACS, go to the Integrations section and add the custom repository via the 3 dot menu on the top right. Enter ```https://github.com/>> leeyuentuen/alfen_wallbox``` in the Repository field, choose the ```Integration``` category, then click add.
Hit the big + at the bottom right and search for **Alfen Wallbox**. Click it, then click the download button.
> - Clone or copy this repository and copy the folder 'custom_components/alfen_wallbox' into '<homeassistant config>/custom_components/alfen_wallbox'
> - Once installed the Alfen Wallbox integration can be configured via the Home Assistant integration interface
where you can enter the IP address of the device.
</details>

### Home Assistant Energy Dashboard
The wallbox can be added to the Home Assistant Energy Dashboard using the `_meter_reading` sensor.

## Settings
The wallbox can be configured using the Integrations settings menu:

<img src="doc/screenshots/configure.png" alt="drawing" style="width:600px;"/>

### Configuration Options

- **Scan Interval** (1-300s, default: 20s) - How often to update data from the wallbox
- **Timeout** (1-30s, default: 30s) - Request timeout for API calls
- **Categories per Cycle** (1-15, default: 15) - Number of property categories to fetch per update cycle
- **Category Fetch Delay** (0-5s, default: 0s) - Delay between fetching categories to reduce wallbox load
- **Refresh Categories** - Select which property categories to fetch regularly (others load once at startup)

**Configurable Category Fetching:** By default, all categories are fetched every cycle for maximum responsiveness. If you experience wallbox instability (crashes, watchdog resets), you can reduce the categories per cycle and/or add a fetch delay via integration options. When categories per cycle is reduced below the total enabled categories, the integration rotates through them across multiple cycles.

Categories that are not selected will only load when the integration starts. The exception to this rule is the `transactions` category, which will load only if explicitly selected.

To locate a category, start by selecting all categories. Allow the integration to load, then find the desired entity. The category will be displayed in the entity's attributes.

<img src="doc/screenshots/attribute category.png" alt="drawing" style="width:400px;"/>

**Note:** If you reduce the categories per cycle below the total enabled categories, reducing the number of selected categories will enhance update frequency (fewer categories means faster rotation). The scan interval, categories per cycle, and fetch delay can all be adjusted via integration options to find the best balance for your wallbox.

### Which entities belong to which category

The wallbox decides which property is in which category. This list was taken from an Eve Single Pro-line with firmware 7.4.6; on other models or firmware a property can be in a different category.

| Category | Entities |
|---|---|
| `generic` | Active Load Balancing, Auth. Connection Timeout (s), Auth. Local List, Auth. Mode, Auth. Plug & Charge ID, Auth. Re-authorize after Power Outage (s), Auth. Restart after Power Outage, Auth. Whitelist, Backoffice Short Name, Boot Reason, Car Disconnect Action, Car Disconnection Timeout (s), Car Time to Report Not Charging (s), Car Time to Unlock Not Charging (s), Charge Point Vendor, Customer Ident. number, Display & LED Brightness, Display Language, Display Light Auto Dim, Ethernet MAC address, Firmware Version, GPRS DNS 1, GPRS DNS 2, GPRS Gateway Address, GPRS IP Address, GPRS Netmask, GPRS Network Mode, GPRS Provider, GPRS SIM IMSI, GPRS SIM Serial, GPRS Signal, GPRS Technology, Heartbeat interval (s), Load Balancing Max. Meter Current, Load Balancing Phase Connection, Load Balancing Received Measurements, Load Balancing Safe Current, Main Active LB Max Current Socket 1, Main Active LB Max Current Socket 2, Main Active Max Current Socket 1, Main Active Max Current Socket 2, Main External Max Current Socket 1, Main External Max Current Socket 2, Main External Min Current Socket 1, Main External Min Current Socket 2, Main Static LB Max Current Socket 1, Main Static LB Max Current Socket 2, Main Station Active Max Current Socket 1, Manufacturer Hardware Version, Manufacturer Software Version, Minimum Chameleon Current, Mobile Weak Signal Threshold, Model, Number of Sockets, Number of bootups, Object Number, Platform Type, Power Connector External Max Current Socket 1, Power Connector Max Current Socket 1, Power Connector Max Current Socket 2, Protocol Version, Socket 1 Operation Mode, Socket 1.2 Max Current, Socket 2.2 Max Current, Socket Type Socket 1, Socket Type Socket 2, Station maximum Current, System Datetime, System Daylight Savings, System Uptime, Timezone, WiFi DNS 1, WiFi DNS 2, WiFi Gateway Address, WiFi IP Address, WiFi Netmask, Wired DNS 1, Wired DNS 2, Wired Gateway Address, Wired IP Address, Wired Netmask |
| `generic2` | Bootloader Version, CPO Name, Display Error Number Socket 1, Display Error Number Socket 2, Display State Socket 1, Display State Socket 2, Installation Direct External Suspend Signal, Installation Max. Allowed Phases, Installation Max. Imbalance Current between phases, Last Modify Config datetime, Load Balancing Charging profiles random delay, Load Balancing Enable Phase Switching, P1 Meter Phase 1 Current, P1 Meter Phase 2 Current, P1 Meter Phase 3 Current, Proxy Address And Port, Proxy Enabled, Proxy Username, Solar Charging Boost Socket 1, Solar Charging Boost Socket 2, Solar Charging Mode, Solar Comfort Level, Solar Green Share, WiFi Enabled |
| `states` | Car CP Voltage High Socket 1, Car CP Voltage High Socket 2, Car CP Voltage Low Socket 1, Car CP Voltage Low Socket 2, Car PP resistance Socket 1, Car PP resistance Socket 2, Car PWM Duty Cycle Socket 1, Car PWM Duty Cycle Socket 2, Connector 1 Max Allowed of Phases, Connector 2 Max Allowed of Phases, Main State Socket 1, Main State Socket 2, Modbus TCP/IP Connection State, Mode3 State Socket 1, Mode3 State Socket 2, OCPP Boot Accept Time, OCPP Boot Last Time Send, OCPP Boot notification State, OCPP Heartbeat Last Failed, OCPP Heartbeat Last Sent, Power State Socket 1, Power State Socket 2, Status Code Socket 1, Status Code Socket 2 |
| `meter1` | Active Power Total Socket 1, Current L1 Socket 1, Current L2 Socket 1, Current L3 Socket 1, Current N Socket 1, Frequency Socket 1, Meter Reading Socket 1, Voltage L1N Socket 1, Voltage L2N Socket 1, Voltage L3N Socket 1 |
| `meter2` | Active Power Total Socket 2, Current L1 Socket 2, Current L2 Socket 2, Current L3 Socket 2, Current N Socket 2, Current total Socket 2, Frequency Socket 2, Meter Reading Socket 2, Smart Meter Real Power L1, Smart Meter Real Power L2, Smart Meter Real Power L3, Smart Meter Real Power Sum, Voltage L1N Socket 2, Voltage L2N Socket 2, Voltage L3N Socket 2 |
| `meter4` | Load Balancing DSMR/SMR Interface, Load Balancing Protocol, Smart Meter Active Power Total, Smart Meter Current L1, Smart Meter Current L2, Smart Meter Current L3, Smart Meter Current total, Smart Meter Voltage L1N, Smart Meter Voltage L2N, Smart Meter Voltage L3N |
| `temp` | Alarm Temperature High, Alarm Temperature low, Max Temperature, Minimum Temperature, Temperature |
| `comm` | Auth. Remote Transaction requests, OCPP Mobile OCPP reply timeout (s), OCPP Mobile OCPP send timeout (s), OCPP Wired OCPP reply timeout (s), OCPP Wired OCPP send timeout (s), WiFi AP Enabled, WiFi AP Start on Boot, WiFi Password, WiFi RSSI, WiFi SSID, WiFi Security, WiFi Status |
| `display` | Price Start Tariff, Price other, Price other description, Price per kWh, Price per minute |
| `ocpp` | Backoffice Network 1 Connection Priority (Ethernet), Backoffice Network 2 Connection Priority (GPRS) |
| `MbusTCP` | Load Balancing Data Source |
| `logs` | Tag Socket 1, Tag Socket 2 (see [Tag and Transaction Sensors](#tag-and-transaction-sensors)) |
| `transactions` | Transaction Socket 1/2 Charging, Charging Time, Last Charge, Last Charge Time, Transaction Socket 2 Stop |

Smart Meter Power L1, L2, L3 and Total are calculated from the voltage (`meter4`) and the current (`generic2`), so they need both categories.

## Simultaneous Use of the App and Integration
The Alfen charger allows only one active login session at a time. This means the Alfen MyEve or Eve Connect app cannot be used concurrently with the Home Assistant integration.

To manage this, the integration includes two buttons: HTTPS API Login and HTTPS API Logout.

- To switch to the Alfen app: Click the Logout button in the Home Assistant integration, then use your preferred Alfen app.
- To return to the integration: Click the Login button to reconnect the Home Assistant integration.

The HTTPS API Login Status binary sensor shows the current state of the login session.

## Tag and Transaction Sensors
The tag and transaction sensors (`sensor.<device>_tag_socket_1` and the
`sensor.<device>_transaction_socket_1_*` sensors) are built from the `logs` and
`transactions` categories of the wallbox. Those categories are **not refreshed by
default**, to limit the load on the wallbox API, so those sensors keep reporting
`No Tag` and `unknown` until they are selected.

To enable them, open the integration options (Configure) and add `logs` and
`transactions` to the refresh categories, then press the *Force fetch transaction*
button or wait for the next scheduled fetch (every 20 and 60 update cycles). The
integration logs a warning on setup while those categories are missing.

## Charging Insight Sensors

These entities are derived from properties the integration already reads, so they need
no extra requests to the wallbox:

| Entity | Description |
|---|---|
| **Charging Status** | Human-readable status of socket 1 (e.g. *Charging session active.*, *Waiting for power.*, *Solar charging using green mode.*, *Charging session has been paused.*). Attributes: `state_code`, `state`, `vehicle_connected`, `charging` |
| **Charging Limited By** | What currently limits the charging current (`218F_1`), e.g. `cable`, `alb_active`, `derating`. Attribute `group`: `load_balancing`, `vehicle` or `installation` |
| **Charging Restricted** (binary) | On while charging is held back by load balancing, the vehicle or the installation (not by the configured maximum current) |
| **Session Energy / Duration / Max Power** | Energy (kWh), duration and peak power of the current or last charging session; a session runs from connecting the vehicle until disconnecting |
| **Solar Charging Power / Grid Charging Power** | Split of the charging power using the smart meter's net power (`5221_16`): while exporting, all charging power counts as solar; while importing, the imported part counts as grid |
| **Green Share / Session Green Share** | Solar share (%) of the current charging power and of the energy charged in the session |

The solar / grid sensors are only available when a smart meter is connected to the wallbox.

## Services
Example of running in Services:
Note; The name of the configured charging point is "wallbox" in these examples.

### - Changing Green Share %
```
service: alfen_wallbox.set_green_share
data:
  entity_id: number.wallbox_solar_green_share
  value: 80
```

### - Changing Comfort Charging Power in Watt
```
service: alfen_wallbox.set_comfort_power
data:
  entity_id: number.wallbox_solar_comfort_level
  value: 1400
```

### - Enable phase switching
```
service: alfen_wallbox.enable_phase_switching
data:
  entity_id: switch.wallbox_enable_phase_switching
```


### - Disable phase switching
```
service: alfen_wallbox.disable_phase_switching
data:
  entity_id: switch.wallbox_enable_phase_switching
```

### - Enable RFID Authorization Mode
```
service: alfen_wallbox.enable_rfid_authorization_mode
data:
  entity_id: select.wallbox_authorization_mode
```

### - Disable RFID Authorization Mode
```
service: alfen_wallbox.disable_rfid_authorization_mode
data:
  entity_id: select.wallbox_authorization_mode
```

### - Reboot wallbox
```
service: alfen_wallbox.reboot_wallbox
data:
  entity_id: alfen_wallbox.garage
```

## Development & Testing

### Setup

**Install dependencies:**
```bash
uv pip install -r requirements_test.txt
```

### Running Tests

**Run all tests:**
```bash
pytest tests/
```

**Run with coverage:**
```bash
pytest tests/ --cov=custom_components.alfen_wallbox --cov-report=term-missing
```

**Run specific test file:**
```bash
pytest tests/test_config_flow.py -v
```

### Code Quality

**Type checking with mypy:**
```bash
mypy custom_components/alfen_wallbox
```

**Linting with ruff:**
```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

**Run all checks:**
```bash
# Full quality check
pytest tests/ && mypy custom_components/alfen_wallbox && ruff check .
```

### Test Structure

- `tests/test_config_flow.py` - Config flow and options flow tests
- `tests/test_init.py` - Integration setup and teardown tests
- `tests/test_coordinator.py` - Coordinator update cycle tests
- `tests/test_alfen_device.py` - Device API communication tests

All tests use mocked device communication to avoid requiring a physical wallbox.

## Screenshots
<img src="doc/screenshots/wallbox-1.png"/>

![Wallbox 2](<doc/screenshots/wallbox-2.png>)

![Wallbox 3](<doc/screenshots/wallbox-3.png>)
