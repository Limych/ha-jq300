# pylint: disable=protected-access,redefined-outer-name
"""The test for the binary sensor platform."""

from custom_components.jq300 import Jq300Account
from custom_components.jq300.binary_sensor import Jq300BinarySensor


async def test_entity_initialization(mock_account: Jq300Account):
    """Test entity initialization."""
    mock_account._devices = {123: {"pt_name": "Kitchen"}}

    entity = Jq300BinarySensor("test", mock_account, 123, 1, False)

    assert entity.name == "Kitchen Air Quality Alert"
    assert entity.icon == "mdi:alert"
    assert entity.device_class == "problem"

    assert entity.is_on is False

    entity.update()
    assert entity.is_on is False

    mock_account._sensors_raw[123] = {1: False}
    entity.update()
    assert entity.is_on is False

    mock_account._sensors_raw[123] = {1: True}
    entity.update()
    assert entity.is_on is True
