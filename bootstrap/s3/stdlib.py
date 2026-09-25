"""Versioned, capability-declared source standard-library modules."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


STANDARD_LIBRARY_VERSION = "1"


@dataclass(frozen=True, slots=True)
class StandardLibraryModule:
    module_id: str
    version: str
    logical_path: str
    exports: tuple[str, ...]
    capabilities: tuple[str, ...]


_MODULES = (
    StandardLibraryModule(
        "s3.v1.collections",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/collections.s3",
        ("new_map", "put_map", "get_map", "new_set", "add_set"),
        (),
    ),
    StandardLibraryModule(
        "s3.v1.core",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/core.s3",
        ("clamp_tryte", "identity_i64"),
        (),
    ),
    StandardLibraryModule(
        "s3.v1.host",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/host.s3",
        ("grant", "open", "active", "invoke"),
        ("resource",),
    ),
    StandardLibraryModule(
        "s3.v1.io",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/io.s3",
        ("kind", "close_resource"),
        ("resource",),
    ),
    StandardLibraryModule(
        "s3.v1.science",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/science.s3",
        (
            "F64Result",
            "sum",
            "sum_squares",
            "sum_abs",
            "l1_norm",
            "min",
            "max",
            "max_abs",
            "dot",
            "mean",
            "variance",
            "squared_distance",
            "distance",
            "l2_norm",
            "rmsd",
            "sum_squared_difference",
            "mae",
            "mse",
            "rmse",
            "standard_deviation",
            "covariance",
            "correlation",
            "cosine_similarity",
        ),
        (),
    ),
    StandardLibraryModule(
        "s3.v1.text",
        STANDARD_LIBRARY_VERSION,
        "s3/v1/text.s3",
        ("from_static", "length"),
        (),
    ),
)


def standard_library_manifest(
    version: str = STANDARD_LIBRARY_VERSION,
) -> tuple[StandardLibraryModule, ...]:
    if version != STANDARD_LIBRARY_VERSION:
        raise ValueError(f"unsupported standard-library version: {version!r}")
    return _MODULES


def standard_library_sources(
    version: str = STANDARD_LIBRARY_VERSION,
    *,
    modules: Iterable[str] | None = None,
) -> dict[str, str]:
    manifest = standard_library_manifest(version)
    if modules is None:
        selected = manifest
    else:
        requested = tuple(modules)
        known = {module.module_id: module for module in manifest}
        unknown = sorted(set(requested) - set(known))
        if unknown:
            raise ValueError(f"unknown standard-library module: {unknown[0]!r}")
        selected = tuple(known[name] for name in requested)
    root = (
        Path(__file__).resolve().parents[2]
        / "stdlib"
        / "s3"
        / f"v{version}"
    )
    return {
        module.logical_path: (root / Path(module.logical_path).name).read_text(
            encoding="utf-8"
        )
        for module in selected
    }
