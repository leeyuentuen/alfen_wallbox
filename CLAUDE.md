# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Home Assistant custom integration for Alfen EV Wallboxes. It enables local control and monitoring of Alfen wallbox charging stations through Home Assistant. The integration communicates directly with the wallbox via its local HTTPS API.

## Architecture

### Core Components

- **AlfenDevice** ([alfen.py](custom_components/alfen_wallbox/alfen.py)): Core API client that handles:
  - HTTPS communication with the wallbox (SSL with `CERT_NONE` due to self-signed certs)
  - Login/logout session management (only one session allowed at a time)
  - Property fetching by category with pagination
  - Transaction and log parsing
  - Request locking to prevent concurrent API calls

- **AlfenCoordinator** ([coordinator.py](custom_components/alfen_wallbox/coordinator.py)): DataUpdateCoordinator implementation that:
  - Manages periodic updates based on scan interval (default: 20 seconds)
  - Triggers immediate refresh after successfully applying user changes
  - Handles timeouts and connection errors with proper exception propagation (default timeout: 30 seconds)
  - Provides device data to all entity platforms
  - Optimized to avoid blocking on timeout (lets update_interval handle retries)

- **Entity Platforms**: Standard Home Assistant platforms (sensor, binary_sensor, number, select, switch, button, text) that expose wallbox properties and controls
  - **Entity Naming**: All entities include the device name prefix (e.g., "Alfen Wallbox Status Code Socket 1") to follow Home Assistant best practices
  - This ensures proper entity_id generation (e.g., `sensor.alfen_wallbox_status_code_socket_1`) and avoids name collisions
  - Both `AlfenSensor` and `AlfenMainSensor` classes set `_attr_name` with device prefix in their `__init__()` methods
  - **Entity Availability**: Entities remain available during transient failures to prevent sensors from becoming "unavailable" during brief network interruptions
  - The base `AlfenEntity` class overrides the `available` property to return `True`, allowing entities to display last known values from the preserved properties dict
  - During timeouts (20-30 seconds), all sensors continue showing their last successfully fetched values instead of becoming unavailable
  - This prevents dashboard gaps and provides better user experience during transient network issues

### Data Model

The wallbox organizes properties into **categories** that can be selectively refreshed:
- Default categories: `comm`, `display`, `generic`, `generic2`, `MbusTCP`, `meter1`, `meter2`, `meter4`, `ocpp`, `states`, `temp`
- Optional categories: `logs`, `transactions` (not fetched by default to reduce API load)
- `transactions` and `logs` are fetched less frequently when enabled (every 60 and 20 cycles respectively)
- Categories not selected are loaded once at startup (static properties)
- Properties are fetched with pagination using `offset` parameter
- Each property has an `id` (e.g., "2129_0"), `value`, and `cat` (category)

### Key Constraints

1. **Single Session Limit**: The wallbox allows only one active login. Using the official Alfen app requires logging out from Home Assistant first (handled via Login/Logout buttons).

2. **API Locking and Authentication** (Fixed as of 2026-01):
   - Uses proper `asyncio.Lock` objects to prevent concurrent requests
   - Three separate locks for different purposes:
     - `_lock`: Serializes HTTP requests to wallbox
     - `_updating_lock`: Serializes update cycles
     - `_update_values_lock`: Protects `update_values` dict access
   - Requests now **wait** for locks instead of being silently dropped
   - Locks are automatically released even on errors (via context managers)
   - **Proactive login**: Integration logs in proactively at start of update cycle if not authenticated, avoiding 401 warnings on first request

3. **SSL Context**: Requires custom SSL context with `DEFAULT` ciphers and `CERT_NONE` to handle the wallbox's self-signed certificate.

4. **Non-Chronological Logs**: Alfen logs are not in chronological order - they're organized in blocks. Log parsing extracts RFID tag information from connection/disconnection events using regex patterns for efficiency.

5. **Async Update Queue with Immediate Processing**:
   - Property updates are queued in `update_values` dict
   - `set_value()` queues the update AND immediately triggers a coordinator update cycle (no debounce)
   - Each update cycle: first pushes pending updates, then fetches fresh data in one efficient cycle
   - This provides instant feedback to users (typically <2 seconds instead of waiting up to 30 seconds)
   - **Smart category refresh**: After value updates, only fetches categories that contain the updated properties plus `states` for status
   - Generic category is fetched first after updates to ensure control properties are updated immediately
   - Failed updates remain in queue and retry automatically on subsequent cycles
   - Check logs for "Failed to update" warnings if values don't apply

