#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import asyncio
import logging
from datetime import timedelta

import async_timeout
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.config_entries import SOURCE_IMPORT, ConfigEntry
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType

from .api import Jq300Account
from .const import (
    CONF_ACCOUNT_CONTROLLER,
    CONF_RECEIVE_HCHO_IN_PPB,
    CONF_RECEIVE_TVOC_IN_PPB,
    CONF_YAML,
    DOMAIN,
    PLATFORMS,
    STARTUP_MESSAGE,
    UPDATE_TIMEOUT,
)
from .util import mask_email

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL = timedelta(seconds=30)


ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_RECEIVE_TVOC_IN_PPB, default=False): cv.boolean,
        vol.Optional(CONF_RECEIVE_HCHO_IN_PPB, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: ACCOUNT_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up this integration using YAML."""
    # Print startup message
    if DOMAIN not in hass.data:
        _LOGGER.info(STARTUP_MESSAGE)
        hass.data[DOMAIN] = {}

    if DOMAIN not in config:
        return True

    hass.data[DOMAIN][CONF_YAML] = config[DOMAIN]
    hass.async_create_task(
        hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data={}
        )
    )

    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up this integration using UI."""
    if entry.source == SOURCE_IMPORT:
        config = hass.data[DOMAIN][CONF_YAML]
    else:
        config = entry.data.copy()
        config.update(entry.options)

    username = config.get(CONF_USERNAME)
    password = config.get(CONF_PASSWORD)
    active_devices = config.get(CONF_DEVICES, [])
    receive_tvoc_in_ppb = config.get(CONF_RECEIVE_TVOC_IN_PPB)
    receive_hcho_in_ppb = config.get(CONF_RECEIVE_HCHO_IN_PPB)

    _LOGGER.debug("Connecting to account %s", mask_email(username))

    session = async_get_clientsession(hass)
    account = Jq300Account(
        hass, session, username, password, receive_tvoc_in_ppb, receive_hcho_in_ppb
    )

    try:
        with async_timeout.timeout(UPDATE_TIMEOUT):
            devices = await account.async_update_devices()
    except TimeoutError as exc:
        raise ConfigEntryNotReady from exc

    devs = {}
    adevs = []
    for device_id in devices:
        name = devices[device_id]["pt_name"]
        if active_devices and name not in active_devices:
            continue

        adevs.append(device_id)
        devs[name] = device_id

    account.active_devices = adevs

    hass.data[DOMAIN][entry.entry_id] = {
        CONF_ACCOUNT_CONTROLLER: account,
        CONF_DEVICES: devs,
    }

    # Load platforms
    for platform in PLATFORMS:
        hass.async_add_job(
            hass.config_entries.async_forward_entry_setup(entry, platform)
        )

    entry.add_update_listener(async_reload_entry)
    return True


# class Jq300DataUpdateCoordinator(DataUpdateCoordinator):
#     """Class to manage fetching data from the API."""
#
#     def __init__(
#         self, hass: HomeAssistant, client: JqApiClient
#     ) -> None:
#         """Initialize."""
#         self.api = client
#         self.platforms = []
#
#         super().__init__(hass, _LOGGER, name=DOMAIN, update_interval=SCAN_INTERVAL)
#
#     async def _async_update_data(self):
#         """Update data via library."""
#         try:
#             return await self.api.async_get_data()
#         except Exception as exception:
#             raise UpdateFailed() from exception


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    # coordinator = hass.data[DOMAIN][entry.entry_id]
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
                # if platform in coordinator.platforms
            ]
        )
    )
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)
