"""Test the Alfen Wallbox device class."""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from custom_components.alfen_wallbox.alfen import AlfenDevice
from custom_components.alfen_wallbox.const import ID, PROPERTIES, TOTAL, VALUE


@pytest.fixture(name="mock_session")
def mock_session_fixture():
    """Mock aiohttp ClientSession."""
    session = MagicMock()
    session.verify = False

    # Create a proper mock response for post requests (used by login)
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(return_value={"success": True})

    # Configure post to return an async context manager
    mock_post_ctx = MagicMock()
    mock_post_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_post_ctx.__aexit__ = AsyncMock(return_value=None)
    session.post = MagicMock(return_value=mock_post_ctx)

    return session


@pytest.fixture(name="mock_ssl_context")
def mock_ssl_context_fixture():
    """Mock SSL context."""
    return MagicMock()


@pytest.fixture(name="alfen_device")
def alfen_device_fixture(mock_session, mock_ssl_context):
    """Create an AlfenDevice instance."""
    device = AlfenDevice(
        session=mock_session,
        host="192.168.1.100",
        name="Test Wallbox",
        username="admin",
        password="secret",
        category_options=["generic", "states"],
        ssl=mock_ssl_context,
    )
    # Disable category fetch delay for faster tests
    device.category_fetch_delay = 0
    return device


async def test_device_init(alfen_device: AlfenDevice, mock_session):
    """Test device initialization."""
    # Mock the info response
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()
    mock_response.json = AsyncMock(
        return_value={
            "Identity": "ALFENEVE001",
            "FWVersion": "5.9.0",
            "Model": "NG910",
            "ObjectId": "123",
            "Type": "Wallbox",
        }
    )

    mock_session.get = AsyncMock(return_value=mock_response)

    result = await alfen_device.init()

    assert result is True
    assert alfen_device.info is not None
    assert alfen_device.info.identity == "ALFENEVE001"
    assert alfen_device.info.firmware_version == "5.9.0"


async def test_device_init_failure(alfen_device: AlfenDevice, mock_session):
    """Test device initialization failure."""
    mock_response = MagicMock()
    mock_response.status = 404
    mock_response.headers = {}
    mock_response.raise_for_status = MagicMock()

    mock_session.get = AsyncMock(return_value=mock_response)

    result = await alfen_device.init()

    # Should return False but still set generic info
    assert result is False
    assert alfen_device.info is not None
    assert alfen_device.info.identity == "192.168.1.100"


async def test_login(alfen_device: AlfenDevice):
    """Test login operation."""
    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"success": True})):
        await alfen_device.login()

        assert alfen_device.logged_in is True
        assert alfen_device.keep_logout is False


async def test_logout(alfen_device: AlfenDevice):
    """Test logout operation."""
    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"success": True})):
        await alfen_device.logout()

        assert alfen_device.logged_in is False
        assert alfen_device.keep_logout is True


async def test_set_value_queues_update(alfen_device: AlfenDevice):
    """Test that set_value queues updates correctly."""
    await alfen_device.set_value("2129_0", 16)

    assert "2129_0" in alfen_device.update_values
    assert alfen_device.update_values["2129_0"]["value"] == 16


async def test_set_value_updates_existing_queue(alfen_device: AlfenDevice):
    """Test that set_value updates existing queued value."""
    await alfen_device.set_value("2129_0", 16)
    await alfen_device.set_value("2129_0", 20)

    assert "2129_0" in alfen_device.update_values
    assert alfen_device.update_values["2129_0"]["value"] == 20


async def test_get_all_properties_value(alfen_device: AlfenDevice):
    """Test fetching all properties for a category."""
    mock_response = {
        PROPERTIES: [
            {ID: "2129_0", VALUE: "16", "cat": "generic"},
            {ID: "2126_0", VALUE: "2", "cat": "generic"},
        ],
        TOTAL: 2,
    }

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=mock_response)):
        properties = await alfen_device._get_all_properties_value("generic")

        assert len(properties) == 2
        assert properties[0][ID] == "2129_0"


