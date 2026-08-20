from __future__ import annotations

import io
import warnings
import zipfile

import pytest

from bootstrap.s3.toolchain_distribution import DistributionError, ToolchainBundler


pytestmark = pytest.mark.s3_contract


def _rewrite_bundle(bundle, *, replace: dict[str, bytes] | None = None, extras: tuple[tuple[str, bytes], ...] = ()):
    replace = replace or {}
    output = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(bundle.data), "r") as source, zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
        for info in source.infolist():
            target.writestr(info, replace.get(info.filename, source.read(info.filename)))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            for name, data in extras:
                target.writestr(name, data)
    return type(bundle)(output.getvalue(), bundle.manifest)


def test_repeated_toolchain_builds_are_byte_identical() -> None:
    bundler = ToolchainBundler()
    first = bundler.build({"bin/s3": b"compiler", "README": b"stable"}, license_text="Apache-2.0", metadata={"version": "1.80", "target": "hosted"})
    second = bundler.build({"README": b"stable", "bin/s3": b"compiler"}, license_text="Apache-2.0", metadata={"target": "hosted", "version": "1.80"})
    assert first.data == second.data
    assert first.sha256 == second.sha256
    bundler.verify(first)


def test_manifest_checksums_and_license_are_present_and_bound() -> None:
    bundle = ToolchainBundler().build({"src/main.s3": b"fn main()"}, license_text="Apache-2.0", metadata={"instruction_limit": "100000"})
    with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
        assert set(("LICENSE", "MANIFEST.json", "src/main.s3")) == set(archive.namelist())
        assert archive.read("LICENSE") == b"Apache-2.0"
    assert bundle.manifest["license"] == "LICENSE"
    assert bundle.manifest["license_size"] == len(b"Apache-2.0")
    assert len(bundle.manifest["license_sha256"]) == 64


def test_machine_paths_and_reserved_files_are_rejected() -> None:
    bundler = ToolchainBundler()
    with pytest.raises(DistributionError, match="rejected"):
        bundler.build({"C:\\Users\\samue\\secret": b"x"}, license_text="Apache", metadata={})
    with pytest.raises(DistributionError, match="rejected"):
        bundler.build({"../escape": b"x"}, license_text="Apache", metadata={})
    with pytest.raises(DistributionError, match="reserved"):
        bundler.build({"LICENSE": b"override"}, license_text="Apache", metadata={})


def test_corrupted_bundle_and_remote_release_are_rejected() -> None:
    bundler = ToolchainBundler()
    bundle = bundler.build({"bin/s3": b"compiler"}, license_text="Apache", metadata={})
    corrupted = _rewrite_bundle(bundle, replace={"bin/s3": b"corrupted"})
    with pytest.raises(DistributionError):
        bundler.verify(corrupted)
    with pytest.raises(DistributionError, match="local-only"):
        bundler.publish(bundle)


def test_unmanifested_extra_and_duplicate_zip_members_are_rejected() -> None:
    bundler = ToolchainBundler()
    bundle = bundler.build({"bin/s3": b"compiler"}, license_text="Apache", metadata={})
    extra = _rewrite_bundle(bundle, extras=(("malicious-extra.bin", b"payload"),))
    with pytest.raises(DistributionError, match="membership differs"):
        bundler.verify(extra)

    duplicate = _rewrite_bundle(bundle, extras=(("bin/s3", b"second-copy"),))
    with pytest.raises(DistributionError, match="duplicate member"):
        bundler.verify(duplicate)


def test_noncanonical_archive_paths_and_manifest_divergence_are_rejected() -> None:
    bundler = ToolchainBundler()
    bundle = bundler.build({"dir/file": b"ok"}, license_text="Apache", metadata={})
    noncanonical = _rewrite_bundle(bundle, extras=(("dir\\other", b"x"),))
    with pytest.raises(DistributionError, match="not canonical"):
        bundler.verify(noncanonical)

    tampered_manifest = dict(bundle.manifest)
    tampered_manifest["metadata"] = {"tampered": "yes"}
    with pytest.raises(DistributionError, match="differs from bundle manifest"):
        bundler.verify(type(bundle)(bundle.data, tampered_manifest))


def test_license_tampering_and_uncompressed_budget_are_rejected() -> None:
    bundler = ToolchainBundler()
    bundle = bundler.build({"bin/s3": b"compiler"}, license_text="Apache", metadata={})
    tampered_license = _rewrite_bundle(bundle, replace={"LICENSE": b"different-license"})
    with pytest.raises(DistributionError, match="LICENSE does not match"):
        bundler.verify(tampered_license)

    bounded = ToolchainBundler(max_files=4, max_bundle_bytes=4096)
    small = bounded.build({"bin/s3": b"x"}, license_text="Apache", metadata={})
    bomb = _rewrite_bundle(small, extras=(("oversized.bin", b"x" * 3500),))
    with pytest.raises(DistributionError, match="configured size|uncompressed content"):
        bounded.verify(bomb)
