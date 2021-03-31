"""Test jq300 config flow."""

from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.jq300 import DOMAIN
from custom_components.jq300.config_flow import Jq300FlowHandler


async def test_async_step_import(hass: HomeAssistant):
    """Test a successful config flow import."""
    config = {"some": "data"}
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data=config,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == config

    with patch.object(
        Jq300FlowHandler, "_async_current_entries", return_value=["Test"]
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=config,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