6. **Performance Optimizations** (as of 2026-01):
   - **Configurable Category Fetching**: Controls how categories are fetched each cycle:
     - By default fetches all categories per cycle (default 15, configurable 1-15 via options)
     - Can rotate through categories across multiple cycles if reduced
     - **Configurable delay between category fetches** (default 0 seconds, range 0-5s) to spread API load if needed
     - **Generic category always loaded at startup**: Ensures critical properties (licenses, socket count) are available before entity creation, fixing entity min/max value detection
     - Pending value updates and user commands are always processed immediately (not rotated)
   - **Tunable settings**: If you experience wallbox instability, you can adjust via integration options:
     - Increase scan interval (default 20s, range 1-300s) to reduce update frequency
     - Decrease categories per cycle (default 15, range 1-15) to fetch fewer categories per update
     - Increase category fetch delay (default 0s, range 0-5s) to spread API load
   - Property dict building preserves unfetched categories between cycles
   - Log parsing uses regex patterns and bounded deque (maxlen=500) to limit memory
   - **Log fetching happens every 20 cycles (~7 minutes with default 20s interval)** to reduce API load
   - **Logs removed from default categories** to prevent memory leaks on wallbox hardware
   - Transaction fetching happens every 60 cycles (~20 minutes with default 20s interval)
   - Update cycle timing is logged (info if >2s, debug otherwise)
   - Per-category timing is logged (info if >5s, debug otherwise) to identify slow categories
   - Static properties are cached and only fetched once at startup
   - Default scan interval set to 20 seconds for responsive updates
   - Default timeout set to 30 seconds to prevent premature timeouts during normal operation

## Development

### Testing in Home Assistant

Since this is a Home Assistant integration, there's no traditional test framework. To test:

1. **Development Installation**:
   ```bash
   # Copy to Home Assistant config directory
   cp -r custom_components/alfen_wallbox <homeassistant_config>/custom_components/

   # Or use symlink for development
   ln -s $(pwd)/custom_components/alfen_wallbox <homeassistant_config>/custom_components/alfen_wallbox
   ```

2. **Restart Home Assistant**: Required after code changes
   ```bash
   # Via Home Assistant CLI or UI
   ha core restart
   ```

3. **Check Logs**: Monitor Home Assistant logs for errors
   ```bash
   # View logs in real-time
   tail -f <homeassistant_config>/home-assistant.log

   # Or use the UI: Settings > System > Logs
   ```

4. **Enable Debug Logging**: Add to `configuration.yaml`:
   ```yaml
   logger:
     default: info
     logs:
       custom_components.alfen_wallbox: debug
   ```

### Configuration

Integration is configured via UI (ConfigFlow in [config_flow.py](custom_components/alfen_wallbox/config_flow.py:78)):
- Initial setup: Host, username (default: "admin"), password, name
- Options (can be changed anytime via integration options if needed):
  - Scan interval (1-300s, default: 20s) - How often to update data
  - Timeout (1-30s, default: 30s) - Request timeout
  - Categories per cycle (1-15, default: 15) - Number of categories to fetch per update
  - Category fetch delay (0-5s, default: 0s) - Delay between category fetches to reduce wallbox load
  - Refresh categories - Which property categories to fetch regularly

### Services

Custom services defined in [services.yaml](custom_components/alfen_wallbox/services.yaml):
- `reboot_wallbox`
- `set_green_share` - Solar green share percentage
- `set_comfort_power` - Comfort charging power in Watts
- `enable_phase_switching` / `disable_phase_switching`
- `enable_rfid_authorization_mode` / `disable_rfid_authorization_mode`

### Property ID Reference

Common property IDs (see [const.py](custom_components/alfen_wallbox/const.py) for constants):
- `2129_0`: Current limit
- `2126_0`: RFID auth mode
- `2069_0`: Current phase
- `2185_0`: Phase switching enable
- `3280_2`: Green share percentage
- `3280_3`: Comfort power
- `205E_0`: Number of sockets
- `21A2_0`: License bitmap

Full API documentation: https://github.com/leeyuentuen/alfen_wallbox/wiki/API-paramID

### Version Management

