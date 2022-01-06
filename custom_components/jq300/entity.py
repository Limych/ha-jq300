#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import logging

from homeassistant.const import ATTR_ATTRIBUTION
from homeassistant.exceptions import PlatformNotReady
from homeassistant.helpers.entity import Entity

from .api import Jq300Account
from .const import ATTRIBUTION, DOMAIN

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

        self._account = account
        self._device = account.devices.get(device_id, {})
        self._device_id = device_id
        self._sensor_id = sensor_id

        self._attr_unique_id = f"{self._account.unique_id}-{device_id}-{sensor_id}"
        self._attr_name = None
        self._attr_icon = None
        self._attr_device_class = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, self._account.unique_id, self._device_id)},
            "name": self._device.get("pt_name"),
            "manufacturer": self._device.get("brandname"),
            "model": self._device.get("pt_model"),
        }

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._account.device_available(self._device_id)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_ATTRIBUTION: ATTRIBUTION,
        }
