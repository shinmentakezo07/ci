"""Runtime capabilities consumed by the HTTP API adapter."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Protocol

from free_claude_code.application.ports import RequestRuntimePort, TaskController


class AdminRuntimePort(Protocol):
    """Runtime operations exposed by the local Admin API."""

    async def apply_admin_config(
        self, updates: Mapping[str, Any]
    ) -> dict[str, Any]: ...

    def admin_status(self) -> dict[str, Any]: ...

    async def test_provider(self, provider_id: str) -> dict[str, Any]: ...

    async def refresh_models(self) -> dict[str, Any]: ...

    async def request_restart(self) -> None: ...

    async def list_provider_keys(self, provider_id: str) -> dict[str, Any]: ...

    async def add_provider_key(
        self, provider_id: str, value: str, label: str
    ) -> dict[str, Any]: ...

    async def remove_provider_key(
        self, provider_id: str, index: int
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class ApiServices:
    """Complete runtime boundary required to construct the API application."""

    requests: RequestRuntimePort
    admin: AdminRuntimePort
    tasks: TaskController
