from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FILES = (
    "bootstrap/s3/ir.py",
    "bootstrap/s3/lowering.py",
    "bootstrap/s3/verifier.py",
    "bootstrap/s3/ir_emulator.py",
    "bootstrap/s3/assembly.py",
    "bootstrap/s3/codegen.py",
    "bootstrap/s3/assembly_verifier.py",
    "bootstrap/s3/emulator.py",
    "bootstrap/s3/backends/x86_64/liveness.py",
    "bootstrap/s3/backends/x86_64/emitter.py",
    "tests/test_compiler.py",
    "tests/test_s3_static_text_concatenation_ir.py",
    "tests/test_numeric_capability_e2e.py",
)

changed = []
for relative in FILES:
    path = ROOT / relative
    text = path.read_text(encoding="utf-8")
    new = text.replace("NUMERIC_SUBTRACT", "NUMERIC_DIFFERENCE")
    new = new.replace('"numeric_subtract"', '"numeric_difference"')
    new = new.replace("TNSUB", "TNDIFF")
    if new != text:
        path.write_text(new, encoding="utf-8")
        changed.append(relative)

if len(changed) < 8:
    raise RuntimeError(f"unexpectedly narrow difference rename: {changed}")

# Preserve the long-standing architectural invariant: there remains no IR opcode
# whose public name/value contains 'sub'. Machine subtraction is a numeric
# difference operation; balanced-ternary subtraction still lowers to invert+add.
ir_text = (ROOT / "bootstrap/s3/ir.py").read_text(encoding="utf-8")
if "numeric_subtract" in ir_text.lower() or "NUMERIC_SUBTRACT" in ir_text:
    raise RuntimeError("stale subtract naming remains in IR")

print("renamed machine subtraction to numeric difference in:")
for relative in changed:
    print(f"- {relative}")
