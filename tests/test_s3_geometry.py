from __future__ import annotations

import platform

import pytest

from bootstrap.s3.backends.x86_64 import NativeToolchain, generate_native_assembly
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.pipeline import compile_sources
from bootstrap.s3.ir_emulator import execute_ir
from bootstrap.s3.stdlib import standard_library_sources


def _run(source: str, optimization: OptimizationLevel) -> int:
    modules = standard_library_sources(modules=("s3.v1.geometry",))
    modules["main.s3"] = "module main\n" + source
    return execute_ir(
        compile_sources(modules, optimization=optimization, mode=SyntaxMode.V0_6).ir
    )


_MISMATCH = (
    "fn mismatch(value: trit) -> i64:\n"
    "    match value:\n"
    "        -1:\n"
    "            return 0\n"
    "        0:\n"
    "            return 1\n"
    "        1:\n"
    "            return 1\n"
)


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_vec2_vec3_operations_and_zero_normalization_are_structured(optimization) -> None:
    source = (
        "from s3.v1.geometry import Vec2\n"
        "from s3.v1.geometry import Vec3\n"
        "from s3.v1.geometry import GeometryVec2Result\n"
        "from s3.v1.geometry import GeometryVec3Result\n"
        "from s3.v1.geometry import squared_distance_vec2\n"
        "from s3.v1.geometry import distance_vec3\n"
        "from s3.v1.geometry import normalize_vec2\n"
        "from s3.v1.geometry import normalize_vec3\n"
        "from s3.v1.geometry import dot_vec2\n"
        "from s3.v1.geometry import dot_vec3\n"
        "from s3.v1.geometry import cross_vec3\n"
        "from s3.v1.geometry import triangle_area\n"
        "from s3.v1.geometry import triangle_normal\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + "    a: Vec3 = Vec3(x=1.0, y=2.0, z=3.0)\n"
        + "    b: Vec3 = Vec3(x=4.0, y=5.0, z=6.0)\n"
        + "    zero3: Vec3 = Vec3(x=0.0, y=0.0, z=0.0)\n"
        + "    n3: GeometryVec3Result = normalize_vec3(a)\n"
        + "    z3: GeometryVec3Result = normalize_vec3(zero3)\n"
        + "    cross: Vec3 = cross_vec3(a, b)\n"
        + "    mut failures: i64 = mismatch(dot_vec3(a, b) == 32.0)\n"
        + "    failures = failures + mismatch(cross.x == -3.0)\n"
        + "    failures = failures + mismatch(cross.y == 6.0)\n"
        + "    failures = failures + mismatch(cross.z == -3.0)\n"
        + "    failures = failures + mismatch(n3.status == 0)\n"
        + "    failures = failures + mismatch(z3.status == 1)\n"
        + "    failures = failures + mismatch(z3.value.x == 0.0)\n"
        + "    failures = failures + mismatch(triangle_area(zero3, Vec3(x=1.0, y=0.0, z=0.0), Vec3(x=0.0, y=1.0, z=0.0)) == 0.5)\n"
        + "    normal: GeometryVec3Result = triangle_normal(zero3, Vec3(x=1.0, y=0.0, z=0.0), Vec3(x=0.0, y=1.0, z=0.0))\n"
        + "    degenerate_normal: GeometryVec3Result = triangle_normal(zero3, Vec3(x=1.0, y=0.0, z=0.0), Vec3(x=2.0, y=0.0, z=0.0))\n"
        + "    failures = failures + mismatch(normal.status == 0)\n"
        + "    failures = failures + mismatch(normal.value.z == 1.0)\n"
        + "    failures = failures + mismatch(degenerate_normal.status == 1)\n"
        + "    failures = failures + mismatch(distance_vec3(a, b) > 5.0)\n"
        + "    v2: Vec2 = Vec2(x=3.0, y=4.0)\n"
        + "    zero2: Vec2 = Vec2(x=0.0, y=0.0)\n"
        + "    n2: GeometryVec2Result = normalize_vec2(v2)\n"
        + "    z2: GeometryVec2Result = normalize_vec2(zero2)\n"
        + "    failures = failures + mismatch(squared_distance_vec2(v2, zero2) == 25.0)\n"
        + "    failures = failures + mismatch(dot_vec2(v2, v2) == 25.0)\n"
        + "    failures = failures + mismatch(n2.status == 0)\n"
        + "    failures = failures + mismatch(z2.status == 1)\n"
        + "    return failures\n"
    )

    assert _run(source, optimization) == 0


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_point_cloud_centroid_validates_empty_and_shape(optimization) -> None:
    source = (
        "from s3.v1.geometry import point_cloud_centroid\n"
        "from s3.v1.geometry import point_cloud_bounds\n"
        "from s3.v1.geometry import point_cloud_squared_radius_sum\n"
        "from s3.v1.geometry import point_cloud_radius_of_gyration\n"
        "from s3.v1.geometry import GeometryScalarResult\n"
        "from s3.v1.geometry import Vec3\n"
        "from s3.v1.geometry import GeometryVec3Result\n"
        "from s3.v1.geometry import GeometryBounds3\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + "    mut points: f64_vector = f64_vector_new(6)\n"
        + "    discard f64_vector_push(&mut points, 1.0)\n"
        + "    discard f64_vector_push(&mut points, 2.0)\n"
        + "    discard f64_vector_push(&mut points, 3.0)\n"
        + "    discard f64_vector_push(&mut points, 3.0)\n"
        + "    discard f64_vector_push(&mut points, 4.0)\n"
        + "    discard f64_vector_push(&mut points, 7.0)\n"
        + "    mut empty: f64_vector = f64_vector_new(0)\n"
        + "    center: GeometryVec3Result = point_cloud_centroid(&points, 2)\n"
        + "    wrong_shape: GeometryVec3Result = point_cloud_centroid(&points, 1)\n"
        + "    empty_result: GeometryVec3Result = point_cloud_centroid(&empty, 0)\n"
        + "    bounds: GeometryBounds3 = point_cloud_bounds(&points, 2)\n"
        + "    radius_sum: GeometryScalarResult = point_cloud_squared_radius_sum(&points, 2, Vec3(x=2.0, y=3.0, z=5.0))\n"
        + "    empty_radius: GeometryScalarResult = point_cloud_squared_radius_sum(&empty, 0, Vec3(x=0.0, y=0.0, z=0.0))\n"
        + "    wrong_shape_radius: GeometryScalarResult = point_cloud_squared_radius_sum(&points, 1, Vec3(x=0.0, y=0.0, z=0.0))\n"
        + "    gyration: GeometryScalarResult = point_cloud_radius_of_gyration(&points, 2)\n"
        + "    empty_gyration: GeometryScalarResult = point_cloud_radius_of_gyration(&empty, 0)\n"
        + "    bad_bounds: GeometryBounds3 = point_cloud_bounds(&points, 3074457345618258603)\n"
        + "    mut failures: i64 = mismatch(center.status == 0)\n"
        + "    failures = failures + mismatch(center.value.x == 2.0)\n"
        + "    failures = failures + mismatch(center.value.y == 3.0)\n"
        + "    failures = failures + mismatch(center.value.z == 5.0)\n"
        + "    failures = failures + mismatch(wrong_shape.status == 2)\n"
        + "    failures = failures + mismatch(empty_result.status == 1)\n"
        + "    failures = failures + mismatch(bounds.status == 0)\n"
        + "    failures = failures + mismatch(bounds.minimum.x == 1.0)\n"
        + "    failures = failures + mismatch(bounds.minimum.y == 2.0)\n"
        + "    failures = failures + mismatch(bounds.minimum.z == 3.0)\n"
        + "    failures = failures + mismatch(bounds.maximum.x == 3.0)\n"
        + "    failures = failures + mismatch(bounds.maximum.y == 4.0)\n"
        + "    failures = failures + mismatch(bounds.maximum.z == 7.0)\n"
        + "    failures = failures + mismatch(radius_sum.status == 0)\n"
        + "    failures = failures + mismatch(radius_sum.value == 12.0)\n"
        + "    failures = failures + mismatch(empty_radius.status == 1)\n"
        + "    failures = failures + mismatch(wrong_shape_radius.status == 2)\n"
        + "    failures = failures + mismatch(gyration.status == 0)\n"
        + "    failures = failures + mismatch(gyration.value > 2.44)\n"
        + "    failures = failures + mismatch(gyration.value < 2.45)\n"
        + "    failures = failures + mismatch(empty_gyration.status == 1)\n"
        + "    failures = failures + mismatch(bad_bounds.status == 2)\n"
        + "    return failures\n"
    )

    assert _run(source, optimization) == 0


