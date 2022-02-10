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

from homeassistant.components.sensor import (
    ENTITY_ID_FORMAT,
    STATE_CLASS_MEASUREMENT,
    SensorEntity,
)
from homeassistant.const import (
    CONF_DEVICE_CLASS,
    CONF_DEVICES,
    CONF_ENTITY_ID,
    CONF_ICON,
    CONF_NAME,
)
from homeassistant.helpers.entity import async_generate_entity_id

from .api import Jq300Account
from .const import ATTR_RAW_STATE, CONF_ACCOUNT_CONTROLLER, DOMAIN, SENSORS
from .entity import Jq300Entity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up sensor platform."""
    data = hass.data[DOMAIN][entry.entry_id]
    account = data[CONF_ACCOUNT_CONTROLLER]  # type: Jq300Account
    devices = data[CONF_DEVICES]  # type: dict

    _LOGGER.debug("Setup sensors for account %s", account.name_secure)

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

        dev_model = account.devices.get(dev_id, {}).get("pt_model")
        is_jq300 = dev_model == "JQ_300"
        is_jq200 = is_jq300 or (dev_model == "JQ300")

        for sensor_id, sensor_state in sensors.items():
            if (
                sensor_id not in SENSORS
                or (sensor_id in (4, 5) and not is_jq200)
                or (sensor_id == 6 and not is_jq300)
            ):
                continue

            ent_name = SENSORS[sensor_id].get(
                CONF_ENTITY_ID, SENSORS[sensor_id][CONF_NAME]
            )
            entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, "_".join((dev_name, ent_name)), hass=hass
            )

            _LOGGER.debug("Initialize %s", entity_id)
            entities.append(
                Jq300Sensor(entity_id, account, dev_id, sensor_id, sensor_state)
            )

    async_add_entities(entities)
    return True


# pylint: disable=too-many-instance-attributes
class Jq300Sensor(Jq300Entity, SensorEntity):
    """A sensor implementation for JQ device."""

    def __init__(
        self, entity_id, account: Jq300Account, device_id, sensor_id, sensor_state
    ):
        """Initialize a sensor."""
        super().__init__(entity_id, account, device_id, sensor_id, sensor_state)

        self._raw_value = sensor_state

        self._attr_icon = SENSORS[sensor_id][CONF_ICON]
        self._attr_name = (
            f"{self._device.get('pt_name')} {SENSORS[sensor_id][CONF_NAME]}"
        )
        self._attr_device_class = SENSORS[sensor_id].get(CONF_DEVICE_CLASS)
        self._attr_native_unit_of_measurement = self._account.units[sensor_id]
        self._attr_native_value = sensor_state
        self._attr_state_class = STATE_CLASS_MEASUREMENT
        self._attr_extra_state_attributes[ATTR_RAW_STATE] = self._raw_value

    def update(self):
        """Update the sensor state if it needed."""
        ret = self._account.get_sensors(self._device_id)
        if not ret:
            return

        value = ret[self._sensor_id]
        raw_value = self._account.get_sensors_raw(self._device_id)[self._sensor_id]
        if self._attr_native_value == value and self._raw_value == raw_value:
            return

        self._raw_value = raw_value

        self._attr_native_value = value
        self._attr_extra_state_attributes[ATTR_RAW_STATE] = raw_value

        _LOGGER.debug("Update state: %s = %s (%s)", self.entity_id, value, raw_value)
