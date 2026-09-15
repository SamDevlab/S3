from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from tools import reliability_campaign_v2 as cli


pytestmark = [pytest.mark.s3_contract, pytest.mark.s3_differential]
ROOT = Path(__file__).resolve().parent.parent
HEAD = "a" * 40


def _report() -> dict[str, object]:
    return {
        "schema": "s3.reliability.differential-campaign.v1",
        "campaign_id": "campaign",
        "campaign_seed": 1,
        "compiler_head": HEAD,
        "case_count": 4,
        "native_case_count": 0,
        "confirmation_runs_per_path": 2,
        "counts": {"PASS": 4},
        "results": [],
    }


def test_r3_campaign_direct_script_entry_point_imports_tools_package() -> None:
    completed = subprocess.run(
        [sys.executable, "tools/reliability_campaign_v2.py", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Run a bounded deterministic S3 Reliability Lab v2 R3 campaign" in (
        completed.stdout
    )
    assert "ModuleNotFoundError" not in completed.stderr


def test_r3_campaign_module_entry_point_imports_tools_package() -> None:
    completed = subprocess.run(
        [sys.executable, "-m", "tools.reliability_campaign_v2", "--help"],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    assert "Run a bounded deterministic S3 Reliability Lab v2 R3 campaign" in (
        completed.stdout
    )


def test_r3_campaign_cli_fails_closed_on_head_mismatch(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setattr(cli, "_current_head", lambda: HEAD)
    code = cli.main(
        [
            "--id",
            "campaign",
            "--seed",
            "1",
            "--cases",
            "4",
            "--report",
            str(tmp_path / "report.json"),
            "--replay-root",
            str(tmp_path / "replays"),
            "--expect-head",
            "b" * 40,
        ]
    )
    assert code == 2
    assert not (tmp_path / "report.json").exists()


def test_r3_campaign_cli_writes_report_and_returns_zero_for_all_pass(
    monkeypatch, tmp_path: Path, capsysbinary
) -> None:
    monkeypatch.setattr(cli, "_current_head", lambda: HEAD)
    observed: dict[str, object] = {}

    def fake_run(campaign_id, campaign_seed, head, **kwargs):
        observed.update(
            campaign_id=campaign_id,
            campaign_seed=campaign_seed,
            head=head,
            **kwargs,
        )
        return _report()

    def fake_write(path, report):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, sort_keys=True) + "\n", encoding="utf-8")

    monkeypatch.setattr(cli, "run_campaign", fake_run)
    monkeypatch.setattr(cli, "write_campaign_report", fake_write)
    report_path = tmp_path / "report.json"
    replay_root = tmp_path / "replays"

    code = cli.main(
        [
            "--id",
            "campaign",
            "--seed",
            "1",
            "--cases",
            "4",
            "--report",
            str(report_path),
            "--replay-root",
            str(replay_root),
            "--expect-head",
            HEAD,
        ]
    )

    assert code == 0
    assert report_path.is_file()
    assert observed["head"] == HEAD
    assert observed["case_count"] == 4
    assert observed["native_case_count"] == 0
    summary = json.loads(capsysbinary.readouterr().out.decode("utf-8"))
    assert summary["counts"] == {"PASS": 4}
    assert summary["compiler_head"] == HEAD


def test_r3_campaign_cli_returns_one_when_campaign_has_failure(
    monkeypatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(cli, "_current_head", lambda: HEAD)
    failed = _report()
    failed["counts"] = {"MISCOMPILE": 1, "PASS": 3}
    monkeypatch.setattr(cli, "run_campaign", lambda *args, **kwargs: failed)
    monkeypatch.setattr(
        cli,
        "write_campaign_report",
        lambda path, report: path.write_text("{}\n", encoding="utf-8"),
    )

    code = cli.main(
        [
            "--id",
            "campaign",
            "--seed",
            "1",
            "--cases",
            "4",
            "--report",
            str(tmp_path / "report.json"),
            "--replay-root",
            str(tmp_path / "replays"),
        ]
    )
    assert code == 1
