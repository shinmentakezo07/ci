"""Provider configuration status for the Admin UI."""

from collections.abc import Mapping
from typing import Any

from free_claude_code.config.provider_catalog import PROVIDER_CATALOG

from .manifest import FIELDS


def _provider_has_credential(
    state: Mapping[str, Mapping[str, Any]], base_env: str
) -> bool:
    """Return True when any credential slot for a provider is non-empty."""
    value = str(state.get(base_env, {}).get("value", ""))
    if value.strip():
        return True
    index = 1
    while True:
        numbered = str(state.get(f"{base_env}_{index}", {}).get("value", ""))
        next_numbered = str(state.get(f"{base_env}_{index + 1}", {}).get("value", ""))
        if numbered.strip():
            return True
        if not next_numbered.strip():
            return False
        index += 1


def provider_config_status(
    state: Mapping[str, Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Return provider configuration status without making network calls."""
    statuses: list[dict[str, Any]] = []
    for provider_id, descriptor in PROVIDER_CATALOG.items():
        if descriptor.local:
            base_url = ""
            if descriptor.base_url_attr is not None:
                base_url = _value_for_settings_attr(state, descriptor.base_url_attr)
            statuses.append(
                {
                    "provider_id": provider_id,
                    "display_name": descriptor.display_name,
                    "kind": "local",
                    "status": "missing_url" if not base_url.strip() else "unknown",
                    "label": "Missing URL" if not base_url.strip() else "Not checked",
                    "base_url": base_url or descriptor.default_base_url or "",
                }
            )
            continue

        configured = _provider_has_credential(state, descriptor.credential_env or "")
        statuses.append(
            {
                "provider_id": provider_id,
                "display_name": descriptor.display_name,
                "kind": "remote",
                "status": "configured" if configured else "missing_key",
                "label": "Configured" if configured else "Missing key",
                "credential_env": descriptor.credential_env,
            }
        )
    return statuses


def _value_for_settings_attr(
    state: Mapping[str, Mapping[str, Any]], settings_attr: str
) -> str:
    for field in FIELDS:
        if field.settings_attr == settings_attr:
            return str(state.get(field.key, {}).get("value", field.default))
    return ""
