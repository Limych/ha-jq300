"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#
#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
#

# Base component constants
DOMAIN = "jq300"
VERSION = "0.1.0"
ISSUE_URL = "https://github.com/Limych/ha-jq300/issues"
ATTRIBUTION = None
DATA_JQ300 = 'jq300'

SUPPORT_LIB_URL = "https://github.com/Limych/jq300/issues/new/choose"

# Error strings
MSG_GENERIC_FAIL = 'Sorry.. Something went wrong...'
MSG_LOGIN_FAIL = 'Account name or password is wrong, please try again'

QUERY_TYPE_API = 'API'
QUERY_TYPE_DEVICE = 'DEVICE'

QUERY_METHOD_GET = 'GET'
QUERY_METHOD_POST = 'POST'

BASE_URL_API = "http://www.youpinyuntai.com:32086/ypyt-api/api/app/"
BASE_URL_DEVICE = "https://www.youpinyuntai.com:31447/device/"

_USERAGENT_SYSTEM = "Android 6.0.1; RedMi Note 5 Build/RB3N5C"
USERAGENT_API = f"Dalvik/2.1.0 (Linux; U; {_USERAGENT_SYSTEM})"
USERAGENT_DEVICE = f"Mozilla/5.0 (Linux; {_USERAGENT_SYSTEM}; wv) " \
                   "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 " \
                   "Chrome/68.0.3440.91 Mobile Safari/537.36"

QUERY_TIMEOUT = 12
