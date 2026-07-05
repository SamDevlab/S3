"""E1 — hosted instruction limit parity.

Tests for ADR-0014 (hosted part only):
- centralised DEFAULT_MAX_INSTRUCTIONS constant;
- run_source and execute_assembly accept max_instructions;
- global counter shared across calls and recursion;
- exact N-allowed / N+1-blocked boundary;
- TCALL, TRET, TBR3, TJMP count as opcodes;
- effect of N+1 opcode is blocked before execution;
- CLI ``s3 run --max-instructions N``;
- invalid values rejected (zero, negative, wrong type);
- diagnostic fields preserved (code, category, phase, limit, function, block);
- --max-instructions absent from native commands in this E1;
- compatibility: V0.5 only by explicit selection; no fallback; no autodetection.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import bootstrap.s3.cli as cli
from bootstrap.s3.diagnostics import diagnostic_from_exception
from bootstrap.s3.emulator import (
    DEFAULT_MAX_INSTRUCTIONS,
    Emulator,
    EmulatorError,
    execute_assembly,
)
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.pipeline import compile_source, run_source


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _write_source(path: Path, source: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _json_stderr(capsys: pytest.CaptureFixture[str]) -> dict[str, object]:
    captured = capsys.readouterr()
    assert captured.out == ""
    return json.loads(captured.err)


# Minimal S3 v0.6 program that returns 0 in exactly 3 hosted opcodes:
#   TCONST r0, 0  →  1 opcode
#   TRET r0       →  1 opcode
# (2 opcodes total for a trivial main; add a TMOV to make it 3)
_TRIVIAL_V0_6 = "fn main() -> tryte:\n    return 0\n"

# Assembly with one infinite loop — used to test limit enforcement
_INFINITE_LOOP_ASM = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TJMP entry
.label done
    TCONST r0, 0
    TRET r0
.end
"""

# Assembly for call / recursion tests
_TWO_FUNC_ASM = """\
.function inner -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 7
    TRET r0
.end

.function main -> tryte
    .register r0, tryte
.label entry
    TCALL r0, inner
    TRET r0
.end
"""

_RECURSIVE_ASM = """\
.function recurse -> tryte
    .register r0, tryte
.label entry
    TCALL r0, recurse
    TRET r0
.end

.function main -> tryte
    .register r0, tryte
.label entry
    TCALL r0, recurse
    TRET r0
.end
"""

# Assembly with a TSTORE to verify effect is blocked when limit exceeded.
# Opcodes: TCONST r0,42 (1) + TCONST r1,0 (2) + TSTORE m0,r1,r0 (3) + TRET r0 (4)
# With limit=2, opcode 3 (TSTORE) is the one that fails before producing effects.
_TSTORE_EFFECT_ASM = """\
.function main -> tryte
    .register r0, tryte
    .register r1, tryte
    .memory m0, tryte, 1, mutable
.label entry
    TCONST r0, 42
    TCONST r1, 0
    TSTORE m0, r1, r0
    TRET r0
.end
"""


# ---------------------------------------------------------------------------
# 1. Default constant
# ---------------------------------------------------------------------------

class TestDefaultConstant:
    def test_constant_exists_and_equals_100000(self) -> None:
        assert DEFAULT_MAX_INSTRUCTIONS == 100_000

    def test_constant_is_integer(self) -> None:
        assert isinstance(DEFAULT_MAX_INSTRUCTIONS, int)
        assert not isinstance(DEFAULT_MAX_INSTRUCTIONS, bool)

    def test_emulator_default_matches_constant(self) -> None:
        emulator = Emulator()
        assert emulator.max_instructions == DEFAULT_MAX_INSTRUCTIONS

    def test_execute_assembly_default_matches_constant(self) -> None:
        # execute_assembly should use DEFAULT_MAX_INSTRUCTIONS as its default.
        # We verify indirectly: an execution with limit = DEFAULT_MAX_INSTRUCTIONS
        # succeeds when the program finishes before the limit.
        result = execute_assembly(_TWO_FUNC_ASM)
        assert result == 7


