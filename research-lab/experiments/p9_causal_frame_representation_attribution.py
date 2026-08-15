"""P9 causal attribution probe; research-only and never imported by production.

The probe uses the production compiler checkout as an immutable input.  It
adds deterministic site comments to a disposable x86 emitter subclass and
counts Assembly-site executions with a disposable copy of the emulator's
execute loop.  The resulting x86 count is a modelled estimate, not a hardware
retired-instruction count: each executed Assembly site is weighted by its
normal-path emitted x86 source lines.
"""

from __future__ import annotations

import argparse
import inspect
import importlib.util
import json
import re
import subprocess
import sys
import textwrap
from collections import Counter, defaultdict
from pathlib import Path


SITE_COMMENT = re.compile(
    r"^# S3SITE (?P<function>[^ ]+) (?P<block>[^ ]+) (?P<index>\d+) "
    r"(?P<opcode>[^ ]+)$"
)
X86_SOURCE = re.compile(r"^\s+([A-Za-z][A-Za-z0-9_.]*)(?:\s|$)")


def load_internal_workloads(production_root: Path):
    research_root = Path(__file__).resolve().parent
    if str(research_root) not in sys.path:
        sys.path.insert(0, str(research_root))
    saved_argv = sys.argv[:]
    try:
        sys.argv = [sys.argv[0], str(production_root), "p9_internal"]
        from post_p7_obligation_profile import WORKLOADS
    finally:
        sys.argv = saved_argv
    selected = (
        "scalar_i64",
        "integer_loop",
        "nested_loop",
        "branch_heavy",
        "call_heavy",
        "f64_kernel",
        "trit_kernel",
        "fixed_array",
        "array_loop",
    )
    return {name: WORKLOADS[name] for name in selected}


def load_jsmn_inputs(benchmark_root: Path) -> dict[str, str]:
    corpus = benchmark_root / "benchmarks" / "jsmn" / "corpus" / "tiny"
    return {
        path.stem: path.read_text(encoding="utf-8")
        for path in sorted(corpus.glob("*.json"))
    }


def render_jsmn_source(template: str, text: str) -> str:
    values = list(text.encode("ascii"))
    if len(values) > 96:
        raise ValueError(f"fixture exceeds S3 benchmark capacity: {len(values)}")
    padded = values + [0] * (96 - len(values))
    rendered = re.sub(
        r"(?m)^    input_length: tryte = \d+$",
        f"    input_length: tryte = {len(values)}",
        template,
        count=1,
    )
    return re.sub(
        r"(?m)^    input: tryte\[96\] = \[[^\n]+\]$",
        "    input: tryte[96] = [" + ", ".join(map(str, padded)) + "]",
        rendered,
        count=1,
    )


def build_traced_execute(Emulator):
    source = textwrap.dedent(inspect.getsource(Emulator.execute))
    needle = "        instruction = block.instructions[frame.instruction_index]\n"
    replacement = needle + (
        "        self._record_site(frame.function.name, frame.block_label, "
        "frame.instruction_index, instruction)\n"
    )
    if needle not in source:
        raise RuntimeError("emulator execute site was not found")
    namespace = dict(Emulator.execute.__globals__)
    exec(compile(source.replace(needle, replacement, 1), "<p9-traced-emulator>", "exec"), namespace)
    return namespace["execute"]


def make_trace_emulator(Emulator):
    class TraceEmulator(Emulator):
        def __init__(self):
            super().__init__()
            self.site_counts: Counter[str] = Counter()

        def _record_site(self, function, block, index, instruction):
            self.site_counts[
                f"{function}::{block}::{index}::{instruction.opcode.value}"
            ] += 1

        def run(self, program):
            self.site_counts.clear()
            result = self.execute(program)
            return result, dict(self.site_counts)

    TraceEmulator.execute = build_traced_execute(Emulator)
    return TraceEmulator


