from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

EXTERNAL_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(EXTERNAL_ROOT))

from providers.ai_memory import client as client_module  # noqa: E402
from providers.ai_memory.cli import main as ai_memory_main  # noqa: E402
from providers.ai_memory.client import (  # noqa: E402
    AiMemoryClient,
    AiMemoryConfig,
    AiMemoryProviderError,
)
from providers.ai_memory.runner import (  # noqa: E402
    build_managed_run_command,
    execute_managed_run,
    workstream_name_from_plan,
)


class _Response:
    def __init__(self, document: object) -> None:
        self._payload = json.dumps(document).encode("utf-8")

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self) -> bytes:
        return self._payload


def _plan(provider_id: str = "ai-memory") -> dict[str, object]:
    return {
        "schema_version": "1.0.0",
        "campaign_id": "agent-memory-v1",
        "campaign_version": "1.0.0",
        "provider": {"id": provider_id, "version": "2.x"},
        "agent": {"provider": "openai", "model": "fixture", "harness": "codex"},
        "execution": {
            "s3_commit": "abc123",
            "agent_harness_version": "1",
            "tool_permissions_profile": "standard",
            "task_protocol_version": "agent-memory-v1",
            "repetition": 2,
        },
        "run_root": f"{provider_id}/run-2",
        "scenarios": [
            {
                "scenario_id": "memory.host-shell-policy.v1",
                "mode": "single-session",
                "template": "templates/agent-memory-v1/single-session.json",
                "worktree_key": "one",
                "observation_path": "one.observation.json",
                "result_path": "one.json",
                "required_evidence": [],
            },
            {
                "scenario_id": "memory.cross-session.v1",
                "mode": "cross-session",
                "template": "templates/agent-memory-v1/cross-session.json",
                "worktree_key": "two",
                "observation_path": "two.observation.json",
                "result_path": "two.json",
                "required_evidence": ["handoff"],
            },
        ],
    }


def test_ai_memory_config_rejects_credentials_in_url() -> None:
    with pytest.raises(AiMemoryProviderError, match="embedded credentials"):
        AiMemoryConfig(server_url="http://user:secret@127.0.0.1:49374")


def test_read_only_probe_never_persists_token_or_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    seen_urls: list[str] = []
    seen_auth: list[str | None] = []

    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        assert timeout == 3.0
        seen_urls.append(request.full_url)  # type: ignore[attr-defined]
        seen_auth.append(request.headers.get("Authorization"))  # type: ignore[attr-defined]
        if request.full_url.endswith("/api/v1/workspaces"):  # type: ignore[attr-defined]
            return _Response(
                {"workspaces": [{"workspace_name": "s3bench", "project_count": 1}]}
            )
        return _Response(
            {
                "projects": [
                    {
                        "workspace_name": "s3bench",
                        "project_name": "s3-agent-memory-v1",
                        "page_count": 12,
                    }
                ]
            }
        )

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)
    client = AiMemoryClient(
        AiMemoryConfig(
            server_url="http://127.0.0.1:49374",
            auth_token="super-secret",
            timeout_seconds=3.0,
        )
    )

    result = client.probe(workspace="s3bench", project="s3-agent-memory-v1")

    assert result["status"] == "PASS"
    assert result["connection"] == {
        "transport": "http",
        "endpoint_class": "loopback",
        "auth_configured": True,
    }
    assert result["scope"]["project_page_count"] == 12  # type: ignore[index]
    serialized = json.dumps(result)
    assert "super-secret" not in serialized
    assert "127.0.0.1" not in serialized
    assert seen_auth == ["Bearer super-secret", "Bearer super-secret"]
    assert all("/api/v1/" in url for url in seen_urls)


@pytest.mark.parametrize("envelope", [False, True])
def test_probe_accepts_bare_lists_and_documented_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    envelope: bool,
) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        del timeout
        if request.full_url.endswith("/api/v1/workspaces"):  # type: ignore[attr-defined]
            rows = [{"workspace_name": "s3bench", "project_count": 1}]
            return _Response({"workspaces": rows} if envelope else rows)
        rows = [
            {
                "workspace_name": "s3bench",
                "project_name": "s3-agent-memory-v1",
                "page_count": 12,
            }
        ]
        return _Response({"projects": rows} if envelope else rows)

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    result = AiMemoryClient(AiMemoryConfig()).probe(
        workspace="s3bench",
        project="s3-agent-memory-v1",
    )

    assert result["status"] == "PASS"
    assert result["scope"]["project_page_count"] == 12  # type: ignore[index]


