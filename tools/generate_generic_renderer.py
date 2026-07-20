"""Generate unified S3 renderer by combining three legacy S3 files."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

FIXTURES = ["first", "simple_call", "sign"]

LEGACY_PATHS = {
    "first": "examples/self_hosting/assembly_renderer_first_text.s3",
    "simple_call": "examples/self_hosting/assembly_renderer_simple_call_text.s3",
    "sign": "examples/self_hosting/assembly_renderer_sign_text.s3",
}

FIXTURE_CONFIG = {
    "first": ("render_first", ["buffer_low", "buffer_high"], ["cursor_low", "cursor_high"], [300, 300]),
    "simple_call": ("render_simple_call", ["buffer_low", "buffer_high"], ["cursor_low", "cursor_high"], [300, 300]),
    "sign": ("render_sign", ["buffer_low", "buffer_mid", "buffer_high"], ["cursor_low", "cursor_mid", "cursor_high"], [364, 364, 218]),
}

# The source function names used in each fixture's main body
FIXTURE_SOURCE_FUNCS = {
    "first": ["text_byte_at"],
    "simple_call": ["fragment_byte", "symbol_byte", "opcode_byte"],
    "sign": ["fragment_byte", "symbol_byte", "opcode_byte"],
}


def extract_texts(source: str, fn_name: str) -> dict[int, bytes]:
    """Extract text entries from a specific byte-lookup function."""
    texts: dict[int, bytes] = {}
    m = re.search(r'fn ' + re.escape(fn_name) + r'\(.*?\) -> tryte:\s*(.*?)(?=\nfn |\Z)', source, re.DOTALL)
    if not m:
        return texts
    body = m.group(1)
    for m2 in re.finditer(r'match id <=> (\d+):\s*0:', body):
        tid = int(m2.group(1))
        rest = body[m2.end():]
        branch_end = re.search(r'match id <=>', rest)
        branch = rest[:branch_end.start()] if branch_end else rest
        vals = []
        for bm in re.finditer(r'match index <=> (\d+):\s*0:\s*return (\d+)', branch):
            vals.append((int(bm.group(1)), int(bm.group(2))))
        if vals:
            vals.sort()
            texts[tid] = bytes(v for _, v in vals)
    return texts


def build_unified_table(
    fixture_sources: dict[str, str]
) -> tuple[dict[int, bytes], dict[str, dict[str, dict[int, int]]]]:
    """Build unified text table and per-fixture per-function ID mappings.

    Returns:
        unified: dict[unified_id -> bytes]
        fixture_map: dict[fixture_name -> dict[source_func_name -> dict[old_id -> new_id]]]
    """
    content_to_id: dict[bytes, int] = {}
    unified: dict[int, bytes] = {}
    fixture_map: dict[str, dict[str, dict[int, int]]] = {}
    next_id = 1

    for name in FIXTURES:
        func_maps: dict[str, dict[int, int]] = {}
        for func_name in FIXTURE_SOURCE_FUNCS[name]:
            texts = extract_texts(fixture_sources[name], func_name)
            old_to_new: dict[int, int] = {}
            for old_id, bs in sorted(texts.items()):
                if bs not in content_to_id:
                    content_to_id[bs] = next_id
                    unified[next_id] = bs
                    next_id += 1
                old_to_new[old_id] = content_to_id[bs]
            func_maps[func_name] = old_to_new
        fixture_map[name] = func_maps

    return unified, fixture_map


def extract_function_body(source: str, fn_name: str) -> str | None:
    m = re.search(r'(fn ' + re.escape(fn_name) + r'\(.*?\) -> tryte:\s*.*?)(?=\nfn |\Z)', source, re.DOTALL)
    if m:
        return m.group(1).rstrip()
    return None


def generate(fixture_sources: dict[str, str]) -> str:
    print("  Building unified text table...", file=sys.stderr)
    unified, fixture_map = build_unified_table(fixture_sources)
    print(f"  Unified: {len(unified)} text strings", file=sys.stderr)

    lines = []
    lines.append("# S3 Assembly Renderer - Generic Event-Driven Text Renderer (v0.41)")
    lines.append("# Unified replacement for three fixture-specific renderers")
    lines.append("")

    # Shared text_byte_at (binary-search tree for O(log n) lookup)
    lines.append("fn text_byte_at(id: tryte, index: tryte) -> tryte:")
    sorted_tids = sorted(unified.keys())

    def emit_text_tree(tids, indent=2):
        result = []
        pre = "    " * indent
        if not tids:
            result.append(f"{pre}return 0")
        elif len(tids) == 1:
            tid = tids[0]
            bs = unified[tid]
            result.append(f"{pre}match id <=> {tid}:")
            result.append(f"{pre}    -1:")
            result.append(f"{pre}        return 0")
            result.append(f"{pre}    0:")
            for idx, b in enumerate(bs):
                result.append(f"{pre}        match index <=> {idx}:")
                result.append(f"{pre}            0:")
                result.append(f"{pre}                return {b}")
                result.append(f"{pre}            -1:")
                result.append(f"{pre}                skip_{tid}_{idx}: tryte = 0")
                result.append(f"{pre}            1:")
                result.append(f"{pre}                skip_{tid}_{idx}: tryte = 0")
            result.append(f"{pre}        return 0")
            result.append(f"{pre}    1:")
            result.append(f"{pre}        return 0")
        else:
            mid = len(tids) // 2
            pivot = tids[mid]
            left = tids[:mid]
            right = tids[mid + 1:]
            result.append(f"{pre}match id <=> {pivot}:")
            if left:
                result.append(f"{pre}    -1:")
                result.extend(emit_text_tree(left, indent + 2))
            else:
                result.append(f"{pre}    -1:")
                result.append(f"{pre}        return 0")
            result.append(f"{pre}    0:")
            bs = unified[pivot]
            for idx, b in enumerate(bs):
                result.append(f"{pre}        match index <=> {idx}:")
                result.append(f"{pre}            0:")
                result.append(f"{pre}                return {b}")
                result.append(f"{pre}            -1:")
                result.append(f"{pre}                skip_{pivot}_{idx}: tryte = 0")
                result.append(f"{pre}            1:")
                result.append(f"{pre}                skip_{pivot}_{idx}: tryte = 0")
            result.append(f"{pre}        return 0")
            if right:
                result.append(f"{pre}    1:")
                result.extend(emit_text_tree(right, indent + 2))
            else:
                result.append(f"{pre}    1:")
                result.append(f"{pre}        return 0")
        return result

    lines.extend(emit_text_tree(sorted_tids))
    lines.append("")

    # Shared text_length (binary-search tree)
    lines.append("fn text_length(id: tryte) -> tryte:")

    def emit_len_tree(tids, indent=2):
        result = []
        pre = "    " * indent
        if not tids:
            result.append(f"{pre}return 0")
        elif len(tids) == 1:
            tid = tids[0]
            ln = len(unified[tid])
            result.append(f"{pre}match id <=> {tid}:")
            result.append(f"{pre}    -1:")
            result.append(f"{pre}        return 0")
            result.append(f"{pre}    0:")
            result.append(f"{pre}        return {ln}")
            result.append(f"{pre}    1:")
            result.append(f"{pre}        return 0")
        else:
            mid = len(tids) // 2
            pivot = tids[mid]
            left = tids[:mid]
            right = tids[mid + 1:]
            ln = len(unified[pivot])
            result.append(f"{pre}match id <=> {pivot}:")
            if left:
                result.append(f"{pre}    -1:")
                result.extend(emit_len_tree(left, indent + 2))
            else:
                result.append(f"{pre}    -1:")
                result.append(f"{pre}        return 0")
            result.append(f"{pre}    0:")
            result.append(f"{pre}        return {ln}")
            if right:
                result.append(f"{pre}    1:")
                result.extend(emit_len_tree(right, indent + 2))
            else:
                result.append(f"{pre}    1:")
                result.append(f"{pre}        return 0")
        return result

    lines.extend(emit_len_tree(sorted_tids))
    lines.append("")

    # Decimal functions from simple_call
    for fn_name in ['decimal_ones_byte', 'decimal_tens_byte']:
        body = extract_function_body(fixture_sources["simple_call"], fn_name)
        if body:
            lines.append(body)
            lines.append("")

    # ── Per-fixture entry functions ──
    for name in FIXTURES:
        src = fixture_sources[name]
        func_maps = fixture_map[name]
        entry_name, legacy_bufs, legacy_cursors, caps = FIXTURE_CONFIG[name]

        lines.append(f"fn {entry_name}() -> tryte:")
        for buf_name, cap in zip(legacy_bufs, caps):
            arr_body = ",".join("0" for _ in range(cap))
            lines.append(f"    mut {buf_name}: tryte[{cap}] = [{arr_body}]")
        for cursor_name in legacy_cursors:
            lines.append(f"    mut {cursor_name}: tryte = 0")
        lines.append("")

        # Extract legacy main body (skip buffer/cursor declarations)
        main_idx = src.find('fn main() -> tryte:')
        body = src[main_idx:]
        code_lines = []
        in_decl = True
        for src_line in body.split('\n'):
            stripped = src_line.strip()
            if not stripped:
                continue
            if in_decl and (stripped.startswith('mut buffer_') or stripped.startswith('mut cursor_') or stripped.startswith('#') or stripped.startswith('fn main') or stripped == ''):
                continue
            in_decl = False
            code_lines.append(stripped)

        for code_line in code_lines:
            if not code_line:
                continue

            new_line = code_line

            # Replace function calls with mapped IDs
            # Build pattern that matches any of the source functions
            func_names = "|".join(FIXTURE_SOURCE_FUNCS[name])

            def make_replacer(fixture_func_maps):
                def replace_byte_call(m):
                    fn = m.group(1)
                    old_id = int(m.group(2))
                    offset_arg = m.group(3)
                    mapping = fixture_func_maps.get(fn, {})
                    new_id = mapping.get(old_id, old_id)
                    return f'text_byte_at({new_id}, {offset_arg})'
                return replace_byte_call

            new_line = re.sub(
                r'(' + func_names + r')\((\d+),\s*(\w+)\)',
                make_replacer(func_maps),
                new_line
            )

            lines.append(f"    {new_line}")

        lines.append("")

    # main() - default entry
    lines.append("fn main() -> tryte:")
    lines.append("    return 0")
    lines.append("")

    return "\n".join(lines)


def main():
    sources = {}
    for name in FIXTURES:
        path = REPO_ROOT / LEGACY_PATHS[name]
        with open(path, encoding="utf-8") as f:
            sources[name] = f.read()
        print(f"Read {name}: {len(sources[name])} chars", file=sys.stderr)

    output = generate(sources)

    out_path = REPO_ROOT / "examples/self_hosting" / "assembly_renderer_generic_text.s3"
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(output)

    print(f"\nGenerated: {out_path}")
    print(f"  Lines: {output.count(chr(10))}")
    print(f"  Chars: {len(output)}")


if __name__ == "__main__":
    main()