def make_trace_emitter(X8664Emitter):
    class TraceEmitter(X8664Emitter):
        def __init__(self, program, **kwargs):
            super().__init__(program, **kwargs)
            self.site_indices = {
                id(instruction): (function.name, block.label, index)
                for function in program.functions
                for block in function.blocks
                for index, instruction in enumerate(block.instructions)
            }

        def _comment(self, instruction):
            function, block, index = self.site_indices[id(instruction)]
            return (
                f"# S3SITE {function} {block} {index} "
                f"{instruction.opcode.value}"
            )

        def _emit_instruction(self, function, block_name, layout, instruction):
            return [self._comment(instruction), *super()._emit_instruction(function, block_name, layout, instruction)]

        def _emit_tcmp_tbr3(self, function, block_name, layout, compare, branch):
            body = super()._emit_tcmp_tbr3(
                function, block_name, layout, compare, branch
            )
            marker = "    cmp qword ptr [rip + __s3_instruction_count]"
            cmp_positions = [
                index for index, line in enumerate(body)
                if line.startswith(marker)
            ]
            if len(cmp_positions) != 2:
                raise RuntimeError("could not split fused compare/branch site map")
            body.insert(cmp_positions[1], self._comment(branch))
            return [self._comment(compare), *body]

    return TraceEmitter


def classify_x86(line: str, opcode: str, site_line_index: int) -> str | None:
    match = X86_SOURCE.match(line)
    if not match:
        return None
    mnemonic = match.group(1).lower()
    text = line.lower()
    if "__s3_instruction_count" in text:
        return "INSTRUCTION_LIMIT"
    if site_line_index < 3 and mnemonic in {"movabs", "cmp", "jae", "inc"}:
        return "INSTRUCTION_LIMIT"
    if mnemonic == "call":
        return "CALL_ABI"
    if mnemonic.startswith("j"):
        if opcode in {"TLOAD", "TSTORE"}:
            return "BOUNDS_CHECK"
        return "CONTROL_FLOW"
    if mnemonic in {"push", "pop", "leave", "ret"}:
        return "FRAME_CANONICALIZATION"
    if mnemonic == "lea":
        return "ADDRESS_CALCULATION"
    if "[rbp" in text:
        if opcode in {"TLOAD", "TSTORE", "TADDR", "TSLOAD", "TSSTORE"}:
            if "byte ptr" in text and ("cmp" in text or "mov byte ptr" in text):
                return "MEMORY_VALIDITY"
            if re.search(r"\+ (r(?:10|ax))\*", text):
                return "ARRAY_DATA_ACCESS"
            if re.search(r"\+ (r(?:10|ax)) -", text):
                return "MEMORY_VALIDITY"
            return "FRAME_CANONICALIZATION"
        return "FRAME_CANONICALIZATION"
    if opcode in {"TLOAD", "TSTORE"} and mnemonic == "cmp":
        return "BOUNDS_CHECK"
    if mnemonic in {"mov", "movsx", "movzx", "movsxd", "movq"}:
        if opcode in {"TLOAD", "TSTORE", "TSLOAD", "TSSTORE"}:
            return "SEMANTIC_PAYLOAD"
        if opcode in {"TCVT"}:
            return "REPRESENTATION_CONVERSION"
        return "SEMANTIC_PAYLOAD"
    if mnemonic in {"sub", "add", "imul", "idiv", "neg", "not", "and", "or", "xor", "cmp", "test", "setl", "setg"}:
        return "SEMANTIC_PAYLOAD"
    return "OTHER_REQUIRED"


def site_static_map(assembly_text: str) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    current: str | None = None
    for line in assembly_text.splitlines():
        if line.startswith(".size ") or line.startswith(".section "):
            current = None
            continue
        marker = SITE_COMMENT.match(line)
        if marker:
            current = (
                f"{marker['function']}::{marker['block']}::"
                f"{marker['index']}::{marker['opcode']}"
            )
            rows[current] = {
                "site_id": current,
                "function": marker["function"],
                "block": marker["block"],
                "instruction_index": int(marker["index"]),
                "opcode": marker["opcode"],
                "x86_lines": [],
                "classes": Counter(),
            }
            continue
        if current is None:
            continue
        category = classify_x86(
            line,
            rows[current]["opcode"],
            len(rows[current]["x86_lines"]),
        )
        if category is not None:
            rows[current]["x86_lines"].append(line.strip())
            rows[current]["classes"][category] += 1
    result = {}
    for key, row in rows.items():
        classes = dict(row["classes"])
        result[key] = {
            **row,
            "x86_line_count": len(row["x86_lines"]),
            "class_counts": classes,
        }
        result[key].pop("classes")
    return result


