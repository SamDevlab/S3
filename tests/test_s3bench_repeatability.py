"""Contract tests for persisted s3bench repeatability analysis."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

pytestmark = pytest.mark.s3_benchmark

import benchmarks.s3bench.repeatability as repeatability
from benchmarks.s3bench.repeatability import (
    RepeatabilityError,
    analyze_root,
    publish_reports,
    render_analysis_markdown,
)
from tools.s3bench_analyze import main


def _row(*, benchmark="bench-a", implementation="s3", optimization="O0", scope="kernel", median_ns=100_000, loops=1_000, cv=0.01):
    return {
        "benchmark_id": benchmark,
        "input_id": "input-a",
        "measurement_scope": scope,
        "implementation": implementation,
        "execution_mode": "emulator" if implementation == "s3" else "interpreted",
        "optimization_mode": optimization,
        "phase": "end_to_end",
        "status": "measured",
        "correctness_status": "verified",
        "expected_checksum": "42",
        "observed_checksum": "42",
        "median_ns": median_ns,
        "loops_per_sample": loops,
        "coefficient_of_variation": cv,
        "extra_metadata": {"preserve": True},
    }


def _document(rows):
    comparisons = []
    for row in rows:
        comparison = {key: row[key] for key in (
            "benchmark_id", "input_id", "measurement_scope", "implementation",
            "execution_mode", "optimization_mode", "phase",
        )}
        comparison["median_ns_per_loop"] = row["median_ns"] / row["loops_per_sample"]
        comparisons.append(comparison)
    return {"schema_version": "1.0.0", "results": rows, "comparisons": comparisons}


def _write_fixture(tmp_path: Path, *, rows_by_run=None, runs=3, stdout=True, stderr="", benchmark_dir="bench-a", marker=None):
    root = tmp_path / "archive" / "benchmarks"
    rows_by_run = rows_by_run or [[_row(), _row(optimization="O1", median_ns=90_000, loops=1_000)] for _ in range(runs)]
    for index in range(runs):
        run = root / benchmark_dir / f"run-{index + 1}"
        run.mkdir(parents=True)
        document = _document(rows_by_run[index])
        encoded = json.dumps(document, indent=2, sort_keys=True) + "\n"
        (run / "results.json").write_text(encoded, encoding="utf-8")
        if stdout:
            (run / "results.stdout").write_text(encoded, encoding="utf-8")
        (run / "results.stderr").write_text(stderr, encoding="utf-8")
    if marker is not None:
        (root / benchmark_dir / "benchmark-id.txt").write_text(marker, encoding="utf-8")
    return root.parent


def _fail_markdown_publication_and_restores(
    monkeypatch,
    json_path: Path,
    markdown_path: Path,
    failed_restorations: set[Path],
):
    original_replace = os.replace
    publication_failed = False
    restoration_attempts = []

    def replace(source, destination):
        nonlocal publication_failed
        source = Path(source)
        destination = Path(destination)
        is_restoration = (
            publication_failed
            and ".backup." in source.name
            and destination in {json_path, markdown_path}
        )
        if is_restoration:
            restoration_attempts.append(destination)
            if destination in failed_restorations:
                raise OSError(f"simulated restoration failure for {destination.name}")
        is_markdown_publication = (
            destination == markdown_path
            and source != markdown_path
            and ".backup." not in source.name
        )
        if is_markdown_publication and not publication_failed:
            publication_failed = True
            raise OSError("simulated markdown publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(repeatability.os, "replace", replace)
    return restoration_attempts


def test_kernel_uses_per_loop_not_raw_median(tmp_path):
    report = analyze_root(_write_fixture(tmp_path))
    o0 = next(item for item in report["measurements"] if item["optimization_mode"] == "O0")
    assert o0["median_ns_per_loop"] == 100
    assert o0["median_ns_per_loop"] != 100_000


def test_o0_o1_different_loops_produce_correct_ratio(tmp_path):
    report = analyze_root(_write_fixture(tmp_path))
    comparison = report["comparisons"][0]
    assert comparison["ratio"] == pytest.approx(0.9)


def test_regression_fixture_is_ten_percent_faster_per_loop(tmp_path):
    rows = [[_row(median_ns=100_000), _row(optimization="O1", median_ns=180_000, loops=2_000)] for _ in range(3)]
    report = analyze_root(_write_fixture(tmp_path, rows_by_run=rows))
    comparison = report["comparisons"][0]
    assert comparison["change_percent"] == pytest.approx(-10)
    assert comparison["classification"] == "CONCLUSIVE"


def test_kernel_per_loop_divergence_fails(tmp_path):
    root = _write_fixture(tmp_path)
    path = next(root.glob("benchmarks/bench-a/run-1/results.json"))
    document = json.loads(path.read_text())
    document["comparisons"][0]["median_ns_per_loop"] = 999
    path.write_text(json.dumps(document, sort_keys=True), encoding="utf-8")
    (path.parent / "results.stdout").write_text(path.read_text(), encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="per-loop mismatch"):
        analyze_root(root)


def test_process_requires_one_loop(tmp_path):
    rows = [[_row(scope="process", median_ns=100, loops=2)] for _ in range(3)]
    with pytest.raises(RepeatabilityError, match="process loops"):
        analyze_root(_write_fixture(tmp_path, rows_by_run=rows))


def test_process_one_loop_is_accepted(tmp_path):
    rows = [[_row(scope="process", median_ns=100, loops=1)] for _ in range(3)]
    report = analyze_root(_write_fixture(tmp_path, rows_by_run=rows))
    assert report["measurements"][0]["median_ns_per_loop"] == 100


def test_kernel_and_process_are_not_compared(tmp_path):
    rows = [[_row(scope="kernel"), _row(scope="process", median_ns=100, loops=1)] for _ in range(3)]
    report = analyze_root(_write_fixture(tmp_path, rows_by_run=rows))
    assert report["comparisons"] == []


def test_duplicate_keys_fail(tmp_path):
    root = _write_fixture(tmp_path)
    path = root / "benchmarks" / "bench-a" / "run-1" / "results.json"
    document = json.loads(path.read_text())
    document["results"].append(document["results"][0])
    document["comparisons"].append(document["comparisons"][0])
    encoded = json.dumps(document, sort_keys=True)
    path.write_text(encoded, encoding="utf-8")
    path.with_name("results.stdout").write_text(encoded, encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="duplicate result"):
        analyze_root(root)


def test_result_without_comparison_fails(tmp_path):
    root = _write_fixture(tmp_path)
    path = root / "benchmarks" / "bench-a" / "run-1" / "results.json"
    document = json.loads(path.read_text())
    document["comparisons"].pop()
    encoded = json.dumps(document, sort_keys=True)
    path.write_text(encoded, encoding="utf-8")
    path.with_name("results.stdout").write_text(encoded, encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="mismatch"):
        analyze_root(root)


def test_comparison_without_result_fails(tmp_path):
    root = _write_fixture(tmp_path)
    path = root / "benchmarks" / "bench-a" / "run-1" / "results.json"
    document = json.loads(path.read_text())
    document["comparisons"].append({**document["comparisons"][0], "optimization_mode": "O2"})
    encoded = json.dumps(document, sort_keys=True)
    path.write_text(encoded, encoding="utf-8")
    path.with_name("results.stdout").write_text(encoded, encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="mismatch"):
        analyze_root(root)


def test_incomplete_runs_fail(tmp_path):
    with pytest.raises(RepeatabilityError, match="invalid run layout"):
        analyze_root(_write_fixture(tmp_path, runs=2))


def test_missing_run_number_fails_closed(tmp_path):
    root = _write_fixture(tmp_path)
    benchmark = root / "benchmarks" / "bench-a"
    (benchmark / "run-3").rename(benchmark / "run-4")
    with pytest.raises(RepeatabilityError, match="invalid run layout"):
        analyze_root(root)


def test_checksum_divergence_fails(tmp_path):
    rows = [[_row()] for _ in range(3)]
    rows[1][0]["observed_checksum"] = "different"
    with pytest.raises(RepeatabilityError, match="checksum"):
        analyze_root(_write_fixture(tmp_path, rows_by_run=rows))


def test_json_different_from_stdout_fails(tmp_path):
    root = _write_fixture(tmp_path)
    stdout = root / "benchmarks" / "bench-a" / "run-1" / "results.stdout"
    stdout.write_text("{}", encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="differs from stdout"):
        analyze_root(root)


def test_nonempty_stderr_fails(tmp_path):
    with pytest.raises(RepeatabilityError, match="stderr"):
        analyze_root(_write_fixture(tmp_path, stderr="unexpected\n"))


def test_shuffled_input_is_deterministic(tmp_path):
    first = analyze_root(_write_fixture(tmp_path / "a"))
    rows = [[_row(optimization="O1", median_ns=90_000, loops=1_000), _row()]] * 3
    second = analyze_root(_write_fixture(tmp_path / "b", rows_by_run=rows))
    assert first == second


def test_stable_usable_and_unstable_limits(tmp_path):
    root = tmp_path / "archive" / "benchmarks"
    values = {"bench-a": [100, 105, 95], "bench-b": [100, 110, 90], "bench-c": [100, 130, 70]}
    for benchmark, per_loop_values in values.items():
        for index, per_loop in enumerate(per_loop_values, 1):
            run = root / benchmark / f"run-{index}"
            run.mkdir(parents=True)
            row = _row(benchmark=benchmark, median_ns=per_loop * 1000)
            encoded = json.dumps(_document([row]), sort_keys=True)
            (run / "results.json").write_text(encoded, encoding="utf-8")
            (run / "results.stdout").write_text(encoded, encoding="utf-8")
            (run / "results.stderr").write_text("", encoding="utf-8")
    report = analyze_root(root.parent)
    assert [item["classification"] for item in report["measurements"]] == ["STABLE", "USABLE", "UNSTABLE"]


def test_conclusive_requires_change_above_noise(tmp_path):
    rows = [
        [_row(median_ns=per_loop * 1_000), _row(optimization="O1", median_ns=105_000)]
        for per_loop in (100, 110, 90)
    ]
    report = analyze_root(_write_fixture(tmp_path, rows_by_run=rows))
    assert report["comparisons"][0]["classification"] == "INCONCLUSIVE"


def test_markdown_separates_kernel_and_process(tmp_path):
    rows = [[_row(), _row(scope="process", median_ns=100, loops=1)] for _ in range(3)]
    markdown = render_analysis_markdown(analyze_root(_write_fixture(tmp_path, rows_by_run=rows)))
    assert "## Kernel" in markdown and "## Process" in markdown
    assert "Different measurement scopes must never be compared directly." in markdown


def test_unknown_scope_fails(tmp_path):
    rows = [[_row(scope="mystery")] for _ in range(3)]
    with pytest.raises(RepeatabilityError, match="unknown measurement_scope"):
        analyze_root(_write_fixture(tmp_path, rows_by_run=rows))


def test_unexpected_benchmark_directory_fails(tmp_path):
    root = _write_fixture(tmp_path)
    unexpected = root / "benchmarks" / "unexpected" / "run-1"
    unexpected.mkdir(parents=True)
    with pytest.raises(RepeatabilityError, match="invalid run layout"):
        analyze_root(root)


def test_cli_writes_json_and_markdown(tmp_path):
    root = _write_fixture(tmp_path)
    output_json = tmp_path / "report.json"
    output_markdown = tmp_path / "report.md"
    assert main([str(root), "--output-json", str(output_json), "--output-markdown", str(output_markdown)]) == 0
    assert json.loads(output_json.read_text(encoding="utf-8"))["summary"]["runs"] == 3
    assert "# s3bench Repeatability Analysis" in output_markdown.read_text(encoding="utf-8")


def test_cli_returns_nonzero_for_invalid_input(tmp_path):
    output_json = tmp_path / "report.json"
    output_markdown = tmp_path / "report.md"
    assert main([str(tmp_path / "missing"), "--output-json", str(output_json), "--output-markdown", str(output_markdown)]) != 0


def test_safe_directory_with_valid_marker_uses_marker_identity(tmp_path):
    report = analyze_root(_write_fixture(tmp_path, benchmark_dir="safe-storage-name", marker="bench-a\n"))
    assert report["measurements"][0]["benchmark_id"] == "bench-a"


def test_safe_directory_without_marker_accepts_consistent_documents(tmp_path):
    report = analyze_root(_write_fixture(tmp_path, benchmark_dir="safe-storage-name"))
    assert report["summary"]["benchmarks"] == 1


def test_divergent_marker_fails(tmp_path):
    with pytest.raises(RepeatabilityError, match="benchmark-id.txt disagrees"):
        analyze_root(_write_fixture(tmp_path, benchmark_dir="safe-storage-name", marker="other-benchmark"))


def test_ids_diverging_between_runs_fail(tmp_path):
    rows = [[_row()] for _ in range(3)]
    rows[1] = [_row(benchmark="other-benchmark")]
    with pytest.raises(RepeatabilityError, match="benchmark IDs differ"):
        analyze_root(_write_fixture(tmp_path, rows_by_run=rows, benchmark_dir="safe-storage-name"))


def test_duplicate_benchmark_identity_across_storage_directories_fails(tmp_path):
    root = _write_fixture(tmp_path, benchmark_dir="first-storage")
    second = _write_fixture(tmp_path / "second", benchmark_dir="second-storage")
    second_benchmarks = second / "benchmarks" / "second-storage"
    destination = root / "benchmarks" / "second-storage"
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination_dir = destination
    for source in second_benchmarks.iterdir():
        if source.is_dir():
            target = destination_dir / source.name
            target.mkdir(parents=True)
            for document in source.iterdir():
                target.joinpath(document.name).write_bytes(document.read_bytes())
        else:
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination_dir.joinpath(source.name).write_bytes(source.read_bytes())
    with pytest.raises(RepeatabilityError, match="duplicate benchmark_id"):
        analyze_root(root)


def test_result_and_comparison_ids_differ_fail(tmp_path):
    root = _write_fixture(tmp_path, benchmark_dir="safe-storage-name")
    path = root / "benchmarks" / "safe-storage-name" / "run-1" / "results.json"
    document = json.loads(path.read_text())
    document["comparisons"][0]["benchmark_id"] = "other-benchmark"
    encoded = json.dumps(document, sort_keys=True)
    path.write_text(encoded, encoding="utf-8")
    path.with_name("results.stdout").write_text(encoded, encoding="utf-8")
    with pytest.raises(RepeatabilityError, match="benchmark IDs disagree"):
        analyze_root(root)


def test_cli_rejects_identical_output_paths_without_writing(tmp_path):
    root = _write_fixture(tmp_path)
    destination = tmp_path / "same-report"
    assert main([
        str(root), "--output-json", str(destination), "--output-markdown", str(destination),
    ]) != 0
    assert not destination.exists()


def test_equivalent_output_paths_are_rejected(tmp_path):
    root = _write_fixture(tmp_path)
    del root
    json_path = tmp_path / "reports" / ".." / "same-report"
    markdown_path = tmp_path / "same-report"
    with pytest.raises(RepeatabilityError, match="same destination"):
        publish_reports("{}\n", "# report\n", json_path, markdown_path)
    assert not markdown_path.exists()


def test_second_temporary_write_failure_leaves_no_outputs_or_temporaries(tmp_path, monkeypatch):
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    original = repeatability._write_temporary

    def fail_markdown(destination, content, suffix):
        if suffix == ".md":
            raise OSError("simulated markdown temporary failure")
        return original(destination, content, suffix)

    monkeypatch.setattr(repeatability, "_write_temporary", fail_markdown)
    with pytest.raises(RepeatabilityError, match="could not publish both reports"):
        publish_reports("{}\n", "# report\n", json_path, markdown_path)
    assert not json_path.exists()
    assert not markdown_path.exists()
    assert list(tmp_path.glob(".*")) == []


def test_second_publication_failure_rolls_back_existing_destinations(tmp_path, monkeypatch, capsys):
    root = _write_fixture(tmp_path)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_text("old-json\n", encoding="utf-8")
    markdown_path.write_text("old-markdown\n", encoding="utf-8")
    original_replace = os.replace
    failed = False

    def fail_second_destination(source, destination):
        nonlocal failed
        if Path(destination) == markdown_path and not failed:
            failed = True
            raise OSError("simulated second publication failure")
        return original_replace(source, destination)

    monkeypatch.setattr(repeatability.os, "replace", fail_second_destination)
    assert main([
        str(root), "--output-json", str(json_path), "--output-markdown", str(markdown_path),
    ]) == 2
    assert json_path.read_text(encoding="utf-8") == "old-json\n"
    assert markdown_path.read_text(encoding="utf-8") == "old-markdown\n"
    assert list(tmp_path.glob(".*")) == []
    stderr = capsys.readouterr().err
    assert "could not publish both reports" in stderr
    assert "rollback restoration failed" not in stderr
    assert "original preserved at" not in stderr


def test_cli_preserves_first_backup_when_first_restoration_fails(tmp_path, monkeypatch, capsys):
    root = _write_fixture(tmp_path)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_bytes(b"old-json\n")
    markdown_path.write_bytes(b"old-markdown\n")
    restoration_attempts = _fail_markdown_publication_and_restores(
        monkeypatch, json_path, markdown_path, {json_path}
    )

    assert main([
        str(root), "--output-json", str(json_path), "--output-markdown", str(markdown_path),
    ]) == 2

    backups = list(tmp_path.glob(".report.json.backup.*"))
    assert restoration_attempts == [json_path, markdown_path]
    assert len(backups) == 1
    assert backups[0].read_bytes() == b"old-json\n"
    assert not json_path.exists()
    assert markdown_path.read_bytes() == b"old-markdown\n"
    stderr = capsys.readouterr().err
    assert "simulated markdown publication failure" in stderr
    assert f"destination {repeatability._canonical_output_path(json_path)}" in stderr
    assert f"original preserved at {repeatability._canonical_output_path(backups[0])}" in stderr
    assert "simulated restoration failure for report.json" in stderr


def test_only_second_failed_restoration_backup_is_reported(tmp_path, monkeypatch):
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_bytes(b"old-json\n")
    markdown_path.write_bytes(b"old-markdown\n")
    restoration_attempts = _fail_markdown_publication_and_restores(
        monkeypatch, json_path, markdown_path, {markdown_path}
    )

    with pytest.raises(RepeatabilityError) as raised:
        publish_reports("new-json\n", "new-markdown\n", json_path, markdown_path)

    json_backups = list(tmp_path.glob(".report.json.backup.*"))
    markdown_backups = list(tmp_path.glob(".report.md.backup.*"))
    assert restoration_attempts == [json_path, markdown_path]
    assert json_path.read_bytes() == b"old-json\n"
    assert not markdown_path.exists()
    assert json_backups == []
    assert len(markdown_backups) == 1
    assert markdown_backups[0].read_bytes() == b"old-markdown\n"
    message = str(raised.value)
    assert f"destination {repeatability._canonical_output_path(markdown_path)}" in message
    assert (
        f"original preserved at {repeatability._canonical_output_path(markdown_backups[0])}"
        in message
    )
    assert ".report.json.backup." not in message


def test_rollback_continues_after_one_restoration_failure(tmp_path, monkeypatch):
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_bytes(b"old-json\n")
    markdown_path.write_bytes(b"old-markdown\n")
    restoration_attempts = _fail_markdown_publication_and_restores(
        monkeypatch, json_path, markdown_path, {json_path}
    )

    with pytest.raises(RepeatabilityError):
        publish_reports("new-json\n", "new-markdown\n", json_path, markdown_path)

    json_backups = list(tmp_path.glob(".report.json.backup.*"))
    assert restoration_attempts == [json_path, markdown_path]
    assert len(json_backups) == 1
    assert json_backups[0].read_bytes() == b"old-json\n"
    assert markdown_path.read_bytes() == b"old-markdown\n"
    assert list(tmp_path.glob(".report.md.backup.*")) == []


def test_first_backup_failure_cleans_placeholder_and_returns_cli_error(tmp_path, monkeypatch, capsys):
    root = _write_fixture(tmp_path)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_text("old-json\n", encoding="utf-8")
    original_replace = os.replace

    def fail_first_backup(source, destination):
        if Path(source) == json_path and ".backup." in Path(destination).name:
            raise OSError("simulated first backup failure")
        return original_replace(source, destination)

    monkeypatch.setattr(repeatability.os, "replace", fail_first_backup)
    assert main([
        str(root), "--output-json", str(json_path), "--output-markdown", str(markdown_path),
    ]) == 2
    assert json_path.read_text(encoding="utf-8") == "old-json\n"
    assert not markdown_path.exists()
    assert list(tmp_path.glob(".*")) == []
    assert "could not publish both reports" in capsys.readouterr().err


def test_second_backup_failure_restores_first_backup_and_cleans_all(tmp_path, monkeypatch):
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_text("old-json\n", encoding="utf-8")
    markdown_path.write_text("old-markdown\n", encoding="utf-8")
    original_replace = os.replace

    def fail_second_backup(source, destination):
        if Path(source) == markdown_path and ".backup." in Path(destination).name:
            raise OSError("simulated second backup failure")
        return original_replace(source, destination)

    monkeypatch.setattr(repeatability.os, "replace", fail_second_backup)
    with pytest.raises(RepeatabilityError, match="could not publish both reports"):
        publish_reports("new-json\n", "new-markdown\n", json_path, markdown_path)
    assert json_path.read_text(encoding="utf-8") == "old-json\n"
    assert markdown_path.read_text(encoding="utf-8") == "old-markdown\n"
    assert list(tmp_path.glob(".*")) == []


def test_post_commit_cleanup_failure_keeps_reports_and_returns_warning(tmp_path, monkeypatch, capsys):
    root = _write_fixture(tmp_path)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    json_path.write_text("old-json\n", encoding="utf-8")
    markdown_path.write_text("old-markdown\n", encoding="utf-8")
    original_unlink = Path.unlink

    def fail_backup_cleanup(path, missing_ok=False):
        if ".backup." in path.name:
            raise OSError("persistent cleanup failure")
        return original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_backup_cleanup)
    assert main([
        str(root), "--output-json", str(json_path), "--output-markdown", str(markdown_path),
    ]) == 0
    assert json_path.read_text(encoding="utf-8") != "old-json\n"
    assert markdown_path.read_text(encoding="utf-8") != "old-markdown\n"
    assert "could not remove backup:" in capsys.readouterr().err


def test_transient_post_commit_cleanup_is_retried(tmp_path, monkeypatch, capsys):
    root = _write_fixture(tmp_path)
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    original_unlink = Path.unlink
    failures = 0

    def fail_once(path, missing_ok=False):
        nonlocal failures
        if ".backup." in path.name and failures == 0:
            failures += 1
            raise OSError("transient cleanup failure")
        return original_unlink(path, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_once)
    assert main([
        str(root), "--output-json", str(json_path), "--output-markdown", str(markdown_path),
    ]) == 0
    assert list(tmp_path.glob(".*")) == []
    assert "warning" not in capsys.readouterr().err


def test_success_publishes_both_reports(tmp_path):
    json_path = tmp_path / "report.json"
    markdown_path = tmp_path / "report.md"
    publish_reports("{}\n", "# report\n", json_path, markdown_path)
    assert json_path.read_text(encoding="utf-8") == "{}\n"
    assert markdown_path.read_text(encoding="utf-8") == "# report\n"
    assert list(tmp_path.glob(".*")) == []