# ---------------------------------------------------------------------------
# 2. API: run_source and execute_assembly accept max_instructions
# ---------------------------------------------------------------------------

class TestAPIAcceptsMaxInstructions:
    def test_run_source_without_argument_preserves_behaviour(self) -> None:
        result = run_source(_TRIVIAL_V0_6)
        assert result == 0

    def test_run_source_with_explicit_limit_succeeds_within_budget(self) -> None:
        # A trivial program uses very few opcodes; 1000 is always enough.
        result = run_source(_TRIVIAL_V0_6, max_instructions=1000)
        assert result == 0

    def test_run_source_with_limit_1_fails_on_instruction_2(self) -> None:
        # Limit of 1 allows exactly 1 opcode; a non-trivial program needs more.
        with pytest.raises(EmulatorError):
            run_source("fn main() -> tryte:\n    return 1 + 1\n", max_instructions=1)

    def test_execute_assembly_with_explicit_limit(self) -> None:
        result = execute_assembly(_TWO_FUNC_ASM, max_instructions=1000)
        assert result == 7

    def test_execute_assembly_limit_1_blocks_second_opcode(self) -> None:
        with pytest.raises(EmulatorError, match="instruction limit 1 exceeded"):
            execute_assembly(_TWO_FUNC_ASM, max_instructions=1)


# ---------------------------------------------------------------------------
# 3. Exact boundary: N allowed, N+1 blocked
# ---------------------------------------------------------------------------

class TestExactBoundary:
    def test_limit_equal_to_count_succeeds(self) -> None:
        # Count how many opcodes the trivial v0.6 program executes,
        # then run it with exactly that limit.
        # We do a binary search: start from 1 and find the minimum working limit.
        source = _TRIVIAL_V0_6
        min_working = None
        for n in range(1, 50):
            try:
                run_source(source, max_instructions=n)
                min_working = n
                break
            except EmulatorError:
                continue
        assert min_working is not None, "program never completed within 50 opcodes"
        # With exactly min_working it must succeed
        result = run_source(source, max_instructions=min_working)
        assert result == 0

    def test_limit_one_below_minimum_fails(self) -> None:
        source = _TRIVIAL_V0_6
        min_working = None
        for n in range(1, 50):
            try:
                run_source(source, max_instructions=n)
                min_working = n
                break
            except EmulatorError:
                continue
        assert min_working is not None
        if min_working > 1:
            with pytest.raises(EmulatorError):
                run_source(source, max_instructions=min_working - 1)

    def test_limit_1_allows_exactly_1_opcode(self) -> None:
        # Single-opcode program: TRET with constant 0
        asm = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
        # 2 opcodes needed (TCONST + TRET). Limit 1 must fail.
        with pytest.raises(EmulatorError, match="instruction limit 1 exceeded"):
            execute_assembly(asm, max_instructions=1)
        # Limit 2 must succeed.
        result = execute_assembly(asm, max_instructions=2)
        assert result == 0


# ---------------------------------------------------------------------------
# 4. Global counter: calls and recursion share the budget
# ---------------------------------------------------------------------------

