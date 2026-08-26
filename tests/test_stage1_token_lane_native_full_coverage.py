from __future__ import annotations

from tools.qualify_stage1_token_lane_full_coverage import _parse_coverage


def test_parse_native_coverage_marker() -> None:
    stderr = (
        b"S3_STAGE1_AUDIT 1 2 3\n"
        b"S3_STAGE1_EMITTER_BLOCKED\n"
        b"S3_STAGE1_COVERAGE length=166984 touched=166984 first_unread=-1 max_read=166983\n"
    )
    assert _parse_coverage(stderr) == {
        "length": 166984,
        "touched": 166984,
        "first_unread": -1,
        "max_read": 166983,
    }


def test_parse_native_coverage_rejects_malformed_marker() -> None:
    assert _parse_coverage(b"S3_STAGE1_COVERAGE touched=10\n") is None


def test_incomplete_native_coverage_is_observable() -> None:
    coverage = _parse_coverage(
        b"S3_STAGE1_COVERAGE length=100 touched=75 first_unread=75 max_read=74\n"
    )
    assert coverage is not None
    assert coverage["touched"] != coverage["length"]
    assert coverage["first_unread"] == 75
    assert coverage["max_read"] != coverage["length"] - 1
