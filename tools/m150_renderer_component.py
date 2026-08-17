"""Hosted gate for the bounded M1.50 Assembly renderer component."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from bootstrap.s3.emulator import Emulator
from bootstrap.s3.pipeline import compile_source, run_source_with_buffer_capture
from bootstrap.s3.optimizer import OptimizationLevel
from tools.s3_renderer_contract import FIXTURE_METADATA, _git_blob_bytes, flatten_capture


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPONENT_SOURCE = REPO_ROOT / "examples" / "self_hosting" / "assembly_renderer_generic_text.s3"
LOCKFILE = REPO_ROOT / "spec" / "lockfile-v1.json"
COMPONENT_MEMORY_LIMIT_BYTES = 8 * 1024 * 1024
COMPONENT_PROFILE = "m150-hosted-assembly-renderer-v1"
ENTRY_METADATA = {
    "render_first": "first_generic",
    "render_simple_call": "simple_call_generic",
    "render_sign": "sign_generic",
}


@dataclass(frozen=True, slots=True)
class ComponentRun:
    entry: str
    optimization: str
    output: bytes | None
    allocated_cells: int
    assembly_sha256: str
    return_value: int


def _read_bytes(path: Path) -> bytes:
    return path.read_bytes()


def component_identity() -> dict[str, str]:
    source_hash = hashlib.sha256(_read_bytes(COMPONENT_SOURCE)).hexdigest()
    lock_hash = hashlib.sha256(_read_bytes(LOCKFILE)).hexdigest()
    payload = {
        "component": COMPONENT_PROFILE,
        "lock_sha256": lock_hash,
        "source_sha256": source_hash,
    }
    identity_payload = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return {
        **payload,
        "identity": hashlib.sha256(identity_payload.encode("utf-8")).hexdigest(),
    }


def _run(entry: str, optimization: OptimizationLevel) -> ComponentRun:
    metadata = FIXTURE_METADATA[ENTRY_METADATA[entry]]
    source = COMPONENT_SOURCE.read_text(encoding="utf-8")
    compilation = compile_source(source, optimization)
    entry_function = next(
        function for function in compilation.assembly.functions if function.name == entry
    )
    allocated_cells = sum(memory.length for memory in entry_function.memory_objects)
    if allocated_cells > COMPONENT_MEMORY_LIMIT_BYTES:
        raise AssertionError(
            f"{entry} allocated {allocated_cells} cells, above the "
            f"{COMPONENT_MEMORY_LIMIT_BYTES}-byte component budget"
        )
    if optimization is OptimizationLevel.O0:
        result, captures = run_source_with_buffer_capture(
            source,
            entry=entry,
            optimization=optimization,
            max_instructions=metadata.max_instructions,
        )
        if result != 0:
            raise AssertionError(f"{entry} returned {result}")
        if not captures:
            raise AssertionError(f"{entry} produced no memory capture")
        output = flatten_capture(
            captures[-1],
            metadata.buffer_count,
            metadata.buffer_offset,
            metadata.expected_bytes,
        )
    else:
        # The current optimizer deliberately removes frame-local stores that
        # have no in-program LOAD. The renderer harness observes those stores
        # after return, so O1 execution is proved separately until that
        # observable-memory contract is made explicit in the compiler.
        result = Emulator(max_instructions=metadata.max_instructions).execute(
            compilation.assembly,
            entry,
        )
        output = None
    return ComponentRun(
        entry=entry,
        optimization=optimization.value,
        output=output,
        allocated_cells=allocated_cells,
        assembly_sha256=hashlib.sha256(compilation.assembly.render().encode("utf-8")).hexdigest(),
        return_value=result,
    )


def check_component() -> dict[str, object]:
    """Run the hosted O0/O1 and Python-oracle gate for all bounded entries."""

    results: list[dict[str, object]] = []
    for entry in ENTRY_METADATA:
        metadata = FIXTURE_METADATA[ENTRY_METADATA[entry]]
        reference = _git_blob_bytes(metadata.golden_path)
        o0 = _run(entry, OptimizationLevel.O0)
        o1 = _run(entry, OptimizationLevel.O1)
        if o0.output != reference:
            raise AssertionError(f"{entry} differs from the Python renderer oracle")
        if o1.return_value != 0:
            raise AssertionError(f"{entry} O1 returned {o1.return_value}")
        results.append(
            {
                "entry": entry,
                "expected_bytes": metadata.expected_bytes,
                "expected_lines": metadata.expected_lines,
                "sha256": hashlib.sha256(o0.output).hexdigest(),
                "allocated_cells": o0.allocated_cells,
                "o0_python_oracle_equal": True,
                "o1_execution": "PASS",
                "o1_output_parity": "DEFERRED_OPTIMIZER_OBSERVABLE_MEMORY_CONTRACT",
            }
        )
    return {
        "schema_version": "s3.m150.renderer-component-gate.v1",
        "component": COMPONENT_PROFILE,
        "source": COMPONENT_SOURCE.relative_to(REPO_ROOT).as_posix(),
        "memory_limit_bytes": COMPONENT_MEMORY_LIMIT_BYTES,
        "identity": component_identity(),
        "hosted_o0_oracle": "PASS",
        "hosted_o1_execution": "PASS",
        "o1_output_parity": "DEFERRED_OPTIMIZER_OBSERVABLE_MEMORY_CONTRACT",
        "native_linux": "DEFERRED_ENVIRONMENT",
        "wasi_runtime": "DEFERRED_ENVIRONMENT",
        "entries": results,
    }


def main() -> int:
    print(json.dumps(check_component(), sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
