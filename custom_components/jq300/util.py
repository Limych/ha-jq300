#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import logging

_LOGGER = logging.getLogger(__name__)


def mask(text: str, first: int = 2, last: int = 1):
    """Mask text by asterisks."""
    tlen = len(text)
    to_show = first + last
    return (
        ("" if tlen <= to_show else text[:first])
        + "*" * (tlen - (0 if tlen <= to_show else to_show))
        + ("" if tlen <= to_show else text[-last:])
    )


def mask_email(email: str):
    """Mask email by asterisks."""
    local, _, domain = email.partition("@")
    parts = domain.split(".")
    dname = ".".join(parts[:-1])
    dtype = parts[-1]
    return "{}@{}.{}".format(mask(local), mask(dname), dtype)