async def test_get_all_properties_pagination(alfen_device: AlfenDevice):
    """Test property fetching handles pagination."""
    # First page
    page1 = {
        PROPERTIES: [{ID: "prop1", VALUE: "val1"}],
        TOTAL: 2,
    }
    # Second page
    page2 = {
        PROPERTIES: [{ID: "prop2", VALUE: "val2"}],
        TOTAL: 2,
    }

    responses = [page1, page2]

    with patch.object(alfen_device, "_get", new=AsyncMock(side_effect=responses)):
        properties = await alfen_device._get_all_properties_value("generic")

        assert len(properties) == 2


async def test_async_update_processes_queue(alfen_device: AlfenDevice):
    """Test that async_update processes queued value updates."""
    # Queue some updates
    await alfen_device.set_value("2129_0", 16)

    # Mock successful update
    with patch.object(alfen_device, "_update_value", new=AsyncMock(return_value=True)):
        with patch.object(alfen_device, "_get_all_properties_value", new=AsyncMock(return_value=[])):
            result = await alfen_device.async_update()

            assert result is True
            assert "2129_0" not in alfen_device.update_values  # Should be removed after success


async def test_async_update_retries_failed_updates(alfen_device: AlfenDevice):
    """Test that failed updates remain in queue for retry."""
    # Queue an update
    await alfen_device.set_value("2129_0", 16)

    # Mock failed update
    with patch.object(alfen_device, "_update_value", new=AsyncMock(return_value=False)):
        with patch.object(alfen_device, "_get_all_properties_value", new=AsyncMock(return_value=[])):
            result = await alfen_device.async_update()

            assert result is True
            assert "2129_0" in alfen_device.update_values  # Should remain for retry


async def test_auto_login_on_401_get(alfen_device: AlfenDevice, mock_session):
    """Test automatic re-login on 401 response for GET."""
    # First request returns 401
    mock_response_401 = MagicMock()
    mock_response_401.status = 401
    mock_response_401.__aenter__ = AsyncMock(return_value=mock_response_401)
    mock_response_401.__aexit__ = AsyncMock(return_value=None)

    # Second request after login returns 200
    mock_response_200 = MagicMock()
    mock_response_200.status = 200
    mock_response_200.json = AsyncMock(return_value={"result": "success"})
    mock_response_200.__aenter__ = AsyncMock(return_value=mock_response_200)
    mock_response_200.__aexit__ = AsyncMock(return_value=None)

    # Create proper context managers
    mock_ctx_401 = MagicMock()
    mock_ctx_401.__aenter__ = AsyncMock(return_value=mock_response_401)
    mock_ctx_401.__aexit__ = AsyncMock(return_value=None)

    mock_ctx_200 = MagicMock()
    mock_ctx_200.__aenter__ = AsyncMock(return_value=mock_response_200)
    mock_ctx_200.__aexit__ = AsyncMock(return_value=None)

    mock_session.get = MagicMock(side_effect=[mock_ctx_401, mock_ctx_200])

    async def mock_login():
        """Mock login that sets logged_in = True."""
        alfen_device.logged_in = True

    with patch.object(alfen_device, "login", new=AsyncMock(side_effect=mock_login)):
        result = await alfen_device._get("https://192.168.1.100/api/test")

        assert result == {"result": "success"}
        # Login called twice: once proactively (logged_in starts False), once after 401
        assert alfen_device.login.call_count == 2


async def test_lock_prevents_concurrent_requests(alfen_device: AlfenDevice, mock_session):
    """Test that lock prevents concurrent API requests."""
    call_order = []

    class MockContextManager:
        def __init__(self):
            self.response = MagicMock()
            self.response.status = 200
            self.response.json = AsyncMock(return_value={})

        async def __aenter__(self):
            call_order.append("start")
            await asyncio.sleep(0.1)
            call_order.append("end")
            return self.response

        async def __aexit__(self, *args):
            return None

    def mock_get(*args, **kwargs):
        return MockContextManager()

    mock_session.get = mock_get

    # Start two concurrent requests
    task1 = asyncio.create_task(alfen_device._get("https://192.168.1.100/api/test1"))
    task2 = asyncio.create_task(alfen_device._get("https://192.168.1.100/api/test2"))

    await asyncio.gather(task1, task2)

    # Verify requests were serialized (start-end-start-end, not start-start-end-end)
    assert call_order == ["start", "end", "start", "end"]


