# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Home Assistant custom integration for Alfen EV Wallboxes. Enables local control and monitoring via the wallbox's HTTPS API.

## Development

This is a Home Assistant integration - there's no build system or test framework. To test changes:

1. Copy/symlink `custom_components/alfen_wallbox` to your Home Assistant config directory
2. Restart Home Assistant
3. Check logs: `tail -f <config>/home-assistant.log`

Enable debug logging in `configuration.yaml`:
```yaml
logger:
  logs:
    custom_components.alfen_wallbox: debug
```

## Architecture

### Core Flow

```
ConfigFlow (config_flow.py)
    ↓
AlfenCoordinator (coordinator.py) - DataUpdateCoordinator, manages update cycle
    ↓
AlfenDevice (alfen.py) - API client, handles all wallbox communication
    ↓
Entity Platforms (sensor.py, number.py, etc.) - expose properties to HA
```

### Key Classes

**AlfenDevice** (`alfen.py`): API client with three `asyncio.Lock` objects:
- `_lock`: Serializes HTTP requests to wallbox
- `_updating_lock`: Serializes update cycles
- `_update_values_lock`: Protects `update_values` dict access

**AlfenCoordinator** (`coordinator.py`): Wraps `AlfenDevice`, manages polling interval (default 5s), handles timeouts.

### Data Model

Properties are organized into **categories** (`const.py`): `comm`, `display`, `generic`, `generic2`, `MbusTCP`, `meter1`, `meter2`, `meter4`, `ocpp`, `states`, `temp`, `logs`, `transactions`.

- Selected categories refresh each update cycle
- Non-selected categories load once at startup (static)
- `transactions` only loads if explicitly selected
- Properties fetched with pagination via `offset` parameter
- Each property has `id` (e.g., "2129_0"), `value`, and `cat`

### Critical Constraints

1. **Single Session**: Wallbox allows only one login. Using official Alfen app requires logging out from HA first.

2. **Async Value Updates**: `set_value()` is async and queues updates for the next coordinator cycle - values are NOT sent immediately:
   ```python
   await device.set_value("2129_0", 16)  # Queued, sent on next update
   ```

3. **SSL Context**: Requires `CERT_NONE` and `DEFAULT` ciphers for self-signed certificate.

4. **Non-Chronological Logs**: Alfen logs are organized in blocks, not chronologically.

### Common Property IDs

| ID | Description |
|----|-------------|
| `2129_0` | Current limit |
| `2126_0` | RFID auth mode |
| `2069_0` | Current phase |
| `2185_0` | Phase switching enable |
| `3280_2` | Green share percentage |
| `3280_3` | Comfort power |
| `205E_0` | Number of sockets |
| `21A2_0` | License bitmap |

Full API docs: https://github.com/leeyuentuen/alfen_wallbox/wiki/API-paramID

## Adding New Entities

1. Identify property ID and category from wallbox API
2. Add entity description to appropriate platform file
3. Use existing entity classes as templates (e.g., `AlfenSensorEntity`)
4. Properties auto-discovered via coordinator data

## Version Management

- Version in `manifest.json`
- Config entry version in `config_flow.py` (VERSION = 2)
- Migration logic in `__init__.py:async_migrate_entry()`
