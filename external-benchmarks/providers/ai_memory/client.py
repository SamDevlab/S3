"""Read-only HTTP client for the optional AI-MEMORY benchmark provider."""

from __future__ import annotations

import ipaddress
import json
import os
import re
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen

PROBE_SCHEMA_VERSION = "1.0.0"
_DEFAULT_SERVER_URL = "http://127.0.0.1:49374"
_SCOPE_RE = re.compile(r"^[a-z0-9][a-z0-9._-]*$")


class AiMemoryProviderError(RuntimeError):
    """AI-MEMORY provider configuration or read-only probe failed."""


def validate_scope_name(value: str, name: str) -> str:
    if not isinstance(value, str) or not _SCOPE_RE.fullmatch(value):
        raise AiMemoryProviderError(
            f"{name} must match ^[a-z0-9][a-z0-9._-]*$"
        )
    return value


def _validated_base_url(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise AiMemoryProviderError("AI-MEMORY server URL must be a non-empty string")
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"}:
        raise AiMemoryProviderError("AI-MEMORY server URL must use http or https")
    if not parsed.hostname:
        raise AiMemoryProviderError("AI-MEMORY server URL must include a host")
    if parsed.username is not None or parsed.password is not None:
        raise AiMemoryProviderError("AI-MEMORY server URL must not contain embedded credentials")
    if parsed.query or parsed.fragment:
        raise AiMemoryProviderError("AI-MEMORY server URL must not contain query or fragment data")
    path = parsed.path.rstrip("/")
    if path not in {"", "/"}:
        raise AiMemoryProviderError("AI-MEMORY server URL must point at the server root")
    return f"{parsed.scheme}://{parsed.netloc}"


def _endpoint_class(hostname: str) -> str:
    if hostname.lower() == "localhost":
        return "loopback"
    try:
        address = ipaddress.ip_address(hostname.strip("[]"))
    except ValueError:
        return "remote"
    return "loopback" if address.is_loopback else "remote"


@dataclass(frozen=True)
class AiMemoryConfig:
    """Runtime-only connection settings. Tokens are never serialized by this module."""

    server_url: str = _DEFAULT_SERVER_URL
    auth_token: str | None = None
    timeout_seconds: float = 5.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "server_url", _validated_base_url(self.server_url))
        if self.auth_token is not None and not isinstance(self.auth_token, str):
            raise AiMemoryProviderError("AI-MEMORY auth token must be a string when present")
        if (
            not isinstance(self.timeout_seconds, (int, float))
            or isinstance(self.timeout_seconds, bool)
            or self.timeout_seconds <= 0
        ):
            raise AiMemoryProviderError("AI-MEMORY timeout must be positive")

    @classmethod
    def from_environment(
        cls,
        *,
        server_url: str | None = None,
        timeout_seconds: float = 5.0,
    ) -> "AiMemoryConfig":
        return cls(
            server_url=server_url or os.environ.get("AI_MEMORY_SERVER_URL", _DEFAULT_SERVER_URL),
            auth_token=os.environ.get("AI_MEMORY_AUTH_TOKEN"),
            timeout_seconds=timeout_seconds,
        )

    @property
    def transport(self) -> str:
        return urlsplit(self.server_url).scheme

    @property
    def endpoint_class(self) -> str:
        hostname = urlsplit(self.server_url).hostname or ""
        return _endpoint_class(hostname)


class AiMemoryClient:
    """Small stdlib-only client for AI-MEMORY's documented read-only `/api/v1`."""

    def __init__(self, config: AiMemoryConfig) -> None:
        self.config = config

    def _get_json(self, path: str, params: dict[str, str | int] | None = None) -> dict[str, Any]:
        if not path.startswith("/api/v1/"):
            raise AiMemoryProviderError("AI-MEMORY adapter permits only /api/v1 read endpoints")
        query = f"?{urlencode(params)}" if params else ""
        request = Request(
            f"{self.config.server_url}{path}{query}",
            method="GET",
            headers={
                "Accept": "application/json",
                **(
                    {"Authorization": f"Bearer {self.config.auth_token}"}
                    if self.config.auth_token
                    else {}
                ),
            },
        )
        try:
            with urlopen(request, timeout=float(self.config.timeout_seconds)) as response:  # noqa: S310
                raw = response.read()
        except HTTPError as error:
            raise AiMemoryProviderError(
                f"AI-MEMORY read-only API returned HTTP {error.code}"
            ) from error
        except URLError as error:
            raise AiMemoryProviderError("AI-MEMORY read-only API is unavailable") from error
        try:
            document = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise AiMemoryProviderError("AI-MEMORY read-only API returned invalid JSON") from error
        if not isinstance(document, dict):
            raise AiMemoryProviderError("AI-MEMORY read-only API response must be a JSON object")
        return document

    def probe(self, *, workspace: str, project: str) -> dict[str, Any]:
        """Check one benchmark scope without persisting endpoint or credential material."""

        workspace = validate_scope_name(workspace, "workspace")
        project = validate_scope_name(project, "project")
        workspaces = self._get_json("/api/v1/workspaces")
        projects = self._get_json("/api/v1/projects", {"workspace": workspace})
        workspace_rows = workspaces.get("workspaces")
        project_rows = projects.get("projects")
        if not isinstance(workspace_rows, list) or not isinstance(project_rows, list):
            raise AiMemoryProviderError("AI-MEMORY probe response shape is unsupported")

        workspace_present = any(
            isinstance(item, dict) and item.get("workspace_name") == workspace
            for item in workspace_rows
        )
        matching_project = next(
            (
                item
                for item in project_rows
                if isinstance(item, dict)
                and item.get("workspace_name") == workspace
                and item.get("project_name") == project
            ),
            None,
        )
        page_count = matching_project.get("page_count") if matching_project else None
        if not isinstance(page_count, int):
            page_count = None

        return {
            "schema_version": PROBE_SCHEMA_VERSION,
            "provider": {"id": "ai-memory"},
            "status": "PASS",
            "connection": {
                "transport": self.config.transport,
                "endpoint_class": self.config.endpoint_class,
                "auth_configured": bool(self.config.auth_token),
            },
            "scope": {
                "workspace_present": workspace_present,
                "project_present": matching_project is not None,
                "project_page_count": page_count,
            },
        }

    def search_count(
        self,
        *,
        workspace: str,
        project: str,
        query: str,
        limit: int = 10,
    ) -> int:
        """Return only hit count so benchmark diagnostics do not persist memory contents."""

        workspace = validate_scope_name(workspace, "workspace")
        project = validate_scope_name(project, "project")
        if not query:
            raise AiMemoryProviderError("search query must be non-empty")
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= 100:
            raise AiMemoryProviderError("search limit must be between 1 and 100")
        document = self._get_json(
            "/api/v1/search",
            {
                "q": query,
                "workspace": workspace,
                "project": project,
                "limit": limit,
            },
        )
        hits = document.get("hits")
        if not isinstance(hits, list):
            raise AiMemoryProviderError("AI-MEMORY search response shape is unsupported")
        return len(hits)