@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_triangle_mesh_area_validates_shape_indices_and_degeneracy(optimization) -> None:
    source = (
        "from s3.v1.geometry import triangle_mesh_surface_area\n"
        "from s3.v1.geometry import GeometryScalarResult\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + "    mut vertices: f64_vector = f64_vector_new(9)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 1.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    discard f64_vector_push(&mut vertices, 1.0)\n"
        + "    discard f64_vector_push(&mut vertices, 0.0)\n"
        + "    mut indices: i64_vector = i64_vector_new(3)\n"
        + "    discard i64_vector_push(&mut indices, 0)\n"
        + "    discard i64_vector_push(&mut indices, 1)\n"
        + "    discard i64_vector_push(&mut indices, 2)\n"
        + "    mut degenerate: i64_vector = i64_vector_new(3)\n"
        + "    discard i64_vector_push(&mut degenerate, 0)\n"
        + "    discard i64_vector_push(&mut degenerate, 0)\n"
        + "    discard i64_vector_push(&mut degenerate, 2)\n"
        + "    mut invalid: i64_vector = i64_vector_new(3)\n"
        + "    discard i64_vector_push(&mut invalid, -1)\n"
        + "    discard i64_vector_push(&mut invalid, 1)\n"
        + "    discard i64_vector_push(&mut invalid, 2)\n"
        + "    area: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &indices, 3, 1)\n"
        + "    zero_area: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &degenerate, 3, 1)\n"
        + "    bad_index: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &invalid, 3, 1)\n"
        + "    bad_shape: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &indices, 2, 1)\n"
        + "    too_many_vertices: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &indices, 3074457345618258603, 0)\n"
        + "    too_many_triangles: GeometryScalarResult = triangle_mesh_surface_area(&vertices, &indices, 0, 3074457345618258603)\n"
        + "    mut failures: i64 = mismatch(area.status == 0)\n"
        + "    failures = failures + mismatch(area.value == 0.5)\n"
        + "    failures = failures + mismatch(zero_area.status == 0)\n"
        + "    failures = failures + mismatch(zero_area.value == 0.0)\n"
        + "    failures = failures + mismatch(bad_index.status == 3)\n"
        + "    failures = failures + mismatch(bad_shape.status == 2)\n"
        + "    failures = failures + mismatch(too_many_vertices.status == 2)\n"
        + "    failures = failures + mismatch(too_many_triangles.status == 2)\n"
        + "    return failures\n"
    )

    assert _run(source, optimization) == 0


