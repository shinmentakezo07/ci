"""Tests for admin provider key management API routes."""

from fastapi.testclient import TestClient

from free_claude_code.api.app import create_app
from free_claude_code.api.ports import AdminRuntimePort, ApiServices
from free_claude_code.application.ports import RequestRuntimePort, TaskController


class FakeAdmin(AdminRuntimePort):
    async def apply_admin_config(self, updates):
        return {}

    def admin_status(self):
        return {}

    async def test_provider(self, provider_id):
        return {}

    async def refresh_models(self):
        return {}

    async def request_restart(self):
        pass

    async def list_provider_keys(self, provider_id):
        return {"provider_id": provider_id, "keys": []}

    async def add_provider_key(self, provider_id, value, label):
        return {"provider_id": provider_id, "index": 1}

    async def remove_provider_key(self, provider_id, index):
        return {"provider_id": provider_id, "index": index}


class FakeRequests(RequestRuntimePort):
    async def acquire(self):
        return None

    def current_settings(self):
        return None

    def cached_model_supports_thinking(self, provider_id, model_id):
        return False

    def cached_prefixed_model_infos(self):
        return {}


class FakeTasks(TaskController):
    async def stop_all(self) -> None:
        pass


def test_list_keys_requires_loopback():
    app = create_app(
        ApiServices(
            requests=FakeRequests(),
            admin=FakeAdmin(),
            tasks=FakeTasks(),
        )
    )
    client = TestClient(app)
    response = client.get("/admin/api/providers/open_router/keys")
    assert response.status_code == 403