def enrich_site_map(static, function, allocation):
    for site, row in static.items():
        if row["function"] != function.name:
            continue
        _, block_name, index_text, _ = site.split("::")
        instruction = function_block_instruction(function, block_name, int(index_text))
        physical = {
            str(register): allocation.physical_register(register)
            for register in instruction.registers
        }
        frame_value_lines = [
            line for line in row["x86_lines"]
            if "qword ptr [rbp" in line
            and not re.search(r"\+ r(?:10|ax)\*", line)
            and not re.search(r"\+ r(?:10|ax) -", line)
        ]
        row["registers"] = list(instruction.registers)
        row["physical_registers"] = physical
        row["stack_resident_registers"] = [
            register for register, value in physical.items() if value is None
        ]
        row["frame_value_line_count"] = len(frame_value_lines)
        row["stack_frame_value_line_count"] = (
            len(frame_value_lines) if row["stack_resident_registers"] else 0
        )


def function_block_instruction(function, block_name: str, index: int):
    block = next(block for block in function.blocks if block.label == block_name)
    return block.instructions[index]


def summarize_dynamic(static_maps, dynamic_maps):
    static_by_class = Counter()
    dynamic_by_class = Counter()
    site_weights: Counter[str] = Counter()
    workload_classes: dict[str, set[str]] = defaultdict(set)
    frame_static = 0
    frame_dynamic = 0
    stack_frame_static = 0
    stack_frame_dynamic = 0
    for workload, static in static_maps.items():
        dynamic = dynamic_maps[workload]
        for site, row in static.items():
            execution_count = dynamic.get(site, 0)
            frame_static += row.get("frame_value_line_count", 0)
            frame_dynamic += execution_count * row.get("frame_value_line_count", 0)
            stack_frame_static += row.get("stack_frame_value_line_count", 0)
            stack_frame_dynamic += execution_count * row.get("stack_frame_value_line_count", 0)
            for category, count in row["class_counts"].items():
                static_by_class[category] += count
                dynamic_by_class[category] += execution_count * count
            site_weights[f"{workload}:{site}"] += execution_count * row["x86_line_count"]
            if execution_count:
                for category in row["class_counts"]:
                    workload_classes[category].add(workload)
    total = sum(site_weights.values())
    hot = sorted(site_weights.values(), reverse=True)
    share = lambda n: sum(hot[:n]) / total if total else 0.0
    return {
        "static_by_class": dict(static_by_class),
        "modelled_dynamic_by_class": dict(dynamic_by_class),
        "modelled_dynamic_total": total,
        "frame_value_static": frame_static,
        "frame_value_modelled_dynamic": frame_dynamic,
        "stack_resident_frame_value_static": stack_frame_static,
        "stack_resident_frame_value_modelled_dynamic": stack_frame_dynamic,
        "true_spill_status": "NOT_ESTABLISHED; stack residency is observed, spill causality is not",
        "top_10_sites_dynamic_share": share(10),
        "top_25_sites_dynamic_share": share(25),
        "top_50_sites_dynamic_share": share(50),
        "workload_generality_by_class": {
            key: sorted(value) for key, value in sorted(workload_classes.items())
        },
        "hot_sites": [
            {"site": site, "modelled_dynamic_count": count}
            for site, count in sorted(site_weights.items(), key=lambda item: (-item[1], item[0]))[:50]
        ],
    }


def disassembly_metrics(executable: Path) -> dict[str, int]:
    text = subprocess.check_output(["objdump", "-d", "--section=.text", str(executable)], text=True)
    instructions = [line for line in text.splitlines() if re.match(r"^\s*[0-9a-f]+:\s+[0-9a-f ]+\s+\S+", line)]
    return {
        "native_static_instructions": len(instructions),
        "native_memory_syntax_lines": sum("[rbp" in line or "[rip" in line for line in instructions),
        "native_branch_instructions": sum(bool(re.search(r"\s(j[a-z]*|loop)\s", line)) for line in instructions),
    }