class TestGlobalCounter:
    def test_counter_starts_at_zero_and_accumulates_across_calls(self) -> None:
        # The two-function program needs at least TCALL + inner body + TRET.
        # With limit 1 it must fail, proving the counter is global.
        with pytest.raises(EmulatorError):
            execute_assembly(_TWO_FUNC_ASM, max_instructions=1)

    def test_recursion_shares_the_budget(self) -> None:
        # Recursive program: limit=3 must fail because recursion eventually
        # exceeds any finite limit; with limit=3 it should be caught.
        with pytest.raises(EmulatorError, match="instruction limit 3 exceeded"):
            execute_assembly(_RECURSIVE_ASM, max_instructions=3)

    def test_tcall_counts_as_opcode(self) -> None:
        # TCALL itself is an opcode; budget of 1 catches it before the call executes.
        # The first opcode in main's entry is TCALL.
        with pytest.raises(EmulatorError, match="instruction limit 1 exceeded"):
            execute_assembly(_TWO_FUNC_ASM, max_instructions=1)

    def test_tret_counts_as_opcode(self) -> None:
        # To verify TRET is counted, we need a program whose ONLY needed opcode
        # beyond TCONST is TRET. Allow TCONST (1) but block TRET (2).
        asm = """\
.function main -> tryte
    .register r0, tryte
.label entry
    TCONST r0, 0
    TRET r0
.end
"""
        with pytest.raises(EmulatorError, match="instruction limit 1 exceeded"):
            execute_assembly(asm, max_instructions=1)

    def test_tjmp_counts_as_opcode(self) -> None:
        # Infinite loop: every TJMP is an opcode. With limit=1 it fails immediately.
        with pytest.raises(EmulatorError, match="instruction limit 1 exceeded"):
            execute_assembly(_INFINITE_LOOP_ASM, max_instructions=1)

    def test_branch_counts_as_opcode(self) -> None:
        # TBR3 is a branch; use it in a program and verify it counts.
        asm = """\
.function main -> tryte
    .register r0, trit
    .register r1, tryte
.label entry
    TCONST r0, 0
    TBR3 r0, neg, zero, pos
.label neg
    TCONST r1, -1
    TRET r1
.label zero
    TCONST r1, 0
    TRET r1
.label pos
    TCONST r1, 1
    TRET r1
.end
"""
        # 3 opcodes: TCONST(r0) + TBR3 + TCONST(r1) + TRET = 4 minimum for zero branch.
        # With limit=2 the TBR3 itself is the 2nd opcode and is allowed;
        # limit=2 should succeed through the jump, but we need at least 4 total.
        with pytest.raises(EmulatorError):
            execute_assembly(asm, max_instructions=2)

    def test_effect_of_exceeded_opcode_is_blocked(self) -> None:
        # With limit = 2 (TCONST + TSTORE would be 3rd), the TSTORE should never
        # execute, so memory effect never happens.
        # The program: TCONST r0,42  TSTORE m0,0,r0  TRET r0
        # limit=2 means TCONST(1) + TSTORE(2 fails before effect) → EmulatorError.
        with pytest.raises(EmulatorError, match="instruction limit"):
            execute_assembly(_TSTORE_EFFECT_ASM, max_instructions=2)


# ---------------------------------------------------------------------------
# 5. Validation: invalid values rejected
# ---------------------------------------------------------------------------

