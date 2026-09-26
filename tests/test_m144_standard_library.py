from __future__ import annotations

import pytest

from bootstrap.s3.backends.x86_64.backend import X8664Backend
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.stdlib import (
    STANDARD_LIBRARY_VERSION,
    standard_library_manifest,
    standard_library_sources,
)


def _sources(
    main: str,
    modules: tuple[str, ...] | None = None,
) -> dict[str, str]:
    sources = standard_library_sources(modules=modules)
    sources["main.s3"] = main
    return sources


def test_manifest_is_versioned_sorted_and_capability_explicit() -> None:
    manifest = standard_library_manifest()
    assert STANDARD_LIBRARY_VERSION == "1"
    assert tuple(item.module_id for item in manifest) == tuple(
        sorted(item.module_id for item in manifest)
    )
    assert manifest[0].exports == (
        "new_map",
        "put_map",
        "get_map",
        "new_set",
        "add_set",
    )
    assert next(item for item in manifest if item.module_id == "s3.v1.host").capabilities == (
        "resource",
    )
    assert next(item for item in manifest if item.module_id == "s3.v1.io").capabilities == (
        "resource",
    )
    science_exports = set(
        next(item for item in manifest if item.module_id == "s3.v1.science").exports
    )
    assert {
        "sum_squares",
        "min",
        "max",
        "max_abs",
        "l1_norm",
        "mae",
        "mse",
        "rmse",
        "standard_deviation",
        "covariance",
        "correlation",
        "cosine_similarity",
    }.issubset(science_exports)
    geometry_exports = set(
        next(item for item in manifest if item.module_id == "s3.v1.geometry").exports
    )
    assert {
        "Vec2",
        "Vec3",
        "GeometryBounds3",
        "squared_distance_vec2",
        "distance_vec3",
        "triangle_normal",
        "point_cloud_bounds",
        "point_cloud_squared_radius_sum",
        "point_cloud_radius_of_gyration",
        "triangle_mesh_surface_area",
    }.issubset(geometry_exports)
    with pytest.raises(ValueError, match="unsupported"):
        standard_library_sources("2")


def test_text_and_collection_modules_cross_compile() -> None:
    source = """\
module main
from s3.v1.text import from_static
from s3.v1.text import length
from s3.v1.collections import new_map
from s3.v1.collections import put_map
from s3.v1.collections import get_map
fn main() -> i64:
    text_value: text = from_static("abc")
    mut values: i64_map = new_map(2)
    discard put_map(&mut values, 7, length(&text_value))
    return get_map(&values, 7)
"""
    compilation = compile_sources(
        _sources(source, ("s3.v1.text", "s3.v1.collections"))
    )
    assert execute_ir(compilation.ir) == 3


def test_host_and_io_wrappers_preserve_explicit_resource_capability() -> None:
    source = """\
module main
from s3.v1.host import grant
from s3.v1.host import open
from s3.v1.host import active
from s3.v1.io import kind
from s3.v1.io import close_resource
fn main() -> i64:
    capability: host_capability = grant(1)
    mut handle: resource_handle = open(capability)
    mut result: i64 = kind(&handle)
    one: i64 = 1
    zero: i64 = 0
    match active(&handle):
        -1:
            result = result + one
        0:
            result = result + zero
        1:
            result = result + zero
    discard close_resource(&mut handle)
    return result
"""
    compilation = compile_sources(_sources(source, ("s3.v1.host", "s3.v1.io")))
    assert execute_ir(compilation.ir) == 2


def test_standard_library_native_generation_has_no_hidden_host_symbols() -> None:
    source = """\
module main
from s3.v1.core import clamp_tryte
fn main() -> tryte:
    return clamp_tryte(8, 0, 4)
"""
    assembly = X8664Backend().generate(
        compile_sources(_sources(source, ("s3.v1.core",))).assembly
    )
    assert "s3.v1" not in assembly
    assert "call __s3_builtin_host_capability_grant" not in assembly
    assert "call __s3_builtin_resource_open" not in assembly
