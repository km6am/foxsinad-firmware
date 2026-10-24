"""The docs must describe the firmware that's actually in this repo."""

import re

from conftest import REPO

INO = (REPO / "foxsinad_fw" / "foxsinad_fw.ino").read_text()
API = (REPO / "docs" / "API.md").read_text()


def _printf_to_regex(fmt):
    """printf format -> regex: each %-specifier matches one token, and any
    run of spaces matches any whitespace (the docs wrap lines)."""
    parts = re.split(r"%[-0-9.]*l?[a-z]", fmt)
    rx = r"\S+".join(re.escape(part) for part in parts)
    return rx.replace(re.escape(" "), r"\s+")


def test_every_command_is_documented():
    verbs = set(re.findall(r'strcmp\(verb, "([A-Z]+)"\)', INO))
    assert verbs, "found no commands in the firmware - has the parser changed?"
    missing = [v for v in sorted(verbs) if f"`{v}" not in API]
    assert not missing, f"commands missing from docs/API.md: {missing}"


def test_every_error_message_is_documented():
    errors = re.findall(r'Serial\.print(?:ln|f)\("(ERR [^"\\]*)', INO)
    assert errors, "found no ERR messages in the firmware"
    missing = [e for e in errors if not re.search(_printf_to_regex(e.strip()), API)]
    assert not missing, f"ERR messages missing from docs/API.md: {missing}"


def test_versions_agree():
    fw = re.search(r'#define FW_VERSION "([^"]+)"', INO).group(1)
    assert f"version **{fw}**" in API, "docs/API.md names a different firmware version"
    changelog = (REPO / "CHANGELOG.md").read_text()
    assert re.search(rf"^## {re.escape(fw)}\b", changelog, re.M), "CHANGELOG.md has no entry for this version"
