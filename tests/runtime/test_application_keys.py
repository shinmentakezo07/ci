"""Tests for ApplicationRuntime provider key management."""

from free_claude_code.api.ports import AdminRuntimePort


def test_admin_runtime_port_has_key_methods():
    assert hasattr(AdminRuntimePort, "list_provider_keys")
    assert hasattr(AdminRuntimePort, "add_provider_key")
    assert hasattr(AdminRuntimePort, "remove_provider_key")
