#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import logging

from homeassistant.const import ATTR_ATTRIBUTION, ATTR_DEVICE_ID
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from custom_components.jq300 import Jq300Account

from .const import (
    ATTR_DEVICE_BRAND,
    ATTR_DEVICE_MODEL,
    ATTRIBUTION,
    DOMAIN,
    NAME,
    VERSION,
)

_LOGGER = logging.getLogger(__name__)


class Jq300Entity(Entity):
    """Jq300 entity."""

    def __init__(
        self, entity_id: str, account: Jq300Account, device_id, sensor_id, sensor_state
    ):
        """Initialize a JQ entity."""
        super().__init__()

        self.entity_id = entity_id

        if account.devices == {}:
            raise PlatformNotReady

        self._name = None
        self._icon = None
        self._account = account
        self._device = account.devices.get(device_id, {})
        self._device_id = device_id
        self._unique_id = "{}-{}-{}".format(
            self._account.unique_id, device_id, sensor_id
        )
        self._sensor_id = sensor_id
        self._state = sensor_state

        self._device_class = None

    @property
    def unique_id(self):
        """Return a unique ID to use for this entity."""
        return self._unique_id

    @property
    def name(self):
        """Return the name of the binary sensor."""
        return self._name

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._account.device_available(self._device_id)

    @property
    def should_poll(self) -> bool:
        """Return the polling state."""
        return True

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def device_info(self):
        """Return the device info."""
        return {
            "identifiers": {(DOMAIN, self.unique_id)},
            "name": NAME,
            "model": VERSION,
        }

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DEVICE_BRAND: self._device.get("brandname"),
            ATTR_DEVICE_MODEL: self._device.get("pt_model"),
            ATTR_DEVICE_ID: self._device.get("deviceid"),
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
