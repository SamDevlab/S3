from __future__ import annotations

from bootstrap.s3.alias_analysis import AliasResult
from bootstrap.s3.ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IROpcode,
    IRParameter,
    IRRegister,
    IRType,
)
from bootstrap.s3.reference_analysis import (
    EscapeStatus,
    ReferenceRegion,
    alias_regions,
    analyze_references,
)


def test_reference_origin_projection_liveness_and_reads_are_reported() -> None:
    function = IRFunction(
        name="read_local",
        parameters=(),
        return_type=IRType.I64,
        registers=(
            IRRegister(0, IRType.I64),
            IRRegister(1, IRType.REFERENCE, reference_target=IRType.I64),
            IRRegister(2, IRType.REFERENCE, reference_target=IRType.I64),
            IRRegister(3, IRType.I64),
        ),
        memory_objects=(IRMemoryObject(4, IRType.I64, 8, True),),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CONST, result=0, immediate=2),
                    IRInstruction(
                        IROpcode.ADDRESS_OF,
                        result=1,
                        operands=(0,),
                        memory=4,
                        reference_target=IRType.I64,
                        reference_mutable=True,
                    ),
                    IRInstruction(IROpcode.MOVE, result=2, operands=(1,)),
                    IRInstruction(IROpcode.JUMP, targets=("read",)),
                ),
            ),
            IRBasicBlock(
                "read",
                (
                    IRInstruction(
                        IROpcode.REFERENCE_LOAD,
                        result=3,
                        operands=(2,),
                        reference_target=IRType.I64,
                    ),
                    IRInstruction(IROpcode.RETURN, operands=(3,)),
                ),
            ),
        ),
    )

    report = analyze_references(function)
    by_register = {fact.register: fact for fact in report.references}

    assert report.complete
    assert by_register[1].origins == (
        ReferenceRegion("frame-memory", 4, ("element", 2)),
    )
    assert by_register[2].origins == by_register[1].origins
    assert by_register[1].escape is EscapeStatus.NO_ESCAPE
    assert by_register[2].escape is EscapeStatus.NO_ESCAPE
    assert by_register[2].read_uses == 1
    assert by_register[1].live_blocks == ("entry",)
    assert by_register[2].live_blocks == ("entry", "read")
    assert report.to_dict() == analyze_references(function).to_dict()


def test_region_aliasing_only_proves_distinct_constant_elements_disjoint() -> None:
    root = ReferenceRegion("frame-memory", 1)
    same = ReferenceRegion("frame-memory", 1)
    element_zero = ReferenceRegion("frame-memory", 1, ("element", 0))
    element_one = ReferenceRegion("frame-memory", 1, ("element", 1))
    dynamic_a = ReferenceRegion("frame-memory", 1, ("element", ("ssa", 10)))
    dynamic_b = ReferenceRegion("frame-memory", 1, ("element", ("ssa", 11)))

    assert alias_regions(root, same) is AliasResult.MUST_ALIAS
    assert alias_regions(element_zero, element_zero) is AliasResult.MUST_ALIAS
    assert alias_regions(element_zero, element_one) is AliasResult.NO_ALIAS
    assert alias_regions(dynamic_a, dynamic_b) is AliasResult.MAY_ALIAS
    assert alias_regions(dynamic_a, element_zero) is AliasResult.MAY_ALIAS
    assert alias_regions(ReferenceRegion("external", "parameter-space"), root) is AliasResult.NO_ALIAS
    assert alias_regions(
        ReferenceRegion("external", "parameter-space", ("parameter", 0)),
        ReferenceRegion("external", "parameter-space", ("parameter", 1)),
    ) is AliasResult.MAY_ALIAS


def test_returned_reference_is_escape_and_unknown_call_stays_unknown() -> None:
    parameter = IRParameter(
        name="borrowed",
        register=0,
        type=IRType.REFERENCE,
        reference_target=IRType.I64,
        reference_mutable=False,
    )
    returned = IRFunction(
        name="return_reference",
        parameters=(),
        return_type=IRType.REFERENCE,
        result_types=(IRType.REFERENCE,),
        registers=(
            IRRegister(0, IRType.REFERENCE, reference_target=IRType.I64),
            IRRegister(1, IRType.REFERENCE, reference_target=IRType.I64),
        ),
        memory_objects=(IRMemoryObject(0, IRType.I64, 1, True),),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.ADDRESS_OF, result=0, memory=0, reference_target=IRType.I64),
                    IRInstruction(IROpcode.MOVE, result=1, operands=(0,)),
                    IRInstruction(IROpcode.RETURN, operands=(1,)),
                ),
            ),
        ),
    )
    escaped = analyze_references(returned)
    assert [fact.escape for fact in escaped.references] == [EscapeStatus.ESCAPES, EscapeStatus.ESCAPES]

    called = IRFunction(
        name="forward_reference",
        parameters=(parameter,),
        return_type=IRType.I64,
        registers=(IRRegister(1, IRType.I64),),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CALL, operands=(0,), callee="opaque_external"),
                    IRInstruction(IROpcode.CONST, result=1, immediate=0),
                    IRInstruction(IROpcode.RETURN, operands=(1,)),
                ),
            ),
        ),
    )
    unknown = analyze_references(called)
    assert not unknown.complete
    assert unknown.references[0].escape is EscapeStatus.UNKNOWN
    assert unknown.references[0].live_blocks == ("entry",)
    assert "parameter-level no-escape summary" in " ".join(unknown.incomplete_reasons)


def test_unmodeled_reference_producer_fails_closed() -> None:
    function = IRFunction(
        name="unknown_reference",
        parameters=(),
        return_type=IRType.I64,
        registers=(IRRegister(0, IRType.REFERENCE), IRRegister(1, IRType.I64)),
        blocks=(
            IRBasicBlock(
                "entry",
                (
                    IRInstruction(IROpcode.CALL, result=0, callee="unknown_factory"),
                    IRInstruction(IROpcode.CONST, result=1, immediate=0),
                    IRInstruction(IROpcode.RETURN, operands=(1,)),
                ),
            ),
        ),
    )

    report = analyze_references(function)
    assert not report.complete
    assert report.references[0].origin_unknown
    assert report.references[0].escape is EscapeStatus.UNKNOWN
