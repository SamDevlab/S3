from __future__ import annotations

import pytest

from bootstrap.s3.build_profiles import BuildProfile, BuildProfileError, PGOProfileIdentity, ProfileProvenance


def test_development_and_release_profiles_are_explicit() -> None:
    development = BuildProfile.resolve("development", "linux-x86_64")
    release = BuildProfile.resolve("release", "linux-x86_64")
    assert development.optimization == "O0"
    assert development.debug_info is True
    assert release.optimization == "O1"
    assert release.debug_info is False
    assert development.payload != release.payload


def test_pgo_identity_requires_matching_provenance() -> None:
    profile = BuildProfile.resolve("release", "linux-x86_64")
    provenance = ProfileProvenance(profile, "compiler", "source", "linux-x86_64")
    evidence = PGOProfileIdentity.create(source_identity="source", compiler_sha="compiler", target="linux-x86_64", workload_identity="workload", profile_data=b"profile")
    assert evidence.matches(provenance, "workload")
    assert not evidence.matches(provenance, "other-workload")
    assert "profile_digest" in evidence.text


def test_profiles_fail_closed_on_unknown_or_mismatched_inputs() -> None:
    with pytest.raises(BuildProfileError, match="unknown"):
        BuildProfile.resolve("fast", "linux-x86_64")
    with pytest.raises(BuildProfileError, match="mismatch"):
        ProfileProvenance(BuildProfile.resolve("release", "linux-x86_64"), "compiler", "source", "windows")