- Current version defined in [manifest.json](custom_components/alfen_wallbox/manifest.json:12)
- Config entry versioning handled in [`async_migrate_entry()`](custom_components/alfen_wallbox/__init__.py:39)
- When adding new config options, increment VERSION in ConfigFlow and add migration logic

## Code Patterns

### Adding New Properties

1. Identify the property ID and category from the wallbox API
2. Add to appropriate entity platform (sensor.py, number.py, etc.)
3. Use existing entity classes as templates (e.g., `AlfenSensorEntity`)
4. Properties are automatically discovered via coordinator data

### Setting Values

Use `AlfenDevice.set_value()` which queues updates and triggers immediate processing:
```python
await device.set_value("property_id", value)
# Value is queued and coordinator update is triggered immediately
# Update cycle: pushes queued updates first, then fetches fresh data
```

**Important**:
- `set_value()` is now async and must be awaited
- Values are queued and an immediate coordinator update is triggered automatically
- Each update cycle pushes pending updates first, then fetches fresh data in one efficient operation
- This provides instant feedback without waiting for the next scheduled interval
- Failed updates automatically retry on subsequent cycles
- Enable debug logging to see "Queued value update", "Triggering immediate coordinator update", and "Failed to update" messages

### Accessing Device Data

```python
coordinator.device.properties["property_id"]["value"]
coordinator.device.info  # AlfenDeviceInfo object
coordinator.device.get_licenses()  # List of active licenses
```

## Testing

### Running Tests

The integration includes a comprehensive automated test suite that covers:
- Config flow and options flow
- Integration setup/teardown and migration
- Coordinator update cycles and error handling
- Device API communication and locking

**Run tests:**
```bash
# Install dependencies
uv pip install -r requirements_test.txt

# Run all tests
pytest tests/

# Run with coverage
pytest tests/ --cov=custom_components.alfen_wallbox --cov-report=term-missing

# Run specific test
pytest tests/test_config_flow.py::test_user_form_success -v
```

### Test Structure

- `tests/conftest.py` - Fixtures and test configuration
- `tests/test_alfen_device.py` - Device communication (66 tests)
- `tests/test_security.py` - Security features (56 tests)
- `tests/test_sensor.py` - Sensor entities (43 tests)
- `tests/test_translations.py` - Translation completeness (34 tests)
- `tests/test_number_comprehensive.py` - Number entities (19 tests)
- `tests/test_repairs.py` - Repair flows (10 tests)
- `tests/test_init.py` - Integration initialization (11 tests)
- `tests/test_switch.py` - Switch entities (10 tests)
- `tests/test_config_flow.py` - UI setup, options, and reconfigure (9 tests)
- `tests/test_coordinator.py` - Data update coordination (9 tests)
- `tests/test_select.py` - Select entities (9 tests)
- `tests/test_binary_sensor.py` - Binary sensor entities (7 tests)
- `tests/test_button.py` - Button entities (7 tests)
- `tests/test_entity.py` - Base entity (6 tests)
- `tests/test_text.py` - Text entities (6 tests)
- `tests/test_diagnostics.py` - Diagnostics (1 test)

**Total: 302 tests**

### Testing Philosophy

- **Mocked Communication**: All tests use mocked HTTP responses to avoid requiring physical hardware
- **Fast Execution**: Complete suite runs in ~12 seconds
- **Isolated Tests**: Each test is independent and can run in any order
- **Timeout Protection**: Tests timeout after 10 seconds to prevent hangs
- **Warning-Free**: Tests run without async/await warnings

### Adding New Tests

When adding new features:
1. Add test cases to relevant test file
2. Mock external dependencies (aiohttp, device responses)
3. Test both success and failure scenarios
4. Verify async behavior and locking
5. Ensure tests are deterministic (no race conditions)

## Performance & Monitoring

### Update Cycle Performance

The integration includes timing metrics to help identify performance issues:

- **Debug logging**: Shows update duration for cycles <2s
- **Info logging**: Warns when update cycles take >2s
- **Category timing**: Each category fetch logs its duration and property count

Enable debug logging to see detailed performance metrics:
```yaml
logger:
  logs:
    custom_components.alfen_wallbox: debug
```

### Memory Management

- **Log storage**: Uses `deque(maxlen=500)` to prevent unbounded growth
- **Property caching**: Static properties loaded once and reused
- **Update queue**: Pending updates stored efficiently in dict

### Optimization Guidelines

