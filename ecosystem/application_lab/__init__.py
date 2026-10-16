"""Offline discovery and validation for real S3 application projects."""

from .lab import PINNED_COMPILER_REVISION, discover_applications, run_application

__all__ = ["PINNED_COMPILER_REVISION", "discover_applications", "run_application"]
