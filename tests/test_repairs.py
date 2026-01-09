"""Test the Alfen Wallbox repairs module."""


from custom_components.alfen_wallbox.repairs import (
    AuthenticationFailedRepairFlow,
    ConnectionFailedRepairFlow,
    async_create_fix_flow,
)


class TestConnectionFailedRepairFlow:
    """Tests for ConnectionFailedRepairFlow."""

    async def test_init_step_redirects_to_confirm(self, hass):
        """Test that init step redirects to confirm."""
        flow = ConnectionFailedRepairFlow()
        flow.hass = hass
        flow.data = {"host": "192.168.1.100"}

        result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_confirm_step_shows_form(self, hass):
        """Test that confirm step shows form with host placeholder."""
        flow = ConnectionFailedRepairFlow()
        flow.hass = hass
        flow.data = {"host": "192.168.1.100"}

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"
        assert result["description_placeholders"]["host"] == "192.168.1.100"

    async def test_confirm_step_with_none_data(self, hass):
        """Test confirm step when data is None."""
        flow = ConnectionFailedRepairFlow()
        flow.hass = hass
        flow.data = None

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["description_placeholders"]["host"] == "unknown"

    async def test_confirm_step_creates_entry_on_submit(self, hass):
        """Test that submitting confirm step creates entry."""
        flow = ConnectionFailedRepairFlow()
        flow.hass = hass
        flow.data = {"host": "192.168.1.100"}

        result = await flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        assert result["data"] == {}


class TestAuthenticationFailedRepairFlow:
    """Tests for AuthenticationFailedRepairFlow."""

    async def test_init_step_redirects_to_confirm(self, hass):
        """Test that init step redirects to confirm."""
        flow = AuthenticationFailedRepairFlow()
        flow.hass = hass
        flow.data = {}

        result = await flow.async_step_init()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_confirm_step_shows_form(self, hass):
        """Test that confirm step shows form."""
        flow = AuthenticationFailedRepairFlow()
        flow.hass = hass
        flow.data = {}

        result = await flow.async_step_confirm()

        assert result["type"] == "form"
        assert result["step_id"] == "confirm"

    async def test_confirm_step_creates_entry_on_submit(self, hass):
        """Test that submitting confirm step creates entry."""
        flow = AuthenticationFailedRepairFlow()
        flow.hass = hass
        flow.data = {}

        result = await flow.async_step_confirm(user_input={})

        assert result["type"] == "create_entry"
        assert result["data"] == {}


class TestAsyncCreateFixFlow:
    """Tests for async_create_fix_flow factory function."""

    async def test_creates_connection_failed_flow(self, hass):
        """Test creating connection failed repair flow."""
        flow = await async_create_fix_flow(
            hass, "connection_failed", {"host": "192.168.1.100"}
        )

        assert isinstance(flow, ConnectionFailedRepairFlow)

    async def test_creates_authentication_failed_flow(self, hass):
        """Test creating authentication failed repair flow."""
        flow = await async_create_fix_flow(hass, "authentication_failed", None)

        assert isinstance(flow, AuthenticationFailedRepairFlow)

    async def test_creates_confirm_flow_for_unknown_issue(self, hass):
        """Test creating confirm flow for unknown issue ID."""
        flow = await async_create_fix_flow(hass, "unknown_issue", None)

        # Should return a ConfirmRepairFlow for unknown issues
        assert flow is not None
