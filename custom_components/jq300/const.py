"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

# Base component constants
DOMAIN = "jq300"
VERSION = "0.1.0"
ISSUE_URL = "https://github.com/Limych/ha-jq300/issues"
ATTRIBUTION = None
DATA_JQ300 = 'jq300'

SUPPORT_LIB_URL = "https://github.com/Limych/jq300/issues/new/choose"

_UA_SYSTEM = "Android 6.0.1; RedMi Note 5 Build/RB3N5C"
UA_DALVIK = f"Dalvik/2.1.0 (Linux; U; {_UA_SYSTEM})"
UA_MOZILLA = f"Mozilla/5.0 (Linux; {_UA_SYSTEM}; wv) AppleWebKit/537.36 " \
             "(KHTML, like Gecko) Version/4.0 Chrome/68.0.3440.91 Mobile " \
             "Safari/537.36"
