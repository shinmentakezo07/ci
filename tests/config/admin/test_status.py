"""Tests for admin provider config status with numbered keys."""

import os

import pytest

from free_claude_code.config.admin.status import provider_config_status
from free_claude_code.config.admin.values import load_value_state


@pytest.fixture
def clean_openrouter_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("OPENROUTER_API_KEY"):
            monkeypatch.delenv(key, raising=False)


def test_status_configured_when_numbered_key_exists(clean_openrouter_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "extra")
    state = load_value_state()
    statuses = {s["provider_id"]: s for s in provider_config_status(state)}
    assert statuses["open_router"]["status"] == "configured"
