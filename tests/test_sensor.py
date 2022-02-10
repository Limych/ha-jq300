# pylint: disable=protected-access,redefined-outer-name
"""The test for the sensor platform."""

import homeassistant.util.dt as dt_util
from homeassistant.core import HomeAssistant

from custom_components.jq300 import Jq300Account
from custom_components.jq300.const import ATTRIBUTION
from custom_components.jq300.sensor import Jq300Sensor


async def test_entity_initialization(hass: HomeAssistant, mock_account: Jq300Account):
    """Test entity initialization."""
    mock_account._devices = {123: {"pt_name": "Kitchen"}}

    entity = Jq300Sensor("test", mock_account, 123, 7, 12)
    entity.hass = hass

    expected_attributes = {
        "attribution": ATTRIBUTION,
        "raw_state": 12,
    }

    assert entity.name == "Kitchen HCHO"
    assert entity.icon == "mdi:cloud"
    assert entity.device_class is None
    assert entity.extra_state_attributes == expected_attributes

    assert entity.state == 12
    assert entity.unit_of_measurement == "ppb"

    entity.update()
    assert entity.state == 12

    ts_now = int(dt_util.now().timestamp())

    data = {7: 12}
    mock_account._sensors[123][ts_now] = data
    mock_account._sensors_raw[123] = data
    #
    entity.update()
    assert entity.state == 12

    data = {7: 23}
    mock_account._sensors[123][ts_now] = data
    mock_account._sensors_raw[123] = data
    #
    entity.update()
    assert entity.state == 23
