"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import logging
from time import sleep

from homeassistant import exceptions
from homeassistant.components.binary_sensor import ENTITY_ID_FORMAT
from homeassistant.const import CONF_DEVICES
from homeassistant.helpers.entity import async_generate_entity_id

# Code snippet to keep compatibility with Home Assistant 0.109
try:
    from homeassistant.components.binary_sensor import BinarySensorEntity
except ImportError:
    from homeassistant.components.binary_sensor import (
        BinarySensorDevice as BinarySensorEntity,
    )

from . import JqAccount, CannotConnect
from .const import (
    BINARY_SENSORS,
    DOMAIN,
    ATTR_DEVICE_BRAND,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_ID,
    ACCOUNT_CONTROLLER,
    CONF_ACCOUNT_ID,
)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> bool:
    """Set up a binary sensors to integrate JQ-300."""
    if discovery_info is None:
        return True

    domain_data = hass.data[DOMAIN][discovery_info[CONF_ACCOUNT_ID]]
    account = domain_data[ACCOUNT_CONTROLLER]  # type: JqAccount
    devices = domain_data[CONF_DEVICES]  # type: dict

    _LOGGER.debug("Setup binary sensors for account %s", account.name_secure)

    try:
        await account.async_update_sensors_or_timeout()
    except CannotConnect:
        return False

    entities = []
    for dev_name, dev_id in devices.items():
        sensors = account.get_sensors(dev_id)
        while not sensors:
            _LOGGER.debug("Sensors list is not ready. Wait for 3 sec...")
            sleep(3)
            sensors = account.get_sensors(dev_id)

        sensor_id = 1
        ent_name = str(BINARY_SENSORS[sensor_id][4] or BINARY_SENSORS[sensor_id][0])
        entity_id = async_generate_entity_id(
            ENTITY_ID_FORMAT, "_".join((dev_name, ent_name)), hass=hass
        )
        _LOGGER.debug("Initialize %s", entity_id)
        entities.append(
            JqBinarySensor(entity_id, account, dev_id, sensor_id, sensors[sensor_id])
        )

    async_add_entities(entities)

    return True


# pylint: disable=too-many-instance-attributes
class JqBinarySensor(BinarySensorEntity):
    """A binary sensor implementation for JQ device."""

    def __init__(
        self, entity_id, account: JqAccount, device_id, sensor_id, sensor_state
    ):
        """Initialize a binary sensor."""
        super().__init__()

        self.entity_id = entity_id

        device = account.update_devices()
        if device is None:
            raise exceptions.PlatformNotReady

        self._account = account
        self._device = device.get(device_id, {})
        self._device_id = device_id
        self._unique_id = "{}-{}-{}".format(
            self._account.unique_id, device_id, sensor_id
        )
        self._name = "{} {}".format(
            self._device.get("pt_name"), BINARY_SENSORS[sensor_id][0]
        )
        self._sensor_id = sensor_id
        self._state = sensor_state
        self._icon = BINARY_SENSORS[sensor_id][2]
        self._device_class = BINARY_SENSORS[sensor_id][3]

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._account.device_available(self._device_id)

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return bool(self._state)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DEVICE_BRAND: self._device.get("brandname"),
            ATTR_DEVICE_MODEL: self._device.get("pt_model"),
            ATTR_DEVICE_ID: self._device.get("deviceid"),
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def should_poll(self):
        """Return the polling state."""
        return True

    def update(self):
        """Update the sensor state if it needed."""
        ret = self._account.get_sensors_raw(self._device_id)
        if not ret:
            return

        if self._state == ret[self._sensor_id]:
            return

        self._state = ret[self._sensor_id]
        _LOGGER.debug("Update state: %s = %s", self.entity_id, self._state)
