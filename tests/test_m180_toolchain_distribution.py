from __future__ import annotations

import zipfile
import io

import pytest

from bootstrap.s3.toolchain_distribution import DistributionError, ToolchainBundler


pytestmark = pytest.mark.s3_contract


def test_repeated_toolchain_builds_are_byte_identical() -> None:
    bundler = ToolchainBundler()
    first = bundler.build({"bin/s3": b"compiler", "README": b"stable"}, license_text="Apache-2.0", metadata={"version": "1.80", "target": "hosted"})
    second = bundler.build({"README": b"stable", "bin/s3": b"compiler"}, license_text="Apache-2.0", metadata={"target": "hosted", "version": "1.80"})
    assert first.data == second.data
    assert first.sha256 == second.sha256
    bundler.verify(first)


def test_manifest_checksums_and_license_are_present() -> None:
    bundle = ToolchainBundler().build({"src/main.s3": b"fn main()"}, license_text="Apache-2.0", metadata={"instruction_limit": "100000"})
    with zipfile.ZipFile(io.BytesIO(bundle.data)) as archive:
        assert set(("LICENSE", "MANIFEST.json", "src/main.s3")) <= set(archive.namelist())
        assert archive.read("LICENSE") == b"Apache-2.0"


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
    corrupted_bytes = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(bundle.data), "r") as source, zipfile.ZipFile(corrupted_bytes, "w") as target:
        for info in source.infolist():
            data = source.read(info.filename)
            if info.filename == "bin/s3":
                data = b"corrupted"
            target.writestr(info, data)
    corrupted = type(bundle)(corrupted_bytes.getvalue(), bundle.manifest)
    with pytest.raises(DistributionError):
        bundler.verify(corrupted)
    with pytest.raises(DistributionError, match="local-only"):
        bundler.publish(bundle)
