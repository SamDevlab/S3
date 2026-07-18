from __future__ import annotations

import hashlib
import subprocess
import sys
from pathlib import Path

import pytest

from bootstrap.s3 import assembly_program_text_adapter
from bootstrap.s3.assembly import (
    AssemblyBlock,
    AssemblyFunction,
    AssemblyInstruction,
    AssemblyMemoryObject,
    AssemblyOpcode,
    AssemblyParameter,
    AssemblyProgram,
    AssemblyType,
    parse_assembly,
)
from bootstrap.s3.assembly_program_text_adapter import (
    AssemblyProgramTextAdapter,
    AssemblyProgramTextAdapterError,
    render_first_program,
    render_sign_program,
    render_simple_call_program,
    render_supported_program,
)
from bootstrap.s3.assembly_text_renderer import AssemblyTextRenderer
from bootstrap.s3.diagnostics import SourceLocation
from bootstrap.s3.static_text import StaticTextDocument


REPO_ROOT = Path(__file__).resolve().parents[1]
FIRST_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "first.assembly.txt"
)
FIRST_ACTUAL_OUTPUT = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_actual"
    / "first.assembly.txt"
)
SIMPLE_CALL_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "simple_call.assembly.txt"
)
SIMPLE_CALL_ACTUAL_OUTPUT = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_actual"
    / "simple_call.assembly.txt"
)
SIGN_ASSEMBLY_GOLDEN = (
    REPO_ROOT / "tests" / "golden" / "inspect" / "sign.assembly.txt"
)
SIGN_ACTUAL_OUTPUT = (
    REPO_ROOT
    / "tests"
    / "golden"
    / "assembly_renderer_candidate_actual"
    / "sign.assembly.txt"
)
INSPECT_ASSEMBLY_GOLDENS = tuple(
    sorted((REPO_ROOT / "tests" / "golden" / "inspect").glob("*.assembly.txt"))
)


def _read_lf_normalized_golden_bytes(path: Path) -> bytes:
    return path.read_text(encoding="utf-8").encode("utf-8")


def _run_tool(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *args],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def _first_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                tuple((register, AssemblyType.TRYTE) for register in range(6)),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=10,
                                source=SourceLocation(35, 2, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TMOV,
                                (1, 0),
                                source=SourceLocation(24, 2, 5),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (2,),
                                immediate=4,
                                source=SourceLocation(53, 3, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TMOV,
                                (3, 2),
                                source=SourceLocation(42, 3, 5),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (4, 3),
                                source=SourceLocation(68, 4, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TADD,
                                (5, 1, 4),
                                source=SourceLocation(68, 4, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (5,),
                                source=SourceLocation(59, 4, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def _simple_call_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "add",
                AssemblyType.TRYTE,
                (
                    AssemblyParameter(0, AssemblyType.TRYTE),
                    AssemblyParameter(1, AssemblyType.TRYTE),
                ),
                ((2, AssemblyType.TRYTE),),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TADD,
                                (2, 0, 1),
                                source=SourceLocation(50, 2, 14),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(41, 2, 5),
                            ),
                        ),
                    ),
                ),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                tuple((register, AssemblyType.TRYTE) for register in range(3)),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=10,
                                source=SourceLocation(90, 5, 16),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (1,),
                                immediate=5,
                                source=SourceLocation(94, 5, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCALL,
                                (2, 0, 1),
                                callee="add",
                                source=SourceLocation(86, 5, 12),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(79, 5, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def _sign_program() -> AssemblyProgram:
    return AssemblyProgram(
        (
            AssemblyFunction(
                "sign",
                AssemblyType.TRIT,
                (AssemblyParameter(0, AssemblyType.TRYTE),),
                (
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRIT),
                    (3, AssemblyType.TRIT),
                    (4, AssemblyType.TRIT),
                    (5, AssemblyType.TRIT),
                    (6, AssemblyType.TRIT),
                ),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (1,),
                                immediate=0,
                                source=SourceLocation(51, 2, 21),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCMP,
                                (2, 0, 1),
                                source=SourceLocation(47, 2, 17),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TBR3,
                                (2,),
                                labels=(
                                    "switch_negative_0",
                                    "switch_neutral_1",
                                    "switch_positive_2",
                                ),
                                source=SourceLocation(35, 2, 5),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_negative_0",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (3,),
                                immediate=1,
                                source=SourceLocation(86, 4, 21),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (4, 3),
                                source=SourceLocation(85, 4, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (4,),
                                source=SourceLocation(78, 4, 13),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_neutral_1",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (5,),
                                immediate=0,
                                source=SourceLocation(119, 7, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (5,),
                                source=SourceLocation(112, 7, 13),
                            ),
                        ),
                    ),
                    AssemblyBlock(
                        "switch_positive_2",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (6,),
                                immediate=1,
                                source=SourceLocation(152, 10, 20),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (6,),
                                source=SourceLocation(145, 10, 13),
                            ),
                        ),
                    ),
                ),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRIT,
                (),
                (
                    (0, AssemblyType.TRYTE),
                    (1, AssemblyType.TRYTE),
                    (2, AssemblyType.TRIT),
                ),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TCONST,
                                (0,),
                                immediate=20,
                                source=SourceLocation(191, 13, 18),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TINV,
                                (1, 0),
                                source=SourceLocation(190, 13, 17),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TCALL,
                                (2, 1),
                                callee="sign",
                                source=SourceLocation(185, 13, 12),
                            ),
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (2,),
                                source=SourceLocation(178, 13, 5),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )


