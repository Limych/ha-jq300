#!/usr/bin/env python3
# Partially Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
"""Helper script to bump the current version."""
import argparse
import logging
import os
import sys
from datetime import datetime
import re
import subprocess

from packaging.version import Version

# http://docs.python.org/2/howto/logging.html#library-config
# Avoids spurious error messages if no logger is configured by the user
logging.getLogger(__name__).addHandler(logging.NullHandler())

# logging.basicConfig(level=logging.DEBUG)

_LOGGER = logging.getLogger(__name__)

VERSION = "1.3.1"

ROOT = os.path.dirname(os.path.abspath(f"{__file__}/.."))

sys.path.append(ROOT)


def _get_fallback_version(localpath):
    """Return version from regex match."""
    if os.path.isfile(localpath):
        with open(localpath) as local:
            ret = re.compile(r"^\b(VERSION|__version__)\s*=\s*['\"](.*)['\"]")
            for line in local.readlines():
                matcher = ret.match(line)
                if matcher:
                    return str(matcher.group(2))
    return ""


def get_fallback_version(localpath):
    """Return version from regex match."""
    if os.path.isfile(localpath):
        version = _get_fallback_version(localpath)
    else:
        for fname in ("__init__", "const"):
            fpath = f"{localpath}/{fname}.py"
            version = _get_fallback_version(fpath)
            if version != "":
                break
    return version


def get_package_version(localpath, package):
    """Return the local version if any."""
    _LOGGER.debug("Started for %s (%s)", localpath, package)
    return_value = ""
    if os.path.isfile(f"{localpath}/__init__.py"):
        try:
            name = "__version__"
            return_value = getattr(__import__(f"..{package}", fromlist=[name]), name)
        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.debug(str(err))
        if return_value == "":
            try:
                name = "VERSION"
                return_value = getattr(
                    __import__(f"..{package}", fromlist=[name]), name
                )
            except Exception as err:  # pylint: disable=broad-except
                _LOGGER.debug(str(err))
    if return_value == "":
        return_value = get_fallback_version(localpath)
    _LOGGER.debug(str(return_value))
    assert return_value, "Version not found!"
    return return_value


def _bump_release(release, bump_type):
    """Bump a release tuple consisting of 3 numbers."""
    major, minor, patch = release

    if bump_type == "patch":
        patch += 1
    elif bump_type == "minor":
        minor += 1
        patch = 0

    return major, minor, patch


def bump_version(version, bump_type):
    """Return a new version given a current version and action."""
    to_change = {}

    if bump_type == "minor":
        # Convert 0.67.3 to 0.68.0
        # Convert 0.67.3.b5 to 0.68.0
        # Convert 0.67.3.dev0 to 0.68.0
        # Convert 0.67.0.b5 to 0.67.0
        # Convert 0.67.0.dev0 to 0.67.0
        to_change["dev"] = None
        to_change["pre"] = None

        if not version.is_prerelease or version.release[2] != 0:
            to_change["release"] = _bump_release(version.release, "minor")

    elif bump_type == "patch":
        # Convert 0.67.3 to 0.67.4
        # Convert 0.67.3.b5 to 0.67.3
        # Convert 0.67.3.dev0 to 0.67.3
        to_change["dev"] = None
        to_change["pre"] = None

        if not version.is_prerelease:
            to_change["release"] = _bump_release(version.release, "patch")

    elif bump_type == "dev":
        # Convert 0.67.3 to 0.67.4.dev0
        # Convert 0.67.3.b5 to 0.67.4.dev0
        # Convert 0.67.3.dev0 to 0.67.3.dev1
        if version.is_devrelease:
            to_change["dev"] = ("dev", version.dev + 1)
        else:
            to_change["pre"] = ("dev", 0)
            to_change["release"] = _bump_release(version.release, "minor")

    elif bump_type == "beta":
        # Convert 0.67.5 to 0.67.6b0
        # Convert 0.67.0.dev0 to 0.67.0b0
        # Convert 0.67.5.b4 to 0.67.5b5

        if version.is_devrelease:
            to_change["dev"] = None
            to_change["pre"] = ("b", 0)

        elif version.is_prerelease:
            if version.pre[0] == "a":
                to_change["pre"] = ("b", 0)
            if version.pre[0] == "b":
                to_change["pre"] = ("b", version.pre[1] + 1)
            else:
                to_change["pre"] = ("b", 0)
                to_change["release"] = _bump_release(version.release, "patch")

        else:
            to_change["release"] = _bump_release(version.release, "patch")
            to_change["pre"] = ("b", 0)

    elif bump_type == "nightly":
        # Convert 0.70.0d0 to 0.70.0d20190424, fails when run on non dev release
        if not version.is_devrelease:
            raise ValueError("Can only be run on dev release")

        to_change["dev"] = (
            "dev",
            datetime.utcnow().date().isoformat().replace("-", ""),
        )

    else:
        assert False, f"Unsupported type: {bump_type}"

    temp = Version("0")
    temp._version = version._version._replace(  # pylint: disable=protected-access
        **to_change
    )
    return Version(str(temp))


