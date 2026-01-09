"""Test the Alfen Wallbox config flow."""


from homeassistant import config_entries
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.const import (
    CONF_CATEGORIES_PER_CYCLE,
    CONF_CATEGORY_FETCH_DELAY,
    CONF_REFRESH_CATEGORIES,
    DEFAULT_CATEGORIES_PER_CYCLE,
    DEFAULT_CATEGORY_FETCH_DELAY,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)


async def test_user_form_display(hass: HomeAssistant) -> None:
    """Test that the user form is displayed correctly."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    # errors may be None or empty dict initially
    assert result.get("errors") is None or result.get("errors") == {}


async def test_user_form_success(hass: HomeAssistant) -> None:
    """Test successful user form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "My Wallbox",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret123",
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.100"
    assert result["data"] == {
        CONF_HOST: "192.168.1.100",
        CONF_NAME: "My Wallbox",
        CONF_USERNAME: "admin",
        CONF_PASSWORD: "secret123",
    }
    assert result["options"] == {
        CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
        CONF_TIMEOUT: DEFAULT_TIMEOUT,
        CONF_REFRESH_CATEGORIES: DEFAULT_REFRESH_CATEGORIES,
        CONF_CATEGORIES_PER_CYCLE: DEFAULT_CATEGORIES_PER_CYCLE,
        CONF_CATEGORY_FETCH_DELAY: DEFAULT_CATEGORY_FETCH_DELAY,
    }


async def test_user_form_duplicate_host(hass: HomeAssistant) -> None:
    """Test that duplicate host is detected."""
    # Create an existing entry with the same host
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.100",
            CONF_NAME: "Existing Wallbox",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test123",
        },
        options={
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_REFRESH_CATEGORIES: DEFAULT_REFRESH_CATEGORIES,
            CONF_CATEGORIES_PER_CYCLE: DEFAULT_CATEGORIES_PER_CYCLE,
            CONF_CATEGORY_FETCH_DELAY: DEFAULT_CATEGORY_FETCH_DELAY,
        },
    )
    existing_entry.add_to_hass(hass)

    # Try to add another entry with the same host
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.100",  # Same host as existing entry
            CONF_NAME: "Another Wallbox",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "test456",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_init(hass: HomeAssistant, mock_config_entry: MockConfigEntry) -> None:
    """Test options flow initialization."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "init"


async def test_options_flow_update_scan_interval(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating scan interval via options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: 10,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_REFRESH_CATEGORIES: list(DEFAULT_REFRESH_CATEGORIES),
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_SCAN_INTERVAL] == 10


async def test_options_flow_update_timeout(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating timeout via options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_TIMEOUT: 15,
            CONF_REFRESH_CATEGORIES: list(DEFAULT_REFRESH_CATEGORIES),
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TIMEOUT] == 15


async def test_options_flow_update_categories(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating refresh categories via options flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    new_categories = ["generic", "states"]
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SCAN_INTERVAL: DEFAULT_SCAN_INTERVAL,
            CONF_TIMEOUT: DEFAULT_TIMEOUT,
            CONF_REFRESH_CATEGORIES: new_categories,
        },
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REFRESH_CATEGORIES] == new_categories


async def test_reconfigure_flow_init(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow initialization."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_update_credentials(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test updating credentials via reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "192.168.1.200",
            CONF_USERNAME: "newadmin",
            CONF_PASSWORD: "newpassword",
        },
    )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"

    # Verify the entry was updated
    assert mock_config_entry.data[CONF_HOST] == "192.168.1.200"
    assert mock_config_entry.data[CONF_USERNAME] == "newadmin"
    assert mock_config_entry.data[CONF_PASSWORD] == "newpassword"
