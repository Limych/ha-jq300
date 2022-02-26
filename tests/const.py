"""Constants for tests."""
from typing import Final

from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME

MOCK_USERNAME: Final = "test@email.com"
MOCK_PASSWORD: Final = "test_password"

# Mock config data to be used across multiple tests
MOCK_CONFIG: Final = {
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_DEVICES: ["test_name"],
}