def _track_supported_program_delegation(
    monkeypatch: pytest.MonkeyPatch,
) -> list[AssemblyProgram]:
    calls: list[AssemblyProgram] = []
    original = AssemblyProgramTextAdapter.render_supported_program

    def spy(
        self: AssemblyProgramTextAdapter,
        program: AssemblyProgram,
    ) -> StaticTextDocument:
        calls.append(program)
        return original(self, program)

    monkeypatch.setattr(
        AssemblyProgramTextAdapter,
        "render_supported_program",
        spy,
    )
    return calls


def test_render_supported_program_matches_first_fixture_outputs() -> None:
    document = render_supported_program(_first_program())
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)
    actual = FIRST_ACTUAL_OUTPUT.read_bytes()

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.utf8_bytes == actual
    assert document.byte_count == 441
    assert document.line_count == 18
    assert (
        document.sha256
        == "46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67"
    )
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_supported_program_matches_simple_call_fixture_outputs() -> None:
    document = render_supported_program(_simple_call_program())
    expected = _read_lf_normalized_golden_bytes(SIMPLE_CALL_ASSEMBLY_GOLDEN)
    actual = SIMPLE_CALL_ACTUAL_OUTPUT.read_bytes()

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.utf8_bytes == actual
    assert document.byte_count == 448
    assert document.line_count == 21
    assert (
        document.sha256
        == "d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f"
    )
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_supported_program_matches_sign_fixture_outputs() -> None:
    document = render_supported_program(_sign_program())
    expected = _read_lf_normalized_golden_bytes(SIGN_ASSEMBLY_GOLDEN)
    actual = SIGN_ACTUAL_OUTPUT.read_bytes()

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.utf8_bytes == actual
    assert document.byte_count == 946
    assert document.line_count == 36
    assert (
        document.sha256
        == "c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9"
    )
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_supported_program_matches_all_inspect_assembly_golden_outputs() -> None:
    assert {path.name for path in INSPECT_ASSEMBLY_GOLDENS} == {
        "assembly_renderer_stub.assembly.txt",
        "first.assembly.txt",
        "sign.assembly.txt",
        "simple_call.assembly.txt",
    }

    for golden in INSPECT_ASSEMBLY_GOLDENS:
        expected = _read_lf_normalized_golden_bytes(golden)
        program = parse_assembly(golden.read_text(encoding="utf-8"))
        document = render_supported_program(program)

        assert document.utf8_bytes == expected
        assert document.text.endswith("\n")
        assert "\r\n" not in document.text
        assert b"\r\n" not in document.utf8_bytes


def test_render_first_program_delegates_to_supported_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = _first_program()
    calls = _track_supported_program_delegation(monkeypatch)

    document = render_first_program(program)

    assert calls == [program]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        FIRST_ASSEMBLY_GOLDEN
    )


def test_render_simple_call_program_delegates_to_supported_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = _simple_call_program()
    calls = _track_supported_program_delegation(monkeypatch)

    document = render_simple_call_program(program)

    assert calls == [program]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIMPLE_CALL_ASSEMBLY_GOLDEN
    )


def test_render_sign_program_delegates_to_supported_program(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    program = _sign_program()
    calls = _track_supported_program_delegation(monkeypatch)

    document = render_sign_program(program)

    assert calls == [program]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIGN_ASSEMBLY_GOLDEN
    )


def test_render_supported_program_preserves_program_without_functions() -> None:
    document = render_supported_program(AssemblyProgram(()))

    assert document.text == ".s3asm 0.5.0\n\n\n"
    assert document.utf8_bytes == b".s3asm 0.5.0\n\n\n"
    assert document.text.endswith("\n")


def test_render_supported_program_renders_memory_objects() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE),),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TRET,
                                (0,),
                                source=SourceLocation(0, 1, 1),
                            ),
                        ),
                    ),
                ),
                (
                    AssemblyMemoryObject(
                        0,
                        AssemblyType.TRYTE,
                        1,
                        mutable=False,
                    ),
                ),
            ),
        )
    )

    document = render_supported_program(program)

    assert (
        document.text
        == ".s3asm 0.5.0\n"
        "\n"
        ".function main -> tryte\n"
        "    .register r0, tryte\n"
        "    .memory m0, tryte, 1, immutable\n"
        ".label entry\n"
        "    TRET   r0 ; source=1:1:0\n"
        ".end\n"
    )