@pytest.mark.skipif(
    platform.system() != "Linux" or platform.machine().lower() not in {"x86_64", "amd64"},
    reason="native geometry integration requires Linux x86-64",
)
@pytest.mark.parametrize("optimization", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_native_geometry_point_cloud_and_triangle_area(tmp_path, optimization) -> None:
    source = (
        "from s3.v1.geometry import Vec3\n"
        "from s3.v1.geometry import GeometryVec3Result\n"
        "from s3.v1.geometry import GeometryScalarResult\n"
        "from s3.v1.geometry import point_cloud_centroid\n"
        "from s3.v1.geometry import point_cloud_radius_of_gyration\n"
        "from s3.v1.geometry import triangle_area\n"
        + _MISMATCH
        + "fn main() -> i64:\n"
        + "    mut points: f64_vector = f64_vector_new(6)\n"
        + "    discard f64_vector_push(&mut points, 1.0)\n"
        + "    discard f64_vector_push(&mut points, 2.0)\n"
        + "    discard f64_vector_push(&mut points, 3.0)\n"
        + "    discard f64_vector_push(&mut points, 3.0)\n"
        + "    discard f64_vector_push(&mut points, 4.0)\n"
        + "    discard f64_vector_push(&mut points, 7.0)\n"
        + "    center: GeometryVec3Result = point_cloud_centroid(&points, 2)\n"
        + "    gyration: GeometryScalarResult = point_cloud_radius_of_gyration(&points, 2)\n"
        + "    mut failures: i64 = mismatch(center.status == 0)\n"
        + "    failures = failures + mismatch(center.value.x == 2.0)\n"
        + "    failures = failures + mismatch(center.value.y == 3.0)\n"
        + "    failures = failures + mismatch(center.value.z == 5.0)\n"
        + "    failures = failures + mismatch(gyration.status == 0)\n"
        + "    failures = failures + mismatch(gyration.value > 2.44)\n"
        + "    failures = failures + mismatch(gyration.value < 2.45)\n"
        + "    failures = failures + mismatch(triangle_area(Vec3(x=0.0, y=0.0, z=0.0), Vec3(x=1.0, y=0.0, z=0.0), Vec3(x=0.0, y=1.0, z=0.0)) == 0.5)\n"
        + "    return failures\n"
    )
    modules = standard_library_sources(modules=("s3.v1.geometry",))
    modules["main.s3"] = "module main\n" + source
    compilation = compile_sources(
        modules,
        optimization=optimization,
        mode=SyntaxMode.V0_6,
    )
    executable = NativeToolchain.detect().build(
        generate_native_assembly(compilation.assembly),
        tmp_path / f"geometry-{optimization.value.lower()}",
    )
    result = NativeToolchain.detect().run(executable)

    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert result.stdout.strip() == "program returned: 0"
