"""Tests for provider credential ring and credential value object."""

from dataclasses import FrozenInstanceError

import pytest

from free_claude_code.config.credentials import ProviderCredential
from free_claude_code.providers.credentials import CredentialRing


def test_credential_ring_rotates_sequentially() -> None:
    ring = CredentialRing(("a", "b", "c"))
    assert ring.next() == "a"
    assert ring.next() == "b"
    assert ring.next() == "c"
    assert ring.next() == "a"


def test_credential_ring_reports_length() -> None:
    assert len(CredentialRing(("a", "b"))) == 2


def test_credential_ring_rejects_empty() -> None:
    with pytest.raises(ValueError, match="at least one credential"):
        CredentialRing(())


def test_provider_credential_default_label_is_empty() -> None:
    credential = ProviderCredential("value")
    assert credential.value == "value"
    assert credential.label == ""


def test_provider_credential_accepts_label() -> None:
    credential = ProviderCredential("value", "Label")
    assert credential.value == "value"
    assert credential.label == "Label"


def test_provider_credential_is_frozen() -> None:
    credential = ProviderCredential("value")
    attribute = "value"
    with pytest.raises(FrozenInstanceError):
        setattr(credential, attribute, "new")
