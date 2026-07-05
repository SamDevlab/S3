import pytest
from pathlib import Path
from tools.benchmark import load_manifest, run_hosted_pipeline
from bootstrap.s3 import OptimizationLevel

def test_manifest_structure():
    manifest_path = Path(__file__).parent.parent / "benchmarks" / "manifest.json"
    assert manifest_path.exists()

    manifest = load_manifest(manifest_path)
    assert manifest["manifest_version"] == "1.0.0"

    workloads = manifest["workloads"]
    assert len(workloads) == 7

    ids = [w["id"] for w in workloads]
    assert len(set(ids)) == 7

    for w in workloads:
        assert (Path(__file__).parent.parent / "benchmarks" / w["file"]).exists()
        assert not Path(w["file"]).is_absolute()
        assert w["max_instructions"] > 0
        assert "expected_return" in w
        if "max_frames" in w:
            assert w["max_frames"] > 0

@pytest.mark.parametrize("workload_id", [
    "minimal",
    "arithmetic",
    "branches",
    "calls",
    "recursion",
    "arrays",
    "optimizer_stress",
])
@pytest.mark.parametrize("opt", [OptimizationLevel.O0, OptimizationLevel.O1])
def test_workload_execution(workload_id, opt):
    manifest_path = Path(__file__).parent.parent / "benchmarks" / "manifest.json"
    manifest = load_manifest(manifest_path)
    w = next(w for w in manifest["workloads"] if w["id"] == workload_id)

    w_path = Path(__file__).parent.parent / "benchmarks" / w["file"]
    with w_path.open("r", encoding="utf-8") as f:
        source = f.read()

    expected_ret = w["expected_return"]
    max_inst = w["max_instructions"]
    max_frames = w.get("max_frames")

    ret = run_hosted_pipeline(source, opt, max_inst, max_frames)
    assert ret == expected_ret