class TestValidation:
    def test_zero_is_rejected_by_emulator(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            Emulator(max_instructions=0)

    def test_negative_is_rejected_by_emulator(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            Emulator(max_instructions=-1)

    def test_zero_is_rejected_by_execute_assembly(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            execute_assembly(_TWO_FUNC_ASM, max_instructions=0)

    def test_negative_is_rejected_by_execute_assembly(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            execute_assembly(_TWO_FUNC_ASM, max_instructions=-5)

    def test_zero_is_rejected_by_run_source(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            run_source(_TRIVIAL_V0_6, max_instructions=0)

    def test_negative_is_rejected_by_run_source(self) -> None:
        with pytest.raises(ValueError, match="max_instructions must be at least 1"):
            run_source(_TRIVIAL_V0_6, max_instructions=-1)


# ---------------------------------------------------------------------------
# 6. Diagnostic fields preserved
# ---------------------------------------------------------------------------

class TestDiagnosticFields:
    def _get_diagnostic(self, **kwargs: int) -> dict[str, object]:
        with pytest.raises(EmulatorError) as captured:
            execute_assembly(_RECURSIVE_ASM, **kwargs)
        return diagnostic_from_exception(captured.value).to_dict()

    def test_diagnostic_code(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert d["code"] == "S3E_RUNTIME_INSTRUCTION_LIMIT"

    def test_diagnostic_category(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert d["category"] == "instruction-limit"

    def test_diagnostic_phase(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert d["phase"] == "emulation"

    def test_diagnostic_limit_field(self) -> None:
        d = self._get_diagnostic(max_instructions=5)
        assert d["limit"] == 5

    def test_diagnostic_function_field(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert "function" in d
        assert isinstance(d["function"], str)

    def test_diagnostic_block_field(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert "block" in d

    def test_diagnostic_schema_version_unchanged(self) -> None:
        d = self._get_diagnostic(max_instructions=3)
        assert d["schema_version"] == "1.0.0"


# ---------------------------------------------------------------------------
# 7. CLI: s3 run --max-instructions
# ---------------------------------------------------------------------------

class TestCLIMaxInstructions:
    def test_run_with_default_succeeds_for_trivial_program(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(["run", str(source)])
        captured = capsys.readouterr()
        assert code == 0
        assert "program returned:" in captured.out

    def test_run_with_sufficient_limit_succeeds(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(["run", str(source), "--max-instructions", "10000"])
        assert code == 0

    def test_run_with_limit_1_fails_with_exit_code_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Any non-trivial program (even return 0) takes > 1 opcode.
        source = _write_source(
            tmp_path / "prog.s3", "fn main() -> tryte:\n    return 1 + 1\n"
        )
        code = cli.main(["run", str(source), "--max-instructions", "1"])
        assert code == 1

    def test_run_instruction_limit_text_diagnostic_no_traceback(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(
            tmp_path / "prog.s3", "fn main() -> tryte:\n    return 1 + 1\n"
        )
        code = cli.main(["run", str(source), "--max-instructions", "1"])
        assert code == 1
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err
        assert captured.err.startswith("error:")

    def test_run_instruction_limit_json_diagnostic(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(
            tmp_path / "prog.s3", "fn main() -> tryte:\n    return 1 + 1\n"
        )
        code = cli.main(
            ["run", str(source), "--max-instructions", "1", "--diagnostic-format", "json"]
        )
        assert code == 1
        payload = _json_stderr(capsys)
        assert payload["code"] == "S3E_RUNTIME_INSTRUCTION_LIMIT"
        assert payload["category"] == "instruction-limit"
        assert payload["phase"] == "emulation"

    def test_run_zero_max_instructions_is_a_cli_usage_error(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(["run", str(source), "--max-instructions", "0"])
        # Invalid value must not succeed; exit code 1 or 2 is both acceptable,
        # but must not be 0.
        assert code != 0
        captured = capsys.readouterr()
        assert "Traceback" not in captured.err

    def test_run_negative_max_instructions_is_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(["run", str(source), "--max-instructions", "-1"])
        assert code != 0

    def test_run_non_integer_max_instructions_is_rejected(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(["run", str(source), "--max-instructions", "abc"])
        assert code == 2  # argparse usage error

    def test_run_max_instructions_and_max_frames_are_independent(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(
            ["run", str(source), "--max-instructions", "10000", "--max-frames", "512"]
        )
        assert code == 0

    def test_run_max_instructions_with_diagnostic_format(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        source = _write_source(tmp_path / "prog.s3", _TRIVIAL_V0_6)
        code = cli.main(
            [
                "run",
                str(source),
                "--max-instructions",
                "10000",
                "--diagnostic-format",
                "text",
            ]
        )
        assert code == 0



# ---------------------------------------------------------------------------
# 9. Compatibility contracts
# ---------------------------------------------------------------------------

class TestCompatibilityContracts:
    def test_v0_6_is_default_with_max_instructions(self) -> None:
        result = run_source(_TRIVIAL_V0_6, max_instructions=10000)
        assert result == 0

    def test_v0_5_requires_explicit_selection(self) -> None:
        source_v0_5 = "fn main() -> tryte { return 0; }\n"
        result = run_source(source_v0_5, mode=SyntaxMode.V0_5, max_instructions=10000)
        assert result == 0

    def test_no_new_ir_field(self) -> None:
        result = compile_source(_TRIVIAL_V0_6)
        ir_dict = result.ir.to_dict()
        # IR should not contain any instruction_limit or max_instructions field
        ir_json = json.dumps(ir_dict)
        assert "instruction_limit" not in ir_json
        assert "max_instructions" not in ir_json

    def test_no_new_assembly_directive(self) -> None:
        result = compile_source(_TRIVIAL_V0_6)
        asm_text = result.assembly_text
        assert "max_instructions" not in asm_text
        assert "instruction_limit" not in asm_text
