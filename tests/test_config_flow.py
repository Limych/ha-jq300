"""Test integration_blueprint config flow."""

from homeassistant import config_entries, data_entry_flow
from homeassistant.core import HomeAssistant

from custom_components.jq300 import DOMAIN


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