def test_render_supported_program_preserves_empty_blocks() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                (),
                (AssemblyBlock("entry", ()),),
            ),
        )
    )

    document = render_supported_program(program)

    assert (
        document.text
        == ".s3asm 0.5.0\n"
        "\n"
        ".function main -> tryte\n"
        ".label entry\n"
        ".end\n"
    )


def test_render_supported_program_rejects_unsupported_opcode() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                (),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                "TNOPE",  # type: ignore[arg-type]
                                (),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )

    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="supported adapter does not support opcode TNOPE",
    ):
        render_supported_program(program)


def test_render_supported_program_covers_current_instruction_forms_without_source() -> None:
    source = (
        ".s3asm 0.5.0\n"
        "\n"
        ".function helper -> tryte\n"
        "    .register r0, tryte\n"
        ".label entry\n"
        "    TRET   r0\n"
        ".end\n"
        "\n"
        ".function main -> tryte\n"
        "    .register r0, tryte\n"
        "    .register r1, tryte\n"
        "    .register r2, tryte\n"
        "    .register r3, tryte\n"
        "    .register r4, tryte\n"
        "    .register r5, tryte\n"
        "    .memory m0, tryte, 2, mutable\n"
        ".label entry\n"
        "    TCONST r0, 0\n"
        "    TCONST r1, 1\n"
        "    TSTORE m0, r0, r1\n"
        "    TLOAD  r2, m0, r0\n"
        "    TMIN   r3, r1, r2\n"
        "    TMAX   r4, r1, r2\n"
        "    TCALL  r5, helper\n"
        "    TJMP   done\n"
        ".label done\n"
        "    TRET   r5\n"
        ".end\n"
    )
    program = parse_assembly(source)
    document = render_supported_program(program)

    assert document.text == source
    assert b"\r\n" not in document.utf8_bytes
    assert document.utf8_bytes.endswith(b"\n")


def test_render_supported_program_rejects_invalid_memory_instruction_shape() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                ((0, AssemblyType.TRYTE), (1, AssemblyType.TRYTE)),
                (
                    AssemblyBlock(
                        "entry",
                        (
                            AssemblyInstruction(
                                AssemblyOpcode.TLOAD,
                                (0, 1),
                            ),
                        ),
                    ),
                ),
            ),
        )
    )

    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="supported adapter expects TLOAD memory object",
    ):
        render_supported_program(program)


def test_render_first_program_still_requires_fixture_source_metadata() -> None:
    original = _first_program()
    function = original.functions[0]
    block = function.blocks[0]
    instructions = (
        AssemblyInstruction(
            block.instructions[0].opcode,
            block.instructions[0].registers,
            immediate=block.instructions[0].immediate,
        ),
        *block.instructions[1:],
    )
    program = AssemblyProgram(
        (
            AssemblyFunction(
                function.name,
                function.return_type,
                function.parameters,
                function.register_types,
                (AssemblyBlock(block.label, instructions),),
            ),
        )
    )

    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="first adapter expects source metadata for TCONST",
    ):
        render_first_program(program)


def test_render_first_program_matches_lf_normalized_inspect_golden() -> None:
    document = render_first_program(_first_program())
    expected = _read_lf_normalized_golden_bytes(FIRST_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 441
    assert document.line_count == 18
    assert (
        document.sha256
        == "46ebd2aef715d7a7e9f7ada01ca844b8ae23494ff6a5333f78c75db2eaca2f67"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_first_program_matches_candidate_actual_output() -> None:
    document = AssemblyProgramTextAdapter().render_first_program(_first_program())
    actual = FIRST_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 441
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_render_first_program_uses_renderer_core(monkeypatch) -> None:
    calls: list[str] = []

    class SpyRenderer(AssemblyTextRenderer):
        def __init__(self) -> None:
            calls.append("init")
            super().__init__()

        def build(self) -> StaticTextDocument:
            calls.append("build")
            return super().build()

    monkeypatch.setattr(
        assembly_program_text_adapter,
        "AssemblyTextRenderer",
        SpyRenderer,
    )

    document = render_first_program(_first_program())

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        FIRST_ASSEMBLY_GOLDEN
    )


def test_render_first_program_rejects_non_first_subset() -> None:
    program = AssemblyProgram(
        (
            AssemblyFunction(
                "add",
                AssemblyType.TRYTE,
                (),
                (),
                (),
            ),
            AssemblyFunction(
                "main",
                AssemblyType.TRYTE,
                (),
                (),
                (),
            ),
        )
    )

    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="first adapter expects exactly one function",
    ):
        render_first_program(program)


