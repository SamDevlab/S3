from __future__ import annotations

from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parents[1]
runpy.run_path(str(Path(__file__).with_name("_closure_132_apply_v2.py")), run_name="__main__")


def replace_once(path: str, old: str, new: str) -> None:
    target = ROOT / path
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"{path}: expected exactly one anchor, got {count}")
    target.write_text(text.replace(old, new, 1), encoding="utf-8")


replace_once(
    "bootstrap/s3/backends/x86_64/layout.py",
    '''def _element_size(type_name: AssemblyType) -> int:
    if type_name is AssemblyType.TRIT:
        return 1
    if type_name is AssemblyType.TRYTE:
        return 2
    if type_name is AssemblyType.STRING:
        return 8
    raise NativeBackendError(f"unsupported memory element type {type_name!r}")
''',
    '''def _element_size(type_name: AssemblyType) -> int:
    if type_name is AssemblyType.TRIT:
        return 1
    if type_name is AssemblyType.TRYTE:
        return 2
    if type_name in {AssemblyType.I64, AssemblyType.F64, AssemblyType.STRING}:
        return 8
    raise NativeBackendError(f"unsupported memory element type {type_name!r}")
''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/emitter.py",
    '''            if type_name is not AssemblyType.STRING:
                overflow = self._overflow_failure(type_name, "r11")
                lines.extend(self._range_check(type_name, "r11", overflow))
''',
    '''            if type_name in {AssemblyType.TRIT, AssemblyType.TRYTE}:
                overflow = self._overflow_failure(type_name, "r11")
                lines.extend(self._range_check(type_name, "r11", overflow))
''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/emitter.py",
    '''        if memory.element_type is AssemblyType.STRING:
            load = "mov rax, qword ptr"
        elif memory.element_size == 1:
            load = "movsx rax, byte ptr"
        else:
            load = "movsx rax, word ptr"
''',
    '''        if memory.element_size == 8:
            load = "mov rax, qword ptr"
        elif memory.element_size == 1:
            load = "movsx rax, byte ptr"
        else:
            load = "movsx rax, word ptr"
''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/emitter.py",
    '''        if memory.element_type is not AssemblyType.STRING:
            overflow = self._overflow_failure(memory.element_type, "r10")
            lines.extend(self._range_check(memory.element_type, "r10", overflow))
''',
    '''        if memory.element_type in {AssemblyType.TRIT, AssemblyType.TRYTE}:
            overflow = self._overflow_failure(memory.element_type, "r10")
            lines.extend(self._range_check(memory.element_type, "r10", overflow))
''',
)

replace_once(
    "bootstrap/s3/backends/x86_64/emitter.py",
    '''        if memory.element_type is AssemblyType.STRING:
            source = "r10"
            size = "qword"
        elif memory.element_size == 1:
            source = "r10b"
            size = "byte"
        else:
            source = "r10w"
            size = "word"
''',
    '''        if memory.element_size == 8:
            source = "r10"
            size = "qword"
        elif memory.element_size == 1:
            source = "r10b"
            size = "byte"
        else:
            source = "r10w"
            size = "word"
''',
)

print("M1.32 native machine-memory codemod applied successfully")
