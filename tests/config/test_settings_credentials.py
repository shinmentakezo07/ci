"""Tests for Settings.provider_credentials helper."""

import os

import pytest

from free_claude_code.config.credentials import ProviderCredential
from free_claude_code.config.settings import Settings


@pytest.fixture
def clean_env(monkeypatch):
    for key in list(os.environ):
        if key.startswith("OPENROUTER_API_KEY"):
            monkeypatch.delenv(key, raising=False)


def test_provider_credentials_base_only(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "primary")
    settings = Settings()
    creds = settings.provider_credentials("OPENROUTER_API_KEY")
    assert creds == (ProviderCredential("primary"),)


def test_provider_credentials_with_numbered_keys(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "primary")
    monkeypatch.setenv("OPENROUTER_API_KEY_1", "second")
    monkeypatch.setenv("OPENROUTER_API_KEY_1_LABEL", "Personal")
    monkeypatch.setenv("OPENROUTER_API_KEY_2", "third")
    settings = Settings()
    creds = settings.provider_credentials("OPENROUTER_API_KEY")
    assert creds == (
        ProviderCredential("primary"),
        ProviderCredential("second", "Personal"),
        ProviderCredential("third"),
    )


def test_provider_credentials_ignores_empty_and_gaps(clean_env, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "primary")
    monkeypatch.setenv("OPENROUTER_API_KEY_2", "third")
    settings = Settings()
    creds = settings.provider_credentials("OPENROUTER_API_KEY")
    assert creds == (
        ProviderCredential("primary"),
        ProviderCredential("third"),
    )
