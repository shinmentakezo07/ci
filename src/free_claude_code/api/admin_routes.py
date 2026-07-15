"""Local admin UI routes and APIs."""

import binascii
import ipaddress
import secrets
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from free_claude_code.config.admin.manifest import FIELD_BY_KEY
from free_claude_code.config.admin.persistence import validate_updates
from free_claude_code.config.admin.values import load_config_response
from free_claude_code.config.settings import Settings

from .dependencies import get_services
from .ports import ApiServices

router = APIRouter()

STATIC_DIR = Path(__file__).resolve().parent / "admin_static"
LOCAL_PROVIDER_PATHS = {
    "lmstudio": "/models",
    "llamacpp": "/models",
    "ollama": "/api/tags",
}


class AdminConfigPayload(BaseModel):
    """Partial config update submitted by the admin UI."""

    values: dict[str, Any] = Field(default_factory=dict)


class AddKeyPayload(BaseModel):
    """New provider key submitted by the admin UI."""

    value: str
    label: str = ""


def _is_loopback_host(host: str | None) -> bool:
    if host is None:
        return False
    normalized = host.strip().strip("[]").lower()
    if normalized == "localhost":
        return True
    try:
        return ipaddress.ip_address(normalized).is_loopback
    except ValueError:
        return False


def _origin_is_local(origin: str | None) -> bool:
    if not origin:
        return True
    parsed = urlsplit(origin)
    return _is_loopback_host(parsed.hostname)


def _decode_basic_auth(header: str) -> tuple[str, str] | None:
    """Return (username, password) from an HTTP Basic Authorization header."""

    parts = header.strip().split(maxsplit=1)
    if len(parts) != 2 or parts[0].casefold() != "basic":
        return None
    try:
        decoded = binascii.a2b_base64(parts[1].strip()).decode("utf-8")
    except binascii.Error, ValueError, UnicodeDecodeError:
        return None
    if ":" not in decoded:
        return None
    username, password = decoded.split(":", 1)
    return username, password


def _remote_admin_basic_auth_ok(request: Request, token: str) -> bool:
    """Verify HTTP Basic auth where the password equals the proxy token."""

    if not token:
        return False
    credentials = _decode_basic_auth(request.headers.get("authorization", ""))
    if credentials is None:
        return False
    return secrets.compare_digest(credentials[1].encode("utf-8"), token.encode("utf-8"))


def _settings_for_admin(request: Request) -> Settings | None:
    """Current settings snapshot for the admin auth decision.

    Mirrors ``get_settings`` but is read from app state so the route handlers
    can keep calling ``require_loopback_admin(request)`` imperatively. Returns
    ``None`` when no snapshot is available (e.g. an in-process test fake) — the
    guard treats that as "remote not allowed" and fails closed.
    """

    return request.app.state.services.requests.current_settings()


def require_loopback_admin(request: Request) -> None:
    """Allow admin access from the local machine, or remotely when opted in.

    Local (loopback) clients are always allowed. Non-loopback clients are only
    allowed when ``ADMIN_REMOTE_ALLOWED`` is enabled AND the request carries
    HTTP Basic auth whose password equals the configured ``ANTHROPIC_AUTH_TOKEN``
    — the same secret that protects the proxy. Remote access without that opt-in,
    without a token, or with a wrong token is rejected with 403/401. If no
    settings snapshot is available, remote access is rejected (fail closed).
    """

    client_host = request.client.host if request.client else None
    if _is_loopback_host(client_host) and _origin_is_local(
        request.headers.get("origin")
    ):
        return

    settings = _settings_for_admin(request)
    if settings is None or not settings.admin_remote_allowed:
        raise HTTPException(status_code=403, detail="Admin UI is local-only")

    token = settings.anthropic_auth_token.strip()
    if not token:
        # Refuse to expose the admin UI remotely without a guarding secret.
        raise HTTPException(
            status_code=403,
            detail="Admin UI is local-only (set ANTHROPIC_AUTH_TOKEN for remote access)",
        )

    if not _remote_admin_basic_auth_ok(request, token):
        raise HTTPException(
            status_code=401,
            detail="Admin authentication required",
            headers={"WWW-Authenticate": 'Basic realm="fcc-admin"'},
        )


