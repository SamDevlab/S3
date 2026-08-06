import json
from pathlib import Path

from bootstrap.s3.ir_serialization import IR_FORMAT_VERSION
from bootstrap.s3.assembly import ASSEMBLY_FORMAT_VERSION
from bootstrap.s3.diagnostics import DIAGNOSTIC_SCHEMA_VERSION


def test_ai_capabilities_json_validity_and_consistency():
    manifest_path = Path(__file__).resolve().parent.parent / "docs" / "ai-capabilities.json"
    assert manifest_path.exists(), "docs/ai-capabilities.json must exist"

    content = manifest_path.read_text(encoding="utf-8")
    data = json.loads(content)

    assert data.get("manifest_version") == "1.0.0"
    assert data.get("ir_version") == IR_FORMAT_VERSION
    assert data.get("assembly_version") == ASSEMBLY_FORMAT_VERSION
    assert data.get("diagnostic_schema_version") == DIAGNOSTIC_SCHEMA_VERSION

    # Default implementation
    defaults = data.get("default_implementation", {})
    assert defaults.get("compiler") == "bootstrap-python"

    # Candidates must not be marked default
    candidates = data.get("candidate_components", [])
    assert isinstance(candidates, list) and len(candidates) > 0
    for cand in candidates:
        assert cand.get("default") is False, f"Candidate {cand.get('name')} must not be marked default"

    # Supported and unsupported sections
    supported = data.get("supported_features", {})
    assert "trit" in supported.get("scalar_types", [])
    assert "O0" in supported.get("optimizer_levels", [])
    assert "O1" in supported.get("optimizer_levels", [])

    unsupported = data.get("unsupported_features", {})
    assert unsupported.get("heap_allocation") is False
    assert unsupported.get("raw_pointers") is False
    assert unsupported.get("dynamic_arrays") is False