When modifying the code:
1. Avoid blocking operations in update cycle (no `sleep()` calls)
2. Use dict comprehensions for building property dicts
3. Prefer regex patterns over multiple string splits for parsing
4. Consider retry backoff times (currently 2s for property fetch retries)
5. Log timing info for operations that may be slow

## Security

### Security Measures

The integration implements several security measures (as of 2026-01):

1. **Login Rate Limiting**:
   - Maximum 5 login attempts per 60-second window
   - Prevents brute force attacks if network is compromised
   - Rate limit status logged as warnings

2. **URL Parameter Validation**:
   - API parameter IDs validated against `^[a-zA-Z0-9_-]+$` pattern
   - All URL parameters properly encoded using `urllib.parse.urlencode()`
   - Offset values validated and capped at 100,000 to prevent unbounded growth

3. **JSON Response Validation**:
   - Comprehensive validation of API response structure
   - Validates `properties` is a list and `total` is an integer
   - Each property validated to have required `id` field

4. **Exception Sanitization**:
   - All exception messages sanitized before logging
   - File paths replaced with `<path>`
   - IP addresses replaced with `<ip>`
   - Long alphanumeric strings (potential tokens) replaced with `<redacted>`
   - Messages truncated to 200 characters

5. **Diagnostics Data Sanitization**:
   - Sensitive properties (matching patterns like `*rfid*`, `*tag*`, `*password*`) are redacted
   - RFID tags hashed with SHA-256 (8-char prefix) for privacy
   - Safe for sharing in bug reports without exposing personal data

6. **RFID Tag Privacy**:
   - RFID tags in `latest_tag` are hashed before debug logging
   - Actual tag values available in memory for UI display
   - Diagnostics output shows hashed values only

### Known Security Considerations

1. **SSL Certificate Verification Disabled** (CRITICAL but unavoidable):
   - Wallbox uses self-signed certificates
   - `CERT_NONE` required for communication
   - Mitigated by local network deployment
   - Recommend isolating wallbox on separate VLAN if concerned

2. **Connection-Based Authentication**:
   - Wallbox authenticates the TCP connection, not requests
   - Session state managed via `logged_in` flag
   - Automatic re-authentication on 401 responses

3. **Credentials in Memory**:
   - Username/password stored in `AlfenDevice` instance
   - Required for re-authentication after connection drops
   - Home Assistant stores credentials encrypted in `.storage/`

## HACS & Home Assistant Compatibility

### Gold Tier Features (as of 2026-01)

The integration implements HACS/HA gold tier compatibility features:

1. **Entity Translations** ([strings.json](custom_components/alfen_wallbox/strings.json)):
   - Full translations for all entity types (sensor, binary_sensor, number, select, switch, button, text)
   - Service translations with name, description, and field descriptions
   - Issue/repair translations

2. **Entity Icons** ([icons.json](custom_components/alfen_wallbox/icons.json)):
   - Custom MDI icons for all entity types
   - Service icons

3. **Reconfigure Flow** ([config_flow.py](custom_components/alfen_wallbox/config_flow.py)):
   - `async_step_reconfigure()` allows changing host/credentials after initial setup
   - Accessible via integration options in Home Assistant UI

4. **Entity Categories**:
   - License sensors marked as `EntityCategory.DIAGNOSTIC`
   - System sensors (daylight savings, API status) marked as `EntityCategory.DIAGNOSTIC`
   - Helps organize entities in the Home Assistant UI

5. **Repair Issues** ([repairs.py](custom_components/alfen_wallbox/repairs.py)):
   - `connection_failed` - Guidance when wallbox is unreachable
   - `authentication_failed` - Guidance when credentials are invalid

6. **HACS Configuration** ([hacs.json](hacs.json)):
   - `render_readme: true` - Renders README in HACS
   - `homeassistant: "2024.1.0"` - Minimum HA version requirement

### Translation Files

Located in `custom_components/alfen_wallbox/translations/`:
- `en.json` - English (primary, synced with strings.json)
- `nl.json` - Dutch
- `de.json` - German
- `fr.json` - French
- `es.json` - Spanish
- `it.json` - Italian
- `sv.json` - Swedish
- `no.json` - Norwegian
- `da.json` - Danish

### Future Improvements

The following would further improve HA compatibility but require breaking changes:

1. **`_attr_has_entity_name = True`**: Would enable cleaner entity naming where device name is automatically prefixed. Currently disabled to avoid breaking existing entity IDs. Should be enabled in a future major version with proper migration.
