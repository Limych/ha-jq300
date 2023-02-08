#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import asyncio
import logging
from typing import Optional

from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_DEVICE_CLASS, CONF_DEVICES, CONF_ICON, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import async_generate_entity_id

from .api import Jq300Account
from .const import BINARY_SENSORS, CONF_ACCOUNT_CONTROLLER, DOMAIN
from .entity import Jq300Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
) -> bool:
    """Set up binary_sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    account = data[CONF_ACCOUNT_CONTROLLER]  # type: Jq300Account
    devices = data[CONF_DEVICES]  # type: dict

    _LOGGER.debug("Setup binary sensors for account %s", account.name_secure)

    try:
        await account.async_update_sensors_or_timeout()
    except TimeoutError:
        return False

    entities = []
    for dev_name, dev_id in devices.items():
        sensors = account.get_sensors(dev_id)
        while not sensors:
            _LOGGER.debug("Sensors list is not ready. Wait for 3 sec...")
            await asyncio.sleep(3)
            sensors = account.get_sensors(dev_id)

        sensor_id = 1
        ent_name = BINARY_SENSORS[sensor_id][CONF_NAME]
        entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "_".join((dev_name, ent_name)), hass=hass
        )

        _LOGGER.debug("Initialize %s", entity_id)
        entities.append(
            Jq300BinarySensor(entity_id, account, dev_id, sensor_id, sensors[sensor_id])
        )

    async_add_entities(entities)
    return True


# pylint: disable=too-many-instance-attributes
class Jq300BinarySensor(Jq300Entity, BinarySensorEntity):
    """A binary sensor implementation for JQ device."""

    def __init__(
        self,
        entity_id: str,
        account: Jq300Account,
        device_id,
        sensor_id,
        sensor_state: Optional[bool],
    ):
        """Initialize a binary sensor."""
        super().__init__(entity_id, account, device_id, sensor_id, sensor_state)

        self._attr_name = (
            f'{self._device.get("pt_name")} {BINARY_SENSORS[sensor_id][CONF_NAME]}'
        )
        self._attr_icon = BINARY_SENSORS[sensor_id][CONF_ICON]
        self._attr_device_class = BINARY_SENSORS[sensor_id].get(CONF_DEVICE_CLASS)
        self._attr_is_on = sensor_state

    def update(self):
        """Update the sensor state if it needed."""
        ret = self._account.get_sensors_raw(self._device_id)
        if not ret:
            return

        if self._attr_is_on == ret[self._sensor_id]:
            return

        self._attr_is_on = ret[self._sensor_id]
        _LOGGER.debug("Update state: %s = %s", self.entity_id, self._attr_is_on)