def _asset_response(filename: str) -> FileResponse:
    path = STATIC_DIR / filename
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return FileResponse(path)


@router.get("/admin", include_in_schema=False)
async def admin_page(request: Request):
    require_loopback_admin(request)
    return _asset_response("index.html")


@router.get("/admin/assets/{filename}", include_in_schema=False)
async def admin_asset(filename: str, request: Request):
    require_loopback_admin(request)
    if filename not in {"admin.css", "admin.js"}:
        raise HTTPException(status_code=404, detail="Admin asset not found")
    return _asset_response(filename)


@router.get("/admin/api/config")
async def get_admin_config(request: Request):
    require_loopback_admin(request)
    return load_config_response()


@router.post("/admin/api/config/validate")
async def validate_admin_config(payload: AdminConfigPayload, request: Request):
    require_loopback_admin(request)
    return validate_updates(_filtered_values(payload.values))


@router.post("/admin/api/config/apply")
async def apply_admin_config(
    payload: AdminConfigPayload,
    request: Request,
    background_tasks: BackgroundTasks,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    result = await services.admin.apply_admin_config(_filtered_values(payload.values))
    restart = result.get("restart")
    if isinstance(restart, dict) and restart.get("automatic"):
        background_tasks.add_task(services.admin.request_restart)
    return result


@router.get("/admin/api/status")
async def admin_status(
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return services.admin.admin_status()


@router.get("/admin/api/providers/local-status")
async def local_provider_status(request: Request):
    require_loopback_admin(request)
    config = load_config_response()
    values = {field["key"]: field["value"] for field in config["fields"]}
    checks = []
    for provider_id, path in LOCAL_PROVIDER_PATHS.items():
        base_url = _local_provider_url(provider_id, values)
        checks.append(await _check_local_provider(provider_id, base_url, path))
    return {"providers": checks}


@router.post("/admin/api/providers/{provider_id}/test")
async def test_provider(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.test_provider(provider_id)


@router.post("/admin/api/models/refresh")
async def refresh_models(
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.refresh_models()


@router.get("/admin/api/providers/{provider_id}/keys")
async def list_provider_keys(
    provider_id: str,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.list_provider_keys(provider_id)


@router.post("/admin/api/providers/{provider_id}/keys")
async def add_provider_key(
    provider_id: str,
    payload: AddKeyPayload,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.add_provider_key(
        provider_id, payload.value, payload.label
    )


@router.delete("/admin/api/providers/{provider_id}/keys/{index}")
async def remove_provider_key(
    provider_id: str,
    index: int,
    request: Request,
    services: ApiServices = Depends(get_services),
):
    require_loopback_admin(request)
    return await services.admin.remove_provider_key(provider_id, index)


def _filtered_values(values: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in values.items() if key in FIELD_BY_KEY}


def _local_provider_url(provider_id: str, values: dict[str, str]) -> str:
    if provider_id == "lmstudio":
        return values.get("LM_STUDIO_BASE_URL", "")
    if provider_id == "llamacpp":
        return values.get("LLAMACPP_BASE_URL", "")
    if provider_id == "ollama":
        return values.get("OLLAMA_BASE_URL", "")
    return ""


async def _check_local_provider(
    provider_id: str, base_url: str, path: str
) -> dict[str, Any]:
    clean_url = base_url.strip().rstrip("/")
    if not clean_url:
        return {
            "provider_id": provider_id,
            "status": "missing_url",
            "label": "Missing URL",
            "base_url": base_url,
        }

    url = f"{clean_url}{path}"
    try:
        async with httpx.AsyncClient(timeout=1.5) as client:
            response = await client.get(url)
        ok = 200 <= response.status_code < 300
        return {
            "provider_id": provider_id,
            "status": "reachable" if ok else "offline",
            "label": "Reachable" if ok else "Offline",
            "base_url": base_url,
            "status_code": response.status_code,
        }
    except Exception as exc:
        return {
            "provider_id": provider_id,
            "status": "offline",
            "label": "Offline",
            "base_url": base_url,
            "error_type": type(exc).__name__,
        }
