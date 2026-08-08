"""Tests for the deterministic physical register allocator on S3 Assembly."""

from __future__ import annotations

import pytest

from bootstrap.s3.assembly import parse_assembly
from bootstrap.s3.backends.x86_64.allocation import analyze_allocation
from bootstrap.s3.backends.x86_64.registers import INITIAL_ALLOCATABLE_REGISTERS


def _get_first_func_allocation(source: str):
    program = parse_assembly(source)
    func = program.functions[0]
    return func, analyze_allocation(func)


def test_single_virtual_to_rbx() -> None:
    # 1. único virtual → rbx
    source = """
    .function main -> tryte
        .register r0, tryte
    .label entry
        TCONST r0, 42
        TRET r0
    .end
    """
    _, plan = _get_first_func_allocation(source)
    assert plan.physical_register(0) == "rbx"


def test_two_non_interfering_share_rbx() -> None:
    # 2. dois não interferentes → podem compartilhar rbx
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 5
        TMOV r1, r0
        TRET r1
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # They don't overlap in live range, so they can share rbx
    assert plan.physical_register(0) == "rbx"
    assert plan.physical_register(1) == "rbx"


def test_two_interfering_distinct_phys() -> None:
    # 3. dois interferentes → físicos distintos
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TADD r2, r0, r1
        TRET r2
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # Both r0 and r1 are live simultaneously before TADD
    assert plan.physical_register(0) != plan.physical_register(1)
    assert plan.physical_register(0) in INITIAL_ALLOCATABLE_REGISTERS
    assert plan.physical_register(1) in INITIAL_ALLOCATABLE_REGISTERS


def test_clique_of_five() -> None:
    # 4. clique de cinco → todos físicos
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
        .register r4, tryte
        .register r5, tryte
    .label entry
        TCONST r0, 1
        TCONST r1, 2
        TCONST r2, 3
        TCONST r3, 4
        TCONST r4, 5
        TADD r5, r0, r1
        TADD r5, r5, r2
        TADD r5, r5, r3
        TADD r5, r5, r4
        TRET r5
    .end
    """
    _, plan = _get_first_func_allocation(source)
    allocated = [plan.physical_register(i) for i in range(5)]
    assert None not in allocated
    assert len(set(allocated)) == 5
    assert set(allocated) == set(INITIAL_ALLOCATABLE_REGISTERS)


def test_clique_of_six_spill() -> None:
    # 5. clique de seis → exatamente um STACK
    # 6. deterministic spill choice
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
        .register r4, tryte
        .register r5, tryte
        .register r6, tryte
    .label entry
        TCONST r0, 1
        TCONST r1, 2
        TCONST r2, 3
        TCONST r3, 4
        TCONST r4, 5
        TCONST r5, 6
        TADD r6, r0, r1
        TADD r6, r6, r2
        TADD r6, r6, r3
        TADD r6, r6, r4
        TADD r6, r6, r5
        TRET r6
    .end
    """
    _, plan = _get_first_func_allocation(source)
    allocated = [plan.physical_register(i) for i in range(6)]
    # Exactly one must be None (spilled to STACK)
    assert allocated.count(None) == 1
    assert len(set(allocated) - {None}) == 5


def test_branch_exclusive_registers() -> None:
    # 7. branch-exclusive values podem compartilhar físico
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
    .label entry
        TCONST r0, 0
        TBR3 r0, left, right, join
    .label left
        TCONST r1, 10
        TMOV r3, r1
        TJMP join
    .label right
        TCONST r2, 20
        TMOV r3, r2
        TJMP join
    .label join
        TRET r3
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # r1 (left branch only) and r2 (right branch only) are never live simultaneously,
    # so they can share the same physical register (e.g. r12 or rbx).
    assert plan.physical_register(1) == plan.physical_register(2)


def test_join_interference() -> None:
    # 8. join com valores simultaneamente vivos interfere
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
        .register r3, tryte
    .label entry
        TCONST r0, 0
        TCONST r1, 10
        TBR3 r0, left, right, join
    .label left
        TCONST r2, 20
        TJMP join
    .label right
        TCONST r2, 30
        TJMP join
    .label join
        TADD r3, r1, r2
        TRET r3
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # r1 is defined in entry and live until join.
    # r2 is defined in branches left/right and used in join.
    # Therefore, they interfere at join entry and must receive distinct registers.
    assert plan.physical_register(1) != plan.physical_register(2)


def test_loop_liveness() -> None:
    # 9. loop
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 10
        TCONST r1, 0
        TJMP header
    .label header
        TBR3 r0, body, exit, exit
    .label body
        TCONST r1, 1
        TMIN r0, r0, r1
        TJMP header
    .label exit
        TRET r1
    .end
    """
    _, plan = _get_first_func_allocation(source)
    assert plan.physical_register(0) is not None
    assert plan.physical_register(1) is not None
    assert plan.physical_register(0) != plan.physical_register(1)


def test_parameter_interference() -> None:
    # 10. parameter interference
    source = """
    .function add_params -> tryte
        .param r0, tryte
        .param r1, tryte
        .register r2, tryte
    .label entry
        TADD r2, r0, r1
        TRET r2
    .end
    """
    _, plan = _get_first_func_allocation(source)
    assert plan.physical_register(0) != plan.physical_register(1)


def test_call_crossing_value() -> None:
    # 11. call-crossing value
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TCALL r2, helper, r0
        TADD r2, r2, r1
        TRET r2
    .end
    """
    _, plan = _get_first_func_allocation(source)
    assert plan.physical_register(1) is not None


def test_dead_def_clobber_protection() -> None:
    # 12. dead-def clobber protection
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TRET r0
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # r0 must not share register with r1, because defining r1 would clobber r0.
    assert plan.physical_register(0) != plan.physical_register(1)


def test_unused_virtual() -> None:
    # 13. unused virtual
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
    .label entry
        TCONST r0, 42
        TRET r0
    .end
    """
    _, plan = _get_first_func_allocation(source)
    # Unused r1 should map to None (STACK)
    assert plan.physical_register(1) is None


def test_deterministic_repeated_allocation() -> None:
    # 14. deterministic repeated allocation
    source = """
    .function main -> tryte
        .register r0, tryte
        .register r1, tryte
        .register r2, tryte
    .label entry
        TCONST r0, 5
        TCONST r1, 10
        TADD r2, r0, r1
        TRET r2
    .end
    """
    _, plan1 = _get_first_func_allocation(source)
    _, plan2 = _get_first_func_allocation(source)
    assert plan1.allocations == plan2.allocations


def test_only_initial_allocatable_registers_allocated() -> None:
    # 15. only INITIAL_ALLOCATABLE_REGISTERS ever allocated
    source = """
    .function main -> tryte
        .register r0, tryte
    .label entry
        TCONST r0, 42
        TRET r0
    .end
    """
    _, plan = _get_first_func_allocation(source)
    for color in plan.allocations.values():
        if color is not None:
            assert color in INITIAL_ALLOCATABLE_REGISTERS
