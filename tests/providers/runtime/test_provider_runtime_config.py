"""Tests for provider runtime config construction."""

import os

import pytest

from free_claude_code.config.provider_catalog import PROVIDER_CATALOG
from free_claude_code.config.settings import Settings
from free_claude_code.providers.runtime.config import build_provider_config


@pytest.fixture
def clean_openrouter_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("OPENROUTER_API_KEY"):
            monkeypatch.delenv(key, raising=False)


def test_build_provider_config_with_multiple_keys(clean_openrouter_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "primary")
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "second")
    settings = Settings()
    descriptor = PROVIDER_CATALOG["open_router"]
    config = build_provider_config(descriptor, settings)
    assert config.api_keys == ("primary", "second")