def test_render_simple_call_program_matches_lf_normalized_inspect_golden() -> None:
    document = render_simple_call_program(_simple_call_program())
    expected = _read_lf_normalized_golden_bytes(SIMPLE_CALL_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 448
    assert document.line_count == 21
    assert (
        document.sha256
        == "d6de00c8c50618bcc8f3a458267eb8590956a9451980084b1add2f59d3267c0f"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_simple_call_program_matches_candidate_actual_output() -> None:
    document = AssemblyProgramTextAdapter().render_simple_call_program(
        _simple_call_program()
    )
    actual = SIMPLE_CALL_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 448
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_render_simple_call_program_uses_renderer_core(monkeypatch) -> None:
    calls: list[str] = []

    class SpyRenderer(AssemblyTextRenderer):
        def __init__(self) -> None:
            calls.append("init")
            super().__init__()

        def build(self) -> StaticTextDocument:
            calls.append("build")
            return super().build()

    monkeypatch.setattr(
        assembly_program_text_adapter,
        "AssemblyTextRenderer",
        SpyRenderer,
    )

    document = render_simple_call_program(_simple_call_program())

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIMPLE_CALL_ASSEMBLY_GOLDEN
    )


def test_render_simple_call_program_rejects_non_simple_call_subset() -> None:
    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="simple_call adapter expects exactly two functions",
    ):
        render_simple_call_program(_first_program())


def test_render_sign_program_matches_lf_normalized_inspect_golden() -> None:
    document = render_sign_program(_sign_program())
    expected = _read_lf_normalized_golden_bytes(SIGN_ASSEMBLY_GOLDEN)

    assert isinstance(document, StaticTextDocument)
    assert document.utf8_bytes == expected
    assert document.byte_count == 946
    assert document.line_count == 36
    assert (
        document.sha256
        == "c077d2c49639b1a033505ec8c1ba1c60c78242e6e09c43f60a8aa5ed8b49e2d9"
    )
    assert document.sha256 == hashlib.sha256(expected).hexdigest()
    assert document.text.endswith("\n")
    assert "\r\n" not in document.text
    assert b"\r\n" not in document.utf8_bytes


def test_render_sign_program_matches_candidate_actual_output() -> None:
    document = AssemblyProgramTextAdapter().render_sign_program(_sign_program())
    actual = SIGN_ACTUAL_OUTPUT.read_bytes()

    assert actual == document.utf8_bytes
    assert len(actual) == 946
    assert hashlib.sha256(actual).hexdigest() == document.sha256
    assert b"\r\n" not in actual
    assert actual.endswith(b"\n")


def test_render_sign_program_uses_renderer_core(monkeypatch) -> None:
    calls: list[str] = []

    class SpyRenderer(AssemblyTextRenderer):
        def __init__(self) -> None:
            calls.append("init")
            super().__init__()

        def build(self) -> StaticTextDocument:
            calls.append("build")
            return super().build()

    monkeypatch.setattr(
        assembly_program_text_adapter,
        "AssemblyTextRenderer",
        SpyRenderer,
    )

    document = render_sign_program(_sign_program())

    assert calls == ["init", "build"]
    assert document.utf8_bytes == _read_lf_normalized_golden_bytes(
        SIGN_ASSEMBLY_GOLDEN
    )


def test_render_sign_program_rejects_non_sign_subset() -> None:
    with pytest.raises(
        AssemblyProgramTextAdapterError,
        match="sign adapter expects functions 'sign' and 'main'",
    ):
        render_sign_program(_simple_call_program())


def test_adapter_paths_keep_available_comparisons_passed() -> None:
    completed = _run_tool(
        "tools/compare_assembly_renderer.py",
        "--candidate-compare-available",
    )

    assert completed.returncode == 0
    assert "first expected=tests/golden/inspect/first.assembly.txt" in completed.stdout
    assert (
        "simple_call expected=tests/golden/inspect/simple_call.assembly.txt"
        in completed.stdout
    )
    assert "sign expected=tests/golden/inspect/sign.assembly.txt" in completed.stdout
    assert "available comparisons: 3" in completed.stdout
    assert "passed comparisons: 3" in completed.stdout


def test_adapter_paths_keep_compare_check_blocked() -> None:
    completed = _run_tool("tools/compare_assembly_renderer.py", "--check")

    assert completed.returncode == 1
    assert "S3 Assembly renderer comparison check: blocked" in completed.stdout
    assert "actual outputs: passed" in completed.stdout
    assert "available comparisons: passed" in completed.stdout
    assert "renderer implementation: not_implemented" in completed.stdout
    assert "global check: blocked" in completed.stdout