def _write_version(localpath, version, dry_run=False):
    """Update package constant file with new version."""
    if not os.path.isfile(localpath):
        return

    _LOGGER.debug("Try to change %s", localpath)

    with open(localpath) as fil:
        cur_content = content = fil.read()

    content = re.sub(r"\nVERSION = .*\n", f'\nVERSION = "{version}"\n', content)
    content = re.sub(r"\n__version__ = .*\n", f'\n__version__ = "{version}"\n', content)

    if cur_content != content:
        _LOGGER.debug("%s changed", localpath)
        if dry_run:
            print("%s could was changed." % os.path.basename(localpath))
        else:
            with open(localpath, "wt") as fil:
                fil.write(content)


def write_version(localpath, version, dry_run=False):
    """Update package constant file with new version."""
    if os.path.isfile(localpath):
        _write_version(localpath, version, dry_run)
    else:
        for fname in ("__init__", "const"):
            _write_version(f"{localpath}/{fname}.py", version, dry_run)


def main():
    """Execute script."""
    package_path = package = None
    for current_path, dirs, _ in os.walk(f"{ROOT}/custom_components"):
        if current_path.find("__pycache__") != -1:
            continue
        for dname in dirs:
            if dname != "__pycache__":
                package = dname

    if package:
        package_path = f"{ROOT}/custom_components/{package}"
        package = f"custom_components.{package}"

    parser = argparse.ArgumentParser(
        description=f"Bump version of Python package. Version {VERSION}"
    )
    parser.add_argument(
        "type",
        help="The type of the bump the version to.",
        choices=["beta", "dev", "patch", "minor", "nightly"],
    )
    parser.add_argument(
        "-n",
        "--dry-run",
        "--dryrun",
        action="store_true",
        help="Preview version bumping without running it.",
    )
    parser.add_argument(
        "--commit", action="store_true", help="Create a version bump commit."
    )
    parser.add_argument(
        "--tag", action="store_true", help="Tag the commit with the new version."
    )
    parser.add_argument(
        "package_path",
        nargs="?",
        default=None,
        help=f"The path to package. Default: {package_path}",
    )
    arguments = parser.parse_args()

    if arguments.dry_run:
        print("!!! Dry Run !!! No Files Was Changed")

    # pylint: disable=subprocess-run-check
    if arguments.commit and subprocess.run(["git", "diff", "--quiet"]).returncode == 1:
        print("Cannot use --commit because git is dirty.")
        return

    if arguments.package_path is not None:
        package_path = os.path.abspath(arguments.package_path)
        package = package_path.split("/")[-1]
    else:
        assert package, "Component not found!"

    current = Version(get_package_version(package_path, package))
    bumped = bump_version(current, arguments.type)
    assert bumped > current, "BUG! New version is not newer than old version"

    if arguments.dry_run:
        print(f"Current version: {current}\n" f"    New version: {bumped}")

    write_version(package_path, bumped, arguments.dry_run)

    if not arguments.commit or arguments.dry_run:
        return

    subprocess.run(["git", "commit", "-nam", f"Bump version to {bumped}"])

    if arguments.tag:
        subprocess.run(["git", "tag", f"v{bumped}", "-am", f"Tagging version {bumped}"])


# pylint: disable=import-outside-toplevel
def test_bump_version():
    """Make sure it all works."""
    import pytest

    assert bump_version(Version("0.56.0"), "beta") == Version("0.56.1b0")
    assert bump_version(Version("0.56.0b3"), "beta") == Version("0.56.0b4")
    assert bump_version(Version("0.56.0.dev0"), "beta") == Version("0.56.0b0")

    assert bump_version(Version("0.56.3"), "dev") == Version("0.57.0.dev0")
    assert bump_version(Version("0.56.0b3"), "dev") == Version("0.57.0.dev0")
    assert bump_version(Version("0.56.0.dev0"), "dev") == Version("0.56.0.dev1")

    assert bump_version(Version("0.56.3"), "patch") == Version("0.56.4")
    assert bump_version(Version("0.56.3.b3"), "patch") == Version("0.56.3")
    assert bump_version(Version("0.56.0.dev0"), "patch") == Version("0.56.0")

    assert bump_version(Version("0.56.0"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.3"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.0.b3"), "minor") == Version("0.56.0")
    assert bump_version(Version("0.56.3.b3"), "minor") == Version("0.57.0")
    assert bump_version(Version("0.56.0.dev0"), "minor") == Version("0.56.0")
    assert bump_version(Version("0.56.2.dev0"), "minor") == Version("0.57.0")

    today = datetime.utcnow().date().isoformat().replace("-", "")
    assert bump_version(Version("0.56.0.dev0"), "nightly") == Version(
        f"0.56.0.dev{today}"
    )
    with pytest.raises(ValueError):
        assert bump_version(Version("0.56.0"), "nightly")


if __name__ == "__main__":
    main()
