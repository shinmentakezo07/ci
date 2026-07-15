"""Remote admin access (cloud/container) auth gate tests.

The admin UI is loopback-only by default. With ``ADMIN_REMOTE_ALLOWED=true``
plus a configured ``ANTHROPIC_AUTH_TOKEN``, remote clients reach it over HTTP
Basic auth (password == token). See ``require_loopback_admin``.
"""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from tests.api.support import create_test_app


def _set_home(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.chdir(tmp_path)


def _clear_process_config(monkeypatch) -> None:
    for key in (
        "MODEL",
        "NVIDIA_NIM_API_KEY",
        "HUGGINGFACE_API_KEY",
        "OPENROUTER_API_KEY",
        "OLLAMA_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "TELEGRAM_PROXY_URL",
        "FCC_ENV_FILE",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
        "GITHUB_MODELS_TOKEN",
        "SAMBANOVA_API_KEY",
        "HOST",
        "PORT",
        "FCC_OPEN_BROWSER",
        "ADMIN_REMOTE_ALLOWED",
        "VOICE_NOTE_ENABLED",
        "WHISPER_DEVICE",
        "LOG_FILE",
        "ZAI_BASE_URL",
        "CLAUDE_WORKSPACE",
        "CLAUDE_CLI_BIN",
    ):
        monkeypatch.delenv(key, raising=False)


def _basic_auth(username: str, password: str) -> dict[str, str]:
    import base64

    token = base64.b64encode(f"{username}:{password}".encode()).decode("ascii")
    return {"Authorization": f"Basic {token}"}


def test_remote_admin_blocked_by_default(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get("/admin")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin UI is local-only"


def test_remote_admin_opt_in_without_token_still_blocked(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get("/admin")

    assert response.status_code == 403
    assert "ANTHROPIC_AUTH_TOKEN" in response.json()["detail"]


def test_remote_admin_opt_in_requires_basic_auth(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "s3cret-token")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get("/admin")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="fcc-admin"'


def test_remote_admin_opt_in_rejects_wrong_password(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "s3cret-token")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get(
        "/admin", headers=_basic_auth("admin", "wrong-password")
    )

    assert response.status_code == 401


def test_remote_admin_opt_in_accepts_correct_basic_auth(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "s3cret-token")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get("/admin", headers=_basic_auth("admin", "s3cret-token"))

    assert response.status_code == 200


def test_remote_admin_api_endpoint_accepts_correct_basic_auth(monkeypatch, tmp_path):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "s3cret-token")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))
    auth = _basic_auth("admin", "s3cret-token")

    response = remote_client.get("/admin/api/config", headers=auth)

    assert response.status_code == 200
    assert "fields" in response.json()


def test_local_admin_still_allowed_without_token_when_remote_disabled(
    monkeypatch, tmp_path
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    app = create_test_app()
    local_client = TestClient(app, client=("127.0.0.1", 50000))

    assert local_client.get("/admin").status_code == 200


@pytest.mark.parametrize(
    "bad_header", ["Bearer s3cret-token", "Basic !!!notb64!!!", "Basic"]
)
def test_remote_admin_rejects_malformed_authorization(
    monkeypatch, tmp_path, bad_header
):
    _set_home(monkeypatch, tmp_path)
    _clear_process_config(monkeypatch)
    monkeypatch.setenv("ADMIN_REMOTE_ALLOWED", "true")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "s3cret-token")
    app = create_test_app()
    remote_client = TestClient(app, client=("203.0.113.10", 50000))

    response = remote_client.get("/admin", headers={"Authorization": bad_header})

    assert response.status_code == 401