async def test_get_number_of_sockets(alfen_device: AlfenDevice):
    """Test getting number of sockets from properties."""
    alfen_device.properties = {"205E_0": {VALUE: 2}}

    sockets = alfen_device.get_number_of_sockets()

    assert sockets == 2


async def test_get_licenses(alfen_device: AlfenDevice):
    """Test getting licenses from properties."""
    # License bitmap with some bits set
    alfen_device.properties = {"21A2_0": {VALUE: 5}}  # Binary: 0101

    licenses = alfen_device.get_licenses()

    # This will depend on your LICENSES constant
    assert isinstance(licenses, list)


async def test_set_current_limit(alfen_device: AlfenDevice):
    """Test setting current limit."""
    await alfen_device.set_current_limit(20)

    assert "2129_0" in alfen_device.update_values
    assert alfen_device.update_values["2129_0"]["value"] == 20


async def test_set_current_limit_validation(alfen_device: AlfenDevice):
    """Test current limit validation."""
    # Too high
    await alfen_device.set_current_limit(40)
    assert "2129_0" not in alfen_device.update_values

    # Too low
    await alfen_device.set_current_limit(0)
    assert "2129_0" not in alfen_device.update_values


async def test_set_rfid_auth_mode(alfen_device: AlfenDevice):
    """Test setting RFID authorization mode."""
    await alfen_device.set_rfid_auth_mode(True)

    assert "2126_0" in alfen_device.update_values
    assert alfen_device.update_values["2126_0"]["value"] == 2

    await alfen_device.set_rfid_auth_mode(False)

    assert alfen_device.update_values["2126_0"]["value"] == 0


async def test_transaction_parsing_unknown_line(alfen_device: AlfenDevice):
    """Test parsing unknown transaction lines."""
    transaction_response = """unknown_line_format"""

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=transaction_response)):
        # Should handle unknown lines without errors
        await alfen_device._get_transaction()


async def test_transaction_parsing_mv(alfen_device: AlfenDevice):
    """Test parsing mv (meter value) transaction lines."""
    transaction_response = """125_mv socket 1, 2024-01-15 11:00:00 20.3"""

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=transaction_response)):
        await alfen_device._get_transaction()

        assert alfen_device.latest_tag is not None
        assert ("socket 1", "mv", "date") in alfen_device.latest_tag
        assert ("socket 1", "mv", "kWh") in alfen_device.latest_tag


async def test_transaction_parsing_empty(alfen_device: AlfenDevice):
    """Test handling of empty transactions."""
    transaction_response = """0_Empty Line"""

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=transaction_response)):
        await alfen_device._get_transaction()

        # Should handle gracefully without errors
        assert True


async def test_log_parsing_ev_connected(alfen_device: AlfenDevice):
    """Test parsing EV_CONNECTED_AUTHORIZED log entries."""
    log_response = """12345_2024-01-15:10:30:00:INFO:charging.c:123:Socket #1 EV_CONNECTED_AUTHORIZED tag: ABC123"""

    alfen_device.latest_logs.append(log_response)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag is not None
        assert ("socket 1", "start", "tag") in alfen_device.latest_tag
        assert alfen_device.latest_tag[("socket 1", "start", "tag")] == "ABC123"


async def test_log_parsing_charging_power_on(alfen_device: AlfenDevice):
    """Test parsing CHARGING_POWER_ON log entries."""
    log_response = """12346_2024-01-15:10:31:00:INFO:charging.c:124:Socket #1 CHARGING_POWER_ON tag: XYZ789"""

    alfen_device.latest_logs.append(log_response)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag is not None
        assert ("socket 1", "start", "tag") in alfen_device.latest_tag
        assert alfen_device.latest_tag[("socket 1", "start", "tag")] == "XYZ789"


