"""Pure unit tests — no database, no event loop.

The parent tests/conftest.py installs an autouse async `_clean_db`
fixture that truncates tables before every test. That's right for the
API-level tests there, but these exercise plain functions and would
otherwise require a live Postgres to run at all. Overriding it with a
no-op sync fixture of the same name opts this directory out.
"""

import pytest


@pytest.fixture(autouse=True)
def _clean_db():
    yield
