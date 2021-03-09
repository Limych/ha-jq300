"""Constants for tests."""
from homeassistant.const import CONF_DEVICES, CONF_PASSWORD, CONF_USERNAME

MOCK_USERNAME = "test@email.com"
MOCK_PASSWORD = "test_password"

# Mock config data to be used across multiple tests
MOCK_CONFIG = {
    CONF_USERNAME: MOCK_USERNAME,
    CONF_PASSWORD: MOCK_PASSWORD,
    CONF_DEVICES: ["test_name"],
}
