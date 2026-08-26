from __future__ import annotations

from pathlib import Path

from tools.qualify_stage2_stage3_strict_sandbox import ROOT, _is_forbidden_read, _quoted_open_path


def test_openat_parser_extracts_path() -> None:
    line = '123 openat(AT_FDCWD, "/etc/ld.so.cache", O_RDONLY|O_CLOEXEC) = 3'
    assert _quoted_open_path(line) == "/etc/ld.so.cache"


def test_system_loader_files_are_not_mistaken_for_bootstrap_delegation() -> None:
    assert _is_forbidden_read("/etc/ld.so.cache") is False
    assert _is_forbidden_read("/lib/x86_64-linux-gnu/libc.so.6") is False


def test_repository_and_python_reads_are_forbidden() -> None:
    root = str(ROOT.resolve()).replace("\\", "/")
    assert _is_forbidden_read(root + "/bootstrap/s3/pipeline.py") is True
    assert _is_forbidden_read("bootstrap/s3/pipeline.py") is True
    assert _is_forbidden_read("/tmp/copied-bootstrap/compiler.pyc") is True


def test_all_relative_file_reads_fail_closed() -> None:
    assert _is_forbidden_read("compiler-input.bin") is True
    assert _is_forbidden_read("../selfhost/compiler/s3c_stage1.s3") is True
    assert _is_forbidden_read("../../bootstrap/s3/pipeline.py") is True


def test_non_python_absolute_sandbox_temporary_file_is_not_intrinsically_forbidden() -> None:
    assert _is_forbidden_read("/tmp/compiler-input.bin") is False


def test_absolute_symlink_to_checkout_is_resolved_before_policy(tmp_path: Path) -> None:
    target = ROOT / "selfhost" / "compiler" / "compiler-sources.json"
    link = tmp_path / "compiler-manifest-link"
    link.symlink_to(target)
    assert _is_forbidden_read(str(link.resolve())) is True
