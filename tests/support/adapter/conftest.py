"""Fixtures shared by the adapter folders' tests."""

from __future__ import annotations

import pytest
from pydantic_settings import BaseSettings


@pytest.fixture()
def seed_env(monkeypatch):
    """Sets environment variables for a seeder, or unsets those given as None. The
    seeder's settings class then reads the process environment only, never the
    developer's `.env`."""

    def set_env(seed_settings_class: type[BaseSettings], values: dict) -> None:
        monkeypatch.setitem(seed_settings_class.model_config, "env_file", None)
        for name, value in values.items():
            if value is None:
                monkeypatch.delenv(name, raising=False)
            else:
                monkeypatch.setenv(name, str(value))

    return set_env
