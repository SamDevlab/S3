from __future__ import annotations

import argparse
import hashlib
import json
import math
import struct
import zipfile
from pathlib import Path

import numpy as np
from PIL import Image


POINT_CLOUD_ARCHIVE_SHA256 = "b94e0146c1d48c5edfc11af71b4af39ffca604485668c55a127c3b43203a6bd5"
POINT_CLOUD_MEMBER = "cloud_bin_0.pcd"
POINT_CLOUD_SHA256 = "e1e100802c29ef454c6b523084668ee0e2f365ec52eaeebe79ae804c20447b15"
RASTER_SHA256 = "cd43579caee85145c8d1407349f7de8b3215ed0ef76f563870e5553586fdeca4"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n").encode()


def _binary_pcd_xyz(data: bytes) -> tuple[list[tuple[float, float, float]], int]:
    marker = b"DATA binary\n"
    header, separator, payload = data.partition(marker)
    if not separator:
        marker = b"DATA binary\r\n"
        header, separator, payload = data.partition(marker)
    if not separator:
        raise ValueError("expected binary PCD data")
    fields: dict[str, list[str]] = {}
    for line in header.decode("ascii").splitlines():
        parts = line.split()
        if parts:
            fields[parts[0].upper()] = parts[1:]
    if fields.get("FIELDS") != ["x", "y", "z", "rgb", "normal_x", "normal_y", "normal_z", "curvature"]:
        raise ValueError("unexpected PCD field order")
    if fields.get("SIZE") != ["4"] * 8 or fields.get("TYPE") != ["F"] * 8:
        raise ValueError("expected eight float32 PCD fields")
    point_count = int(fields["POINTS"][0])
    if len(payload) != point_count * 32:
        raise ValueError("PCD payload length disagrees with point count")

    selected_indices = {index * (point_count - 1) // 120: index for index in range(121)}
    selected: list[tuple[float, float, float] | None] = [None] * 121
    for source_index, record in enumerate(struct.iter_unpack("<8f", payload)):
        target_index = selected_indices.get(source_index)
        if target_index is not None:
            xyz = (float(record[0]), float(record[1]), float(record[2]))
            if not all(math.isfinite(value) for value in xyz):
                raise ValueError(f"non-finite XYZ value at source point {source_index}")
            selected[target_index] = xyz
    if any(point is None for point in selected):
        raise ValueError("failed to extract all deterministic sample points")
    return [point for point in selected if point is not None], point_count


def build_fixture(point_cloud_zip: Path, raster_path: Path) -> tuple[dict[str, object], dict[str, object]]:
    archive_bytes = point_cloud_zip.read_bytes()
    if _sha256(archive_bytes) != POINT_CLOUD_ARCHIVE_SHA256:
        raise ValueError("Open3D archive SHA-256 mismatch")
    with zipfile.ZipFile(point_cloud_zip) as archive:
        pcd_bytes = archive.read(POINT_CLOUD_MEMBER)
    if _sha256(pcd_bytes) != POINT_CLOUD_SHA256:
        raise ValueError("Open3D point-cloud SHA-256 mismatch")
    points, total_points = _binary_pcd_xyz(pcd_bytes)
    point_array = np.asarray(points, dtype=np.float64)

    raster_bytes = raster_path.read_bytes()
    if _sha256(raster_bytes) != RASTER_SHA256:
        raise ValueError("USGS raster SHA-256 mismatch")
    with Image.open(raster_path) as image:
        if image.size != (4992, 6763) or image.mode != "P":
            raise ValueError("unexpected USGS raster dimensions or palette-index mode")
        nodata_tag = image.tag_v2.get(42113)
        if nodata_tag is not None:
            raise ValueError("fixture assumes no declared TIFF NoData tag")
        crop = image.crop((100, 200, 116, 216))
        raster_values = np.asarray(crop, dtype=np.float64).reshape(-1)
    valid_mask = np.ones(raster_values.size, dtype=np.int64)
    threshold = 5.0

    fixture: dict[str, object] = {
        "schema_version": "1.0.0",
        "fixture_id": "s3-1.6-public-compute-samples-v1",
        "point_cloud": {
            "dataset_id": "open3d-demo-icp-cloud-bin-0",
            "source_point_count": total_points,
            "sample_count": len(points),
            "sampling": "index=floor(i*(N-1)/120), i=0..120; preserve source order; take XYZ fields only",
            "coordinates_xyz": point_array.reshape(-1).tolist(),
            "expected": {
                "centroid_xyz": np.mean(point_array, axis=0).tolist(),
                "minimum_xyz": np.min(point_array, axis=0).tolist(),
                "maximum_xyz": np.max(point_array, axis=0).tolist(),
            },
        },
        "raster": {
            "dataset_id": "usgs-elliott-park-pa-7.5min-drg-o41078a5",
            "source_dimensions": [4992, 6763],
            "pixel_semantics": "8-bit palette category indices; not elevation values",
            "window": {"column": 100, "row": 200, "width": 16, "height": 16},
            "values": raster_values.tolist(),
            "valid_mask": valid_mask.tolist(),
            "threshold_strictly_greater_than": threshold,
            "expected": {
                "valid_mean": float(np.mean(raster_values)),
                "count_greater_than_threshold": int(np.count_nonzero(raster_values > threshold)),
            },
        },
        "reference": {
            "engine": "NumPy",
            "version": np.__version__,
            "semantics": "float64 reductions over the exact checked fixture arrays; categorical raster palette indices remain class codes",
        },
    }
    fixture_payload = _json_bytes(fixture)
    manifest: dict[str, object] = {
        "schema_version": "1.0.0",
        "manifest_id": "s3-1.6-public-datasets-v1",
        "retrieved_utc_date": "2026-09-26",
        "fixture_path": "s3-1.6-public-compute-samples-v1.json",
        "fixture_sha256": _sha256(fixture_payload),
        "sources": [
            {
                "dataset_id": "open3d-demo-icp-cloud-bin-0",
                "source_url": "https://github.com/isl-org/open3d_downloads/releases/download/20220301-data/DemoICPPointClouds.zip",
                "archive_member": POINT_CLOUD_MEMBER,
                "archive_bytes": len(archive_bytes),
                "archive_sha256": POINT_CLOUD_ARCHIVE_SHA256,
                "member_bytes": len(pcd_bytes),
                "member_sha256": POINT_CLOUD_SHA256,
                "license": "CC BY 3.0; attribute Open3D and its dataset contributors",
                "license_reference": "https://www.open3d.org/html/cpp_api/classopen3d_1_1data_1_1_demo_i_c_p_point_clouds.html",
                "transformation": "validate binary PCD header, select 121 evenly spaced source indices floor(i*(N-1)/120), retain float32 XYZ and represent as JSON numbers; no geometric transform",
            },
            {
                "dataset_id": "usgs-elliott-park-pa-7.5min-drg-o41078a5",
                "source_url": "https://download.osgeo.org/geotiff/samples/usgs/o41078a5.tif",
                "bytes": len(raster_bytes),
                "sha256": RASTER_SHA256,
                "archive_listing_date": "2007-03-29",
                "license": "USGS historical topographic map public domain; source is a pre-2009 USGS DRG sample",
                "license_reference": "https://www.usgs.gov/faqs/are-usgs-topographic-maps-copyrighted",
                "catalog_reference": "https://libremap.org/data/state/pennsylvania/drg/",
                "transformation": "read 8-bit palette indices, crop columns [100,116) and rows [200,216), flatten row-major; all-valid mask because no TIFF NoData tag is declared; do not interpret palette values as elevation",
            },
        ],
        "reference": {
            "engine": "NumPy",
            "version": np.__version__,
            "point_cloud": "centroid and axis-aligned bounds over sampled XYZ",
            "raster": "mean of all valid palette-index cells and count strictly greater than 5.0",
        },
    }
    return fixture, manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Create hash-pinned S3 1.6 public-data fixtures; performs no network access.")
    parser.add_argument("--point-cloud-zip", type=Path, required=True)
    parser.add_argument("--raster", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    fixture, manifest = build_fixture(args.point_cloud_zip, args.raster)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    fixture_path = args.output_dir / "s3-1.6-public-compute-samples-v1.json"
    manifest_path = args.output_dir / "public-datasets-v1.json"
    fixture_path.write_bytes(_json_bytes(fixture))
    manifest_path.write_bytes(_json_bytes(manifest))
    print(f"FIXTURE={fixture_path}")
    print(f"FIXTURE_SHA256={_sha256(fixture_path.read_bytes())}")
    print(f"MANIFEST={manifest_path}")
    print(f"MANIFEST_SHA256={_sha256(manifest_path.read_bytes())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
