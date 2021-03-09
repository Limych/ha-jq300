# pylint: disable=protected-access,redefined-outer-name
"""The test for the entity."""

from homeassistant.exceptions import PlatformNotReady
from pytest import raises

from custom_components.jq300 import Jq300Account
from custom_components.jq300.const import ATTRIBUTION, DOMAIN, NAME, VERSION
from custom_components.jq300.entity import Jq300Entity


async def test_entity_initialization(mock_account: Jq300Account):
    """Test sensor initialization."""
    with raises(PlatformNotReady):
        _ = Jq300Entity("test", mock_account, 123, 7, 12)

    mock_account._devices = {123: {"pt_name": "Kitchen"}}

    entity = Jq300Entity("test", mock_account, 123, 7, 12)

    expected_device_info = {
        "identifiers": {(DOMAIN, "test@email.com-123-7")},
        "model": VERSION,
        "name": NAME,
    }
    expected_attributes = {
        "attribution": ATTRIBUTION,
        "device_brand": None,
        "device_id": None,
        "device_model": None,
    }

    assert entity.unique_id == "test@email.com-123-7"
    assert entity.name is None
    assert entity.icon is None
    assert entity.available is False
    assert entity.should_poll is True
    assert entity.device_class is None
    assert entity.device_info == expected_device_info
    assert entity.device_state_attributes == expected_attributes
