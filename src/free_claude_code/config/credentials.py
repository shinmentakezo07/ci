"""Credential value objects shared between config and providers."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderCredential:
    """One provider credential with an optional display label."""

    value: str
    label: str = ""