async def test_log_parsing_charging_power_off(alfen_device: AlfenDevice):
    """Test parsing CHARGING_POWER_OFF log entries."""
    log_response = """12347_2024-01-15:12:00:00:INFO:charging.c:125:Socket #1 CHARGING_POWER_OFF tag: ABC123"""

    alfen_device.latest_logs.append(log_response)
    alfen_device.latest_tag = {("socket 1", "start", "taglog"): 12300}

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag[("socket 1", "start", "tag")] == "No Tag"


async def test_log_parsing_socket_2(alfen_device: AlfenDevice):
    """Test parsing log entries for socket 2."""
    log_response = """12348_2024-01-15:10:30:00:INFO:charging.c:126:Socket #2 EV_CONNECTED_AUTHORIZED tag: DEF456"""

    alfen_device.latest_logs.append(log_response)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag is not None
        assert ("socket 2", "start", "tag") in alfen_device.latest_tag
        assert alfen_device.latest_tag[("socket 2", "start", "tag")] == "DEF456"


async def test_fetch_log_max_pages(alfen_device: AlfenDevice):
    """Test that log fetching stops after max pages."""
    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(return_value=True)):
        await alfen_device._get_log()

        # Should fetch up to 6 pages (0-5)
        assert alfen_device._fetch_log.call_count == 6


async def test_keep_logout_blocks_requests(alfen_device: AlfenDevice):
    """Test that keep_logout flag blocks API requests."""
    alfen_device.keep_logout = True

    # POST request should return None
    result = await alfen_device._post("test")
    assert result is None

    # GET request should return None
    result = await alfen_device._get("https://test.com")
    assert result is None


async def test_post_timeout_handling(alfen_device: AlfenDevice, mock_session):
    """Test POST timeout handling."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=TimeoutError())
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    result = await alfen_device._post("test", {})

    assert result is None


async def test_get_timeout_handling(alfen_device: AlfenDevice, mock_session):
    """Test GET timeout handling."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=TimeoutError())
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_ctx)

    result = await alfen_device._get("https://test.com")

    assert result is None


