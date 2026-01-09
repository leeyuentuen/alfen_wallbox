"""Fixtures for Alfen Wallbox tests."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.const import (
    CONF_REFRESH_CATEGORIES,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

pytest_plugins = "pytest_homeassistant_custom_component"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations for all tests."""
    yield


@pytest.fixture(name="mock_alfen_device")
def mock_alfen_device_fixture():
    """Mock an AlfenDevice."""
    with patch(
        "custom_components.alfen_wallbox.coordinator.AlfenDevice", autospec=True
    ) as mock_device_class:
        mock_device = mock_device_class.return_value
        mock_device.init = AsyncMock(return_value=True)
        mock_device.async_update = AsyncMock(return_value=True)
        mock_device.logout = AsyncMock()
        mock_device.login = AsyncMock()
        mock_device.set_value = AsyncMock()
        mock_device.get_value = AsyncMock()
        mock_device.properties = {}
        mock_device.info = MagicMock()
        mock_device.info.identity = "Test Wallbox"
        mock_device.info.model = "Test Model"
        mock_device.info.firmware_version = "1.0.0"
        mock_device.name = "Test Wallbox"
        mock_device.id = "alfen_Test Wallbox"
        mock_device.host = "192.168.1.100"
        mock_device.log_id = "Test Wallbox@192.168.1.100"
        mock_device.get_licenses = MagicMock(return_value=[])
        mock_device.get_number_of_sockets = MagicMock(return_value=1)
        mock_device.keep_logout = False
        mock_device.get_static_properties = False
        mock_device.category_options = ["generic", "states"]
        mock_device.device_info = {
            "identifiers": {("alfen_wallbox", "Test Wallbox")},
            "manufacturer": "Alfen",
            "model": "Test Model",
            "name": "Test Wallbox",
            "sw_version": "1.0.0",
        }
        yield mock_device


@pytest.fixture(name="mock_config_entry")
def mock_config_entry_fixture():
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Test Wallbox",
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Test Wallbox",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
        },
        options={
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_REFRESH_CATEGORIES: list(DEFAULT_REFRESH_CATEGORIES),
        },
        unique_id="192.168.1.100",
        version=2,
    )


@pytest.fixture(name="mock_setup_entry")
def mock_setup_entry_fixture():
    """Mock setting up a config entry."""
    with patch(
        "custom_components.alfen_wallbox.async_setup_entry", return_value=True
    ) as mock_setup:
        yield mock_setup


@pytest.fixture(name="mock_aiohttp_session", autouse=True)
def mock_aiohttp_session_fixture():
    """Mock aiohttp ClientSession."""
    with patch(
        "custom_components.alfen_wallbox.coordinator.ClientSession"
    ) as mock_session_class:
        session = MagicMock()
        session.closed = False
        session.close = AsyncMock()

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

        mock_session_class.return_value = session
        yield session


@pytest.fixture(name="mock_tcp_connector", autouse=True)
def mock_tcp_connector_fixture():
    """Mock aiohttp TCPConnector."""
    with patch(
        "custom_components.alfen_wallbox.coordinator.TCPConnector"
    ) as mock_connector:
        connector = MagicMock()
        mock_connector.return_value = connector
        yield connector


@pytest.fixture(name="mock_ssl_context", autouse=True)
def mock_ssl_context_fixture():
    """Mock SSL context."""
    with patch(
        "custom_components.alfen_wallbox.coordinator.get_default_context"
    ) as mock_ssl:
        context = MagicMock()
        mock_ssl.return_value = context
        yield context