def load_correctness_module(benchmark_root: Path):
    path = benchmark_root / "benchmarks/jsmn/harness/correctness.py"
    spec = importlib.util.spec_from_file_location("p9_benchmark_correctness", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load benchmark correctness module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_one(name, source, expected, production_root, benchmark_root, output, TraceEmulator, TraceEmitter, native_toolchain, *, external=False):
    from bootstrap.s3.backends.x86_64 import X8664Backend
    from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
    from bootstrap.s3.ir_emulator import execute_ir
    from bootstrap.s3.lexer import SyntaxMode
    from bootstrap.s3.pipeline import compile_source
    from bootstrap.s3.ssa import SSABuilder

    optimizations = {}
    for optimization in ("O0", "O1"):
        compilation = compile_source(source, optimization, mode=SyntaxMode.V0_6)
        ssa_functions = [SSABuilder.build_function(function) for function in compilation.ir.functions]
        ir_result = execute_ir(compilation.ir)
        trace_emulator = TraceEmulator()
        assembly_result, counts = trace_emulator.run(compilation.assembly)
        if ir_result != assembly_result or assembly_result != expected:
            raise AssertionError(f"{name} {optimization}: IR={ir_result} assembly={assembly_result} expected={expected}")
        baseline_assembly = X8664Backend().generate(compilation.assembly)
        traced_assembly = TraceEmitter(
            compilation.assembly,
            max_frames=1024,
            max_instructions=100_000,
            register_allocation=True,
        ).emit()
        stripped = "\n".join(line for line in traced_assembly.splitlines() if not line.startswith("# S3SITE")) + "\n"
        if stripped != baseline_assembly:
            raise AssertionError(f"{name} {optimization}: side-car emitter changed x86 output")
        static = site_static_map(traced_assembly)
        for function in compilation.assembly.functions:
            enrich_site_map(static, function, analyze_allocation(function))
        native = {"status": "NOT_RUN"}
        if native_toolchain is not None:
            executable = native_toolchain.build(
                baseline_assembly,
                output / f"{name}-{optimization.lower()}",
            )
            completed = native_toolchain.run(executable)
            native = {
                "status": "PASS" if completed.returncode == 0 and f"program returned: {expected}" in completed.stdout else "FAIL",
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
                "metrics": disassembly_metrics(executable),
            }
            if native["status"] != "PASS":
                raise AssertionError(f"{name} {optimization}: native mismatch {native}")
        optimizations[optimization] = {
            "expected": expected,
            "ir_result": ir_result,
            "assembly_result": assembly_result,
            "native": native,
            "dynamic_site_counts": counts,
            "static_sites": static,
            "dynamic_total_assembly_instructions": sum(counts.values()),
            "external": external,
            "ir_opcode_counts": dict(Counter(instruction.opcode.value for function in compilation.ir.functions for instruction in function.instructions)),
            "ssa_opcode_counts": dict(Counter(instruction.opcode.value for function in ssa_functions for block in function.blocks for instruction in block.instructions)),
            "ssa_phi_count": sum(len(block.phis) for function in ssa_functions for block in function.blocks),
            "assembly_opcode_counts": dict(Counter(instruction.opcode.value for function in compilation.assembly.functions for instruction in function.instructions)),
        }
    return {"workload": name, "optimizations": optimizations}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--production-checkout", type=Path, required=True)
    parser.add_argument("--production-sha", required=True)
    parser.add_argument("--benchmark-checkout", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-native", action="store_true")
    args = parser.parse_args()
    actual = subprocess.check_output(["git", "-C", str(args.production_checkout), "rev-parse", "HEAD"], text=True).strip()
    if actual != args.production_sha:
        raise SystemExit(f"TARGET_HEAD_MATCH=NO actual={actual} expected={args.production_sha}")
    sys.path.insert(0, str(args.production_checkout))
    sys.path.insert(1, str(args.benchmark_checkout))
    from bootstrap.s3.backends.x86_64.emitter import X8664Emitter
    from bootstrap.s3.emulator import Emulator

    TraceEmulator = make_trace_emulator(Emulator)
    TraceEmitter = make_trace_emitter(X8664Emitter)
    from bootstrap.s3.backends.x86_64 import NativeToolchain
    native_toolchain = NativeToolchain.detect() if args.run_native else None
    work_output = args.output.parent / "p9-native-workloads"
    work_output.mkdir(parents=True, exist_ok=True)
    internal = load_internal_workloads(args.production_checkout)
    results = []
    for name, (source, expected) in internal.items():
        results.append(run_one(name, source, expected, args.production_checkout, args.benchmark_checkout, work_output, TraceEmulator, TraceEmitter, native_toolchain))

    template = (args.benchmark_checkout / "benchmarks/jsmn/s3/jsmn_demo.s3").read_text(encoding="utf-8")
    external_inputs = load_jsmn_inputs(args.benchmark_checkout)
    external_correctness = {}
    if str(args.benchmark_checkout) not in sys.path:
        sys.path.insert(1, str(args.benchmark_checkout))
    correctness = load_correctness_module(args.benchmark_checkout)
    compare_results = correctness.compare_results
    reference_jsmn_oracle = correctness.reference_jsmn_oracle
    run_s3_jsmn = correctness.run_s3_jsmn
    for name, text in external_inputs.items():
        rendered = render_jsmn_source(template, text)
        reference_status, reference_tokens = reference_jsmn_oracle(text.encode("ascii"))
        observed = run_s3_jsmn(template, text, "O1")
        passed = compare_results(reference_status, reference_tokens, observed)
        external_correctness[name] = {
            "reference_status": reference_status,
            "observed_status": observed.status,
            "checksum": observed.checksum,
            "pass": passed,
        }
        if not passed:
            raise AssertionError(f"external correctness failed for {name}")
        results.append(run_one(name, rendered, reference_status, args.production_checkout, args.benchmark_checkout, work_output, TraceEmulator, TraceEmitter, native_toolchain, external=True))

    static_maps = {}
    dynamic_maps = {}
    workload_results = {}
    for result in results:
        workload = result["workload"]
        workload_results[workload] = result
        for optimization, data in result["optimizations"].items():
            key = f"{workload}/{optimization}"
            static_maps[key] = data["static_sites"]
            dynamic_maps[key] = data["dynamic_site_counts"]
    summary = summarize_dynamic(static_maps, dynamic_maps)
    dynamic_model_valid = all(
        data["ir_result"] == data["assembly_result"] and data["native"]["status"] in {"PASS", "NOT_RUN"}
        for result in results
        for data in result["optimizations"].values()
    ) and all(item["pass"] for item in external_correctness.values())
    payload = {
        "campaign": "P9_CAUSAL_FRAME_REPRESENTATION_ATTRIBUTION_V1",
        "target_main_sha": actual,
        "benchmark_measurement_head": subprocess.check_output(["git", "-C", str(args.benchmark_checkout), "rev-parse", "HEAD"], text=True).strip(),
        "benchmark_main_sha": subprocess.check_output(["git", "-C", str(args.benchmark_checkout), "rev-parse", "origin/main"], text=True).strip(),
        "external_report": "reports/jsmn-post-p8-20260814.md",
        "external_benchmark_correctness": "PASS",
        "external_fixture_count": len(external_inputs),
        "internal_workload_count": len(internal),
        "internal_dynamic_exclusions": {
            "slice_reference": "Assembly emulator does not support TADDR; excluded from modelled dynamic weighting"
        },
        "dynamic_source": "ASSEMBLY_EMULATOR_SITE_EXECUTIONS_WEIGHTED_BY_DISPOSABLE_X86_SOURCE_MAP",
        "dynamic_model_name": "MODELLED_NATIVE_DYNAMIC_COUNT",
        "dynamic_model_is_hardware_count": False,
        "sidecar_output_identity_preserved": True,
        "dynamic_model_validation": "PASS" if dynamic_model_valid else "FAIL",
        "workloads": workload_results,
        "external_correctness": external_correctness,
        "summary": summary,
        "candidate_hypotheses": [
            "memory-state-materialization",
            "fixed-array-frame-traffic",
            "per-parse-fixed-cost-expansion",
        ],
        "production_compiler_changed": False,
        "p9_started": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "target_head": actual,
        "dynamic_model_validation": payload["dynamic_model_validation"],
        "external_correctness": payload["external_benchmark_correctness"],
        "workloads": len(results),
        "modelled_dynamic_total": summary["modelled_dynamic_total"],
        "dynamic_by_class": summary["modelled_dynamic_by_class"],
        "top_10_share": summary["top_10_sites_dynamic_share"],
        "top_25_share": summary["top_25_sites_dynamic_share"],
        "top_50_share": summary["top_50_sites_dynamic_share"],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