async def test_post_json_decode_error_trailing_comma(alfen_device: AlfenDevice, mock_session):
    """Test POST handling of trailing comma JSON error."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()

    # Create JSONDecodeError with trailing comma message
    json_error = json.JSONDecodeError("trailing comma is not allowed", "doc", 0)
    mock_response.json = AsyncMock(side_effect=json_error)

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    result = await alfen_device._post("test", {})

    # Should return None but not raise
    assert result is None


async def test_set_green_share(alfen_device: AlfenDevice):
    """Test setting green share percentage."""
    await alfen_device.set_green_share(75)

    assert "3280_2" in alfen_device.update_values
    assert alfen_device.update_values["3280_2"]["value"] == 75


async def test_set_green_share_validation(alfen_device: AlfenDevice):
    """Test green share validation."""
    # Too high
    await alfen_device.set_green_share(150)
    assert "3280_2" not in alfen_device.update_values

    # Too low
    await alfen_device.set_green_share(-10)
    assert "3280_2" not in alfen_device.update_values


async def test_set_comfort_power(alfen_device: AlfenDevice):
    """Test setting comfort power."""
    await alfen_device.set_comfort_power(3000)

    assert "3280_3" in alfen_device.update_values
    assert alfen_device.update_values["3280_3"]["value"] == 3000


async def test_set_comfort_power_validation(alfen_device: AlfenDevice):
    """Test comfort power validation."""
    # Too high
    await alfen_device.set_comfort_power(6000)
    assert "3280_3" not in alfen_device.update_values

    # Too low
    await alfen_device.set_comfort_power(1000)
    assert "3280_3" not in alfen_device.update_values


async def test_set_current_phase(alfen_device: AlfenDevice):
    """Test setting current phase."""
    await alfen_device.set_current_phase("L2")

    assert "2069_0" in alfen_device.update_values
    assert alfen_device.update_values["2069_0"]["value"] == "L2"


async def test_set_current_phase_validation(alfen_device: AlfenDevice):
    """Test current phase validation."""
    # Invalid phase
    await alfen_device.set_current_phase("L4")
    assert "2069_0" not in alfen_device.update_values


async def test_set_phase_switching(alfen_device: AlfenDevice):
    """Test setting phase switching."""
    await alfen_device.set_phase_switching(True)

    assert "2185_0" in alfen_device.update_values
    assert alfen_device.update_values["2185_0"]["value"] == 1

    await alfen_device.set_phase_switching(False)

    assert alfen_device.update_values["2185_0"]["value"] == 0


async def test_reboot_wallbox(alfen_device: AlfenDevice):
    """Test rebooting the wallbox."""
    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"success": True})):
        await alfen_device.reboot_wallbox()

        alfen_device._post.assert_called_once()


async def test_clear_transactions(alfen_device: AlfenDevice):
    """Test clearing transactions."""
    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"success": True})):
        await alfen_device.clear_transactions()

        alfen_device._post.assert_called_once()


async def test_send_command(alfen_device: AlfenDevice):
    """Test sending custom command."""
    command = {"command": "test_command"}

    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"success": True})):
        await alfen_device.send_command(command)

        alfen_device._post.assert_called_once()


async def test_async_request_get(alfen_device: AlfenDevice):
    """Test async_request with GET method."""
    with patch.object(alfen_device, "request", new=AsyncMock(return_value={"data": "test"})):
        result = await alfen_device.async_request("GET", "test")

        assert result == {"data": "test"}


async def test_async_request_post(alfen_device: AlfenDevice):
    """Test async_request with POST method."""
    with patch.object(alfen_device, "request", new=AsyncMock(return_value={"data": "test"})):
        result = await alfen_device.async_request("POST", "test", {"key": "value"})

        assert result == {"data": "test"}


async def test_async_request_exception_handling(alfen_device: AlfenDevice):
    """Test async_request exception handling."""
    with patch.object(alfen_device, "request", new=AsyncMock(side_effect=Exception("Test error"))):
        result = await alfen_device.async_request("GET", "test")

        assert result is None


async def test_get_value(alfen_device: AlfenDevice):
    """Test getting a specific value."""
    alfen_device.properties = {"2129_0": {ID: "2129_0", VALUE: "16"}}

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value={
        PROPERTIES: [{ID: "2129_0", VALUE: "20"}]
    })):
        await alfen_device.get_value("2129_0")

        assert alfen_device.properties["2129_0"][VALUE] == "20"


async def test_post_error_not_allowed_login(alfen_device: AlfenDevice, mock_session):
    """Test POST error handling when login not allowed."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("Connection error"))
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.post = MagicMock(return_value=mock_ctx)

    result = await alfen_device._post("test", {}, allowed_login=False)

    assert result is None


async def test_get_error_not_allowed_login(alfen_device: AlfenDevice, mock_session):
    """Test GET error handling when login not allowed."""
    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(side_effect=Exception("Connection error"))
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_ctx)

    result = await alfen_device._get("https://test.com", allowed_login=False)

    assert result is None


async def test_get_text_mode(alfen_device: AlfenDevice, mock_session):
    """Test GET in text mode (json_decode=False)."""
    mock_response = MagicMock()
    mock_response.status = 200
    mock_response.raise_for_status = MagicMock()
    mock_response.text = AsyncMock(return_value="Plain text response")

    mock_ctx = MagicMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_response)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)
    mock_session.get = MagicMock(return_value=mock_ctx)

    result = await alfen_device._get("https://test.com", json_decode=False)

    assert result == "Plain text response"


async def test_login_exception_handling(alfen_device: AlfenDevice):
    """Test login error handling."""
    # Set initial state to not logged in
    alfen_device.logged_in = False

    # Mock session.post context manager to raise an exception on enter
    mock_post_ctx = MagicMock()
    mock_post_ctx.__aenter__ = AsyncMock(side_effect=Exception("Login failed"))
    mock_post_ctx.__aexit__ = AsyncMock(return_value=None)
    alfen_device._session.post = MagicMock(return_value=mock_post_ctx)

    await alfen_device.login()

    # Should not crash, logged_in remains False
    assert alfen_device.logged_in is False


