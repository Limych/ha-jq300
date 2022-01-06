# pylint: disable=protected-access,redefined-outer-name
"""Test integration_blueprint setup process."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    assert_setup_component,
)

from custom_components.jq300 import (
    CONF_ACCOUNT_CONTROLLER,
    DOMAIN,
    Jq300Account,
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)

from tests.const import MOCK_CONFIG


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield

async def test_async_setup(hass: HomeAssistant):
    """Test a successful setup component."""
    with assert_setup_component(5, DOMAIN):
        await async_setup_component(hass, DOMAIN, {DOMAIN: MOCK_CONFIG})
        await hass.async_block_till_done()

    await hass.async_start()
    await hass.async_block_till_done()


async def test_setup_unload_and_reload_entry(hass, bypass_get_data):
    """Test entry setup and unload."""
    # Create a mock entry so we don't have to go through config flow
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    # Set up the entry and assert that the values set during setup are where we expect
    # them to be. Because we have patched the Jq300DataUpdateCoordinator.async_get_data
    # call, no code from custom_components/integration_blueprint/api.py actually runs.
    hass.data.setdefault(DOMAIN, {})
    assert await async_setup_entry(hass, config_entry)
    assert config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id][CONF_ACCOUNT_CONTROLLER],
        Jq300Account,
    )

    # Reload the entry and assert that the data from above is still there
    assert await async_reload_entry(hass, config_entry) is None
    assert config_entry.entry_id in hass.data[DOMAIN]
    assert isinstance(
        hass.data[DOMAIN][config_entry.entry_id][CONF_ACCOUNT_CONTROLLER],
        Jq300Account,
    )

    # Unload the entry and verify that the data has been removed
    assert await async_unload_entry(hass, config_entry)
    assert config_entry.entry_id not in hass.data[DOMAIN]


async def test_setup_entry_exception(hass, error_on_get_data):
    """Test ConfigEntryNotReady when API raises an exception during entry setup."""
    config_entry = MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test")

    # In this case we are testing the condition where async_setup_entry raises
    # ConfigEntryNotReady using the `error_on_get_data` fixture which simulates
    # an error.
    with pytest.raises(ConfigEntryNotReady):
        assert await async_setup_entry(hass, config_entry)
