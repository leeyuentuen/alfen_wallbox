"""Repairs for Alfen Wallbox integration."""

from __future__ import annotations

from homeassistant import data_entry_flow
from homeassistant.components.repairs import ConfirmRepairFlow, RepairsFlow
from homeassistant.core import HomeAssistant


class ConnectionFailedRepairFlow(RepairsFlow):
    """Handler for connection failed repair flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        host = "unknown"
        if self.data is not None:
            host = str(self.data.get("host", "unknown"))

        return self.async_show_form(
            step_id="confirm",
            description_placeholders={"host": host},
        )


class AuthenticationFailedRepairFlow(RepairsFlow):
    """Handler for authentication failed repair flow."""

    async def async_step_init(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the first step of a fix flow."""
        return await self.async_step_confirm()

    async def async_step_confirm(
        self, user_input: dict[str, str] | None = None
    ) -> data_entry_flow.FlowResult:
        """Handle the confirm step of a fix flow."""
        if user_input is not None:
            return self.async_create_entry(data={})

        return self.async_show_form(step_id="confirm")


async def async_create_fix_flow(
    hass: HomeAssistant,
    issue_id: str,
    data: dict[str, str] | None,
) -> RepairsFlow:
    """Create flow for fixing issues."""
    if issue_id == "connection_failed":
        return ConnectionFailedRepairFlow()
    if issue_id == "authentication_failed":
        return AuthenticationFailedRepairFlow()

    return ConfirmRepairFlow()