@pytest.mark.parametrize("envelope", [False, True])
def test_search_count_accepts_bare_lists_and_documented_envelopes(
    monkeypatch: pytest.MonkeyPatch,
    envelope: bool,
) -> None:
    def fake_urlopen(request: object, *, timeout: float) -> _Response:
        del request, timeout
        rows = [{"snippet": "secret-memory-content"}, {"snippet": "other-content"}]
        return _Response({"hits": rows} if envelope else rows)

    monkeypatch.setattr(client_module, "urlopen", fake_urlopen)

    result = AiMemoryClient(AiMemoryConfig()).search_count(
        workspace="s3bench",
        project="s3-agent-memory-v1",
        query="memory",
    )

    assert result == 2
    assert "secret-memory-content" not in json.dumps(result)


@pytest.mark.parametrize(
    ("document", "envelope_key"),
    [
        (None, "workspaces"),
        ("text", "workspaces"),
        (42, "workspaces"),
        (True, "workspaces"),
        ({"projects": []}, "workspaces"),
        ({"workspaces": {}}, "workspaces"),
        (["invalid-row"], "workspaces"),
    ],
)
def test_extract_rows_rejects_malformed_shapes(
    document: object,
    envelope_key: str,
) -> None:
    with pytest.raises(AiMemoryProviderError, match="response|list|root"):
        client_module._extract_rows(document, envelope_key)


def test_get_json_rejects_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    class _MalformedResponse(_Response):
        def read(self) -> bytes:
            return b"{not-json"

    monkeypatch.setattr(client_module, "urlopen", lambda *_args, **_kwargs: _MalformedResponse({}))

    with pytest.raises(AiMemoryProviderError, match="invalid JSON"):
        AiMemoryClient(AiMemoryConfig())._get_json("/api/v1/workspaces")


def test_workstream_names_isolate_provider_arms() -> None:
    plain = workstream_name_from_plan(_plan("ai-memory"), "memory.cross-session.v1")
    gated = workstream_name_from_plan(
        _plan("ai-memory+s3-integrity-gate"),
        "memory.cross-session.v1",
    )

    assert plain == "s3-amv1-ai-memory-r2-cross-session"
    assert gated == "s3-amv1-ai-memory-s3-integrity-gate-r2-cross-session"
    assert plain != gated


def test_managed_command_uses_fresh_external_memory_handoff() -> None:
    launch = build_managed_run_command(
        executable="ai-memory",
        workspace="s3bench",
        project="s3-agent-memory-v1",
        workstream="s3-amv1-ai-memory-r1-cross-session",
        phase="resume",
        harness="codex",
        native_args=("--model", "fixture"),
    )

    assert launch.argv == (
        "ai-memory",
        "run",
        "--workspace",
        "s3bench",
        "--project",
        "s3-agent-memory-v1",
        "--workstream",
        "s3-amv1-ai-memory-r1-cross-session",
        "--fresh",
        "codex",
        "--model",
        "fixture",
    )


def test_execute_managed_run_is_shell_free_and_does_not_capture(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch = build_managed_run_command(
        executable="ai-memory",
        workspace="s3bench",
        project="s3-agent-memory-v1",
        workstream="s3-amv1-ai-memory-r1-host-shell-policy",
        phase="new",
        harness="codex",
    )
    observed: dict[str, object] = {}

    def fake_controlled(argv: list[str], **kwargs: object) -> object:
        observed["argv"] = argv
        observed.update(kwargs)
        return type("Result", (), {"returncode": 7})()

    monkeypatch.setattr("providers.ai_memory.runner.run_controlled_process", fake_controlled)

    assert execute_managed_run(launch, worktree=tmp_path) == 7
    assert observed["cwd"] == tmp_path
    assert "input_text" not in observed


def test_cli_blocks_linked_native_session_for_cross_session(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")

    with pytest.raises(SystemExit, match="require --fresh"):
        ai_memory_main(
            [
                "command",
                "--plan-file",
                str(plan_path),
                "--scenario",
                "memory.cross-session.v1",
                "--workspace",
                "s3bench",
                "--project",
                "s3-agent-memory-v1",
                "--phase",
                "resume",
                "--harness",
                "codex",
                "--allow-linked-session",
            ]
        )


def test_cli_run_requires_explicit_execute(tmp_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(_plan()), encoding="utf-8")

    with pytest.raises(SystemExit, match="explicit --execute"):
        ai_memory_main(
            [
                "run",
                "--plan-file",
                str(plan_path),
                "--scenario",
                "memory.host-shell-policy.v1",
                "--workspace",
                "s3bench",
                "--project",
                "s3-agent-memory-v1",
                "--phase",
                "new",
                "--harness",
                "codex",
                "--worktree",
                str(tmp_path),
            ]
        )
