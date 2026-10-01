"""Explicit credentials for legacy tests against a separately configured test server."""
import os

import pytest


def credentials(role):
    prefix = f"TEST_{role}"
    username = os.environ.get(f"{prefix}_USERNAME")
    password = os.environ.get(f"{prefix}_PASSWORD")
    if not username or not password:
        pytest.skip(f"Set {prefix}_USERNAME and {prefix}_PASSWORD for the test server", allow_module_level=True)
    return {"username": username, "password": password}
