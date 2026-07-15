"""Credential ring for provider API key rotation."""

from free_claude_code.config.credentials import ProviderCredential

__all__ = ["CredentialRing", "ProviderCredential"]


class CredentialRing:
    """Round-robin selector over a non-empty tuple of credential strings."""

    def __init__(self, credentials: tuple[str, ...]) -> None:
        if not credentials:
            raise ValueError("CredentialRing requires at least one credential")
        self._credentials = credentials
        self._index = 0

    def next(self) -> str:
        key = self._credentials[self._index]
        self._index = (self._index + 1) % len(self._credentials)
        return key

    def __len__(self) -> int:
        return len(self._credentials)