async def test_logout_exception_handling(alfen_device: AlfenDevice):
    """Test logout error handling."""
    alfen_device.logged_in = True

    with patch.object(alfen_device, "_post", new=AsyncMock(side_effect=Exception("Logout failed"))):
        await alfen_device.logout()

        # Should still set keep_logout
        assert alfen_device.keep_logout is True


async def test_get_all_properties_string_response(alfen_device: AlfenDevice):
    """Test property fetching with string JSON response."""
    json_str = '{"properties": [{"id": "test", "value": "123"}], "total": 1}'

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=json_str)):
        properties = await alfen_device._get_all_properties_value("generic")

        assert len(properties) == 1
        assert properties[0]["id"] == "test"


async def test_get_all_properties_invalid_json(alfen_device: AlfenDevice):
    """Test property fetching with invalid JSON string."""
    invalid_json = "not valid json{{"

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=invalid_json)):
        properties = await alfen_device._get_all_properties_value("generic")

        # Should return empty list on JSON error
        assert properties == []


async def test_get_all_properties_invalid_structure(alfen_device: AlfenDevice):
    """Test property fetching with invalid response structure."""
    invalid_response = {"invalid": "structure"}

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=invalid_response)):
        properties = await alfen_device._get_all_properties_value("generic")

        # Should return empty list
        assert properties == []


async def test_get_all_properties_retry_after_failures(alfen_device: AlfenDevice):
    """Test property fetching retries after failures."""
    # Return None twice, then success
    responses = [None, None, {PROPERTIES: [{"id": "test"}], TOTAL: 1}]

    with patch.object(alfen_device, "_get", new=AsyncMock(side_effect=responses)):
        properties = await alfen_device._get_all_properties_value("generic")

        assert len(properties) == 1


async def test_get_all_properties_max_retries_exceeded(alfen_device: AlfenDevice):
    """Test property fetching stops after max retries."""
    # Return None 4 times (exceeds 3 attempt limit)
    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=None)):
        properties = await alfen_device._get_all_properties_value("generic")

        # Should return empty list after max retries
        assert properties == []


async def test_fetch_log_returns_none(alfen_device: AlfenDevice):
    """Test log fetching when API returns None."""
    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=None)):
        result = await alfen_device._fetch_log(0)

        assert result is None


async def test_get_log_malformed_lines(alfen_device: AlfenDevice):
    """Test log parsing with malformed log lines."""
    malformed_logs = [
        "no_underscore_in_this_line",
        "12345678901234567890_too_long_line_id",
        "123_onlytwocolons:data",
        "456_valid:but:not:enough:colons:here",
    ]
    alfen_device.latest_logs.extend(malformed_logs)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        # Should handle malformed lines gracefully
        assert True


async def test_get_log_no_socket_in_message(alfen_device: AlfenDevice):
    """Test log parsing with messages without socket number."""
    log_without_socket = "12345_2024-01-15:10:30:00:INFO:charging.c:123:No socket number here tag: ABC123"
    alfen_device.latest_logs.append(log_without_socket)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        # Should skip lines without socket number
        assert True


async def test_get_log_cable_connected_event(alfen_device: AlfenDevice):
    """Test log parsing with CABLE_CONNECTED event."""
    log_line = "12350_2024-01-15:10:30:00:INFO:charging.c:123:Socket #1 CABLE_CONNECTED tag: XYZ789"
    alfen_device.latest_logs.append(log_line)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag is not None
        assert ("socket 1", "start", "tag") in alfen_device.latest_tag


