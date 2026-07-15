"""Tests for admin provider key persistence helpers."""

import pytest

from free_claude_code.config.admin.persistence import (
    add_provider_credential,
    list_provider_credentials,
    remove_provider_credential,
)


@pytest.fixture
def temp_managed_env(tmp_path, monkeypatch):
    path = tmp_path / "managed.env"
    monkeypatch.setattr(
        "free_claude_code.config.admin.persistence.managed_env_path", lambda: path
    )
    monkeypatch.setattr(
        "free_claude_code.config.admin.persistence.managed_env_path",
        lambda: path,
    )
    path.write_text("OPENROUTER_API_KEY=primary\n")
    yield path


def test_list_provider_credentials(temp_managed_env):
    creds = list_provider_credentials("open_router", "OPENROUTER_API_KEY")
    assert creds == [
        {"index": 0, "value": "********", "label": ""},
    ]


def test_add_provider_credential(temp_managed_env):
    result = add_provider_credential(
        "open_router", "OPENROUTER_API_KEY", "new-key", "Work"
    )
    assert result["index"] == 1
    creds = list_provider_credentials("open_router", "OPENROUTER_API_KEY")
    assert len(creds) == 2
    assert creds[1]["label"] == "Work"
    content = temp_managed_env.read_text()
    assert "OPENROUTER_API_KEY_1=new-key" in content
    assert "OPENROUTER_API_KEY_1_LABEL=Work" in content


def test_remove_provider_credential(temp_managed_env):
    add_provider_credential("open_router", "OPENROUTER_API_KEY", "new-key", "Work")
    remove_provider_credential("open_router", "OPENROUTER_API_KEY", 1)
    creds = list_provider_credentials("open_router", "OPENROUTER_API_KEY")
    assert len(creds) == 1
    content = temp_managed_env.read_text()
    assert "OPENROUTER_API_KEY_1" not in content