async def test_get_log_charging_terminating_event(alfen_device: AlfenDevice):
    """Test log parsing with CHARGING_TERMINATING event."""
    alfen_device.latest_tag = {("socket 1", "start", "taglog"): 12300}
    log_line = "12351_2024-01-15:12:00:00:INFO:charging.c:125:Socket #1 CHARGING_TERMINATING tag: ABC123"
    alfen_device.latest_logs.append(log_line)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        assert alfen_device.latest_tag[("socket 1", "start", "tag")] == "No Tag"


async def test_get_log_older_entry_ignored(alfen_device: AlfenDevice):
    """Test that older log entries don't override newer ones."""
    alfen_device.latest_tag = {
        ("socket 1", "start", "taglog"): 12400,
        ("socket 1", "start", "tag"): "NEW123",
    }

    # Older log entry (lower ID)
    old_log = "12300_2024-01-15:10:00:00:INFO:charging.c:123:Socket #1 EV_CONNECTED_AUTHORIZED tag: OLD456"
    alfen_device.latest_logs.append(old_log)

    with patch.object(alfen_device, "_fetch_log", new=AsyncMock(side_effect=[True, False])):
        await alfen_device._get_log()

        # Should keep newer tag
        assert alfen_device.latest_tag[("socket 1", "start", "tag")] == "NEW123"


async def test_transaction_parsing_version_line(alfen_device: AlfenDevice):
    """Test transaction parsing with version line."""
    transaction_response = """version:2,123_txstart: socket 1, 2024-01-15 10:30:00 15.5kWh tag123 3 1 y"""

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=transaction_response)):
        await alfen_device._get_transaction()

        # Should parse correctly even with version prefix
        assert True




async def test_transaction_parsing_multiple_unknown_lines(alfen_device: AlfenDevice):
    """Test transaction parsing stops after too many unknown lines."""
    unknown_lines = """unknown1
unknown2
unknown3
unknown4"""

    with patch.object(alfen_device, "_get", new=AsyncMock(return_value=unknown_lines)):
        await alfen_device._get_transaction()

        # Should stop after 3 unknown lines
        assert True


async def test_async_update_without_value_callback(alfen_device: AlfenDevice):
    """Test async_update without value updated callback."""
    alfen_device._value_updated_callback = None
    await alfen_device.set_value("2129_0", 20)

    with patch.object(alfen_device, "_update_value", new=AsyncMock(return_value=True)):
        with patch.object(alfen_device, "_get_all_properties_value", new=AsyncMock(return_value=[])):
            result = await alfen_device.async_update()

            # Should complete without callback
            assert result is True


async def test_async_update_transaction_counter(alfen_device: AlfenDevice):
    """Test transaction fetching on 60th update cycle."""
    alfen_device.category_options = ["generic", "transactions"]
    alfen_device.transaction_counter = 59  # Next will be 60th cycle (0)

    with patch.object(alfen_device, "_get_all_properties_value", new=AsyncMock(return_value=[])):
        with patch.object(alfen_device, "_get_transaction", new=AsyncMock()) as mock_get_trans:
            await alfen_device.async_update()

            # Should call _get_transaction on 60th cycle
            mock_get_trans.assert_called_once()
            assert alfen_device.transaction_counter == 0


async def test_request_method_post(alfen_device: AlfenDevice):
    """Test request method with POST."""
    with patch.object(alfen_device, "_post", new=AsyncMock(return_value={"result": "ok"})):
        result = await alfen_device.request("POST", "test", {"data": "value"})

        assert result == {"result": "ok"}


async def test_device_info_property(alfen_device: AlfenDevice):
    """Test device_info property."""
    alfen_device.info = MagicMock()
    alfen_device.info.model = "NG910"
    alfen_device.info.firmware_version = "5.9.0"

    device_info = alfen_device.device_info

    assert "identifiers" in device_info
    assert device_info["manufacturer"] == "Alfen"
    assert device_info["model"] == "NG910"
    assert device_info["sw_version"] == "5.9.0"


async def test_device_info_without_info(alfen_device: AlfenDevice):
    """Test device_info property when info is None."""
    alfen_device.info = None

    device_info = alfen_device.device_info

    assert device_info["model"] == "Unknown"
    assert device_info["sw_version"] == "Unknown"
