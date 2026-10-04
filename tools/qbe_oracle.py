"""Experimental, fail-closed translator from verified S3 IR to QBE IL."""

from __future__ import annotations

import re

from bootstrap.s3.ir import IRFunction, IRInstruction, IRModule, IROpcode, IRType
from bootstrap.s3.verifier import verify_ir


class QBETranslationError(ValueError):
    """The verified S3 program uses semantics outside the experimental subset."""


_IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*\Z")
_QBE_TYPES = {IRType.I64: "l", IRType.F64: "d", IRType.TRIT: "l"}


def translate_verified_ir(module: IRModule) -> str:
    """Verify and translate a deliberately small scalar subset to QBE IL.

    Integer arithmetic, memory, aggregates, references, dynamic builtins and
    non-scalar ABI shapes are rejected. In particular, S3 checked i64
    arithmetic is never silently mapped to QBE's wrapping machine arithmetic.
    """

    verify_ir(module)
    _validate_supported_module(module)
    emitted = ["# Experimental QBE oracle; generated from verified S3 IR."]
    functions = {function.name: function for function in module.functions}
    for function_index, function in enumerate(module.functions):
        emitted.extend(_translate_function(function, function_index, functions))
    return "\n".join(emitted) + "\n"


def _validate_supported_module(module: IRModule) -> None:
    if module.static_strings:
        raise QBETranslationError("static strings are outside QBE oracle V1")
    functions = {function.name: function for function in module.functions}
    for function in module.functions:
        if function.external:
            raise QBETranslationError(
                f"external function '{function.name}' is outside QBE oracle V1"
            )
        if not _IDENTIFIER.fullmatch(function.name):
            raise QBETranslationError(
                f"function name '{function.name}' cannot be represented safely in QBE IL"
            )
        if function.return_type not in {IRType.I64, IRType.F64}:
            raise QBETranslationError(
                f"function '{function.name}' result type {function.return_type.value} "
                "is outside QBE oracle V1"
            )
        if function.result_width != 1:
            raise QBETranslationError(
                f"function '{function.name}' has a non-scalar result width"
            )
        if any(parameter.type not in {IRType.I64, IRType.F64} for parameter in function.parameters):
            raise QBETranslationError(
                f"function '{function.name}' has a non-scalar ABI parameter"
            )
        if any(register.type not in _QBE_TYPES for register in function.registers):
            unsupported = next(
                register.type.value
                for register in function.registers
                if register.type not in _QBE_TYPES
            )
            raise QBETranslationError(
                f"function '{function.name}' uses unsupported register type {unsupported}; "
                "this is outside QBE oracle V1"
            )
        for block in function.blocks:
            for instruction in block.instructions:
                _validate_instruction(function, block.name, instruction, functions)


def _validate_instruction(
    function: IRFunction,
    block_name: str,
    instruction: IRInstruction,
    functions: dict[str, IRFunction],
) -> None:
    op = instruction.opcode
    operands = instruction.operands
    registers = {register.index: register.type for register in function.registers}

    if op is IROpcode.CONST:
        result_type = _result_type(function, instruction)
        if result_type not in {IRType.I64, IRType.F64, IRType.TRIT}:
            _unsupported(function, block_name, instruction, "constant type")
        return
    if op is IROpcode.MOVE:
        result_type = _result_type(function, instruction)
        if result_type not in {IRType.I64, IRType.F64, IRType.TRIT}:
            _unsupported(function, block_name, instruction, "move type")
        return
    if op in {IROpcode.COMPARE, IROpcode.RELATE}:
        if len(operands) != 2 or any(
            registers[operand] not in {IRType.I64, IRType.F64} for operand in operands
        ):
            _unsupported(function, block_name, instruction, "comparison operands")
        if _result_type(function, instruction) is not IRType.TRIT:
            _unsupported(function, block_name, instruction, "comparison result")
        return
    if op is IROpcode.CALL:
        callee = functions.get(instruction.callee or "")
        if callee is None:
            _unsupported(function, block_name, instruction, "external or builtin call")
        if len(instruction.results) != 1:
            _unsupported(function, block_name, instruction, "non-scalar call result")
        if any(
            registers[operand] not in {IRType.I64, IRType.F64}
            for operand in operands
        ):
            _unsupported(function, block_name, instruction, "non-scalar call argument")
        if any(parameter.type not in {IRType.I64, IRType.F64} for parameter in callee.parameters):
            _unsupported(function, block_name, instruction, "non-scalar callee ABI")
        if callee.return_type not in {IRType.I64, IRType.F64} or callee.result_width != 1:
            _unsupported(function, block_name, instruction, "non-scalar callee result")
        return
    if op is IROpcode.JUMP:
        return
    if op is IROpcode.BRANCH3:
        if len(operands) != 1 or registers[operands[0]] is not IRType.TRIT:
            _unsupported(function, block_name, instruction, "branch3 condition")
        return
    if op is IROpcode.RETURN:
        if len(operands) != 1 or registers[operands[0]] is not function.return_type:
            _unsupported(function, block_name, instruction, "return value")
        return
    _unsupported(function, block_name, instruction, "opcode")


def _translate_function(
    function: IRFunction,
    function_index: int,
    functions: dict[str, IRFunction],
) -> list[str]:
    linkage = "export " if function.exported or function.name == "main" else ""
    result_type = _qbe_type(function.return_type)
    parameters = ", ".join(
        f"{_qbe_type(parameter.type)} %r{parameter.register}"
        for parameter in function.parameters
    )
    lines = [f"{linkage}function {result_type} ${function.name}({parameters}) {{"]
    block_names = {block.name: f"b{index}" for index, block in enumerate(function.blocks)}
    temporary_index = 0
    for block_index, block in enumerate(function.blocks):
        lines.append(f"@{block_names[block.name]}")
        for instruction in block.instructions:
            op = instruction.opcode
            result = instruction.result
            args = instruction.operands
            if op is IROpcode.CONST:
                assert result is not None and instruction.immediate is not None
                result_type = _register_type(function, result)
                value = _format_constant(instruction.immediate, result_type)
                lines.append(f"\t%r{result} ={_qbe_type(result_type)} copy {value}")
            elif op is IROpcode.MOVE:
                assert result is not None
                result_type = _register_type(function, result)
                lines.append(
                    f"\t%r{result} ={_qbe_type(result_type)} copy %r{args[0]}"
                )
            elif op is IROpcode.RELATE:
                assert result is not None and instruction.immediate is not None
                operand_type = _register_type(function, args[0])
                predicate = _qbe_predicate(int(instruction.immediate), operand_type)
                compare_name = _temporary(function_index, temporary_index, "rel")
                temporary_index += 1
                lines.append(
                    f"\t{compare_name} =l {predicate} %r{args[0]}, %r{args[1]}"
                )
                # QBE comparisons return 1/0; S3 RELATE returns -1/0.
                lines.append(f"\t%r{result} =l sub 0, {compare_name}")
            elif op is IROpcode.COMPARE:
                assert result is not None
                operand_type = _register_type(function, args[0])
                suffix = _comparison_suffix(operand_type)
                less = _temporary(function_index, temporary_index, "cmp_less")
                nonless_label = _label(function_index, temporary_index, "cmp_nonless")
                less_label = _label(function_index, temporary_index, "cmp_lt")
                greater_label = _label(function_index, temporary_index, "cmp_gt")
                equal_label = _label(function_index, temporary_index, "cmp_eq")
                join_label = _label(function_index, temporary_index, "cmp_join")
                greater = _temporary(function_index, temporary_index, "cmp_greater")
                temporary_index += 1
                lines.extend(
                    [
                        f"\t{less} =l {suffix[0]} %r{args[0]}, %r{args[1]}",
                        f"\tjnz {less}, @{less_label}, @{nonless_label}",
                        f"@{less_label}",
                        f"\tjmp @{join_label}",
                        f"@{nonless_label}",
                        f"\t{greater} =l {suffix[1]} %r{args[0]}, %r{args[1]}",
                        f"\tjnz {greater}, @{greater_label}, @{equal_label}",
                        f"@{greater_label}",
                        f"\tjmp @{join_label}",
                        f"@{equal_label}",
                        f"\tjmp @{join_label}",
                        f"@{join_label}",
                        f"\t%r{result} =l phi @{less_label} -1, @{equal_label} 0, @{greater_label} 1",
                    ]
                )
            elif op is IROpcode.CALL:
                assert result is not None and instruction.callee is not None
                callee = functions[instruction.callee]
                result_type = _register_type(function, result)
                call_arguments = ", ".join(
                    f"{_qbe_type(parameter.type)} %r{register}"
                    for parameter, register in zip(
                        callee.parameters, args, strict=True
                    )
                )
                lines.append(
                    f"\t%r{result} ={_qbe_type(result_type)} call "
                    f"${callee.name}({call_arguments})"
                )
            elif op is IROpcode.JUMP:
                lines.append(f"\tjmp @{block_names[instruction.targets[0]]}")
            elif op is IROpcode.BRANCH3:
                assert len(args) == 1
                negative = _temporary(function_index, temporary_index, "branch_neg")
                zero = _temporary(function_index, temporary_index, "branch_zero")
                zero_label = _label(function_index, temporary_index, "branch_check_zero")
                temporary_index += 1
                lines.extend(
                    [
                        f"\t{negative} =l ceql %r{args[0]}, -1",
                        f"\tjnz {negative}, @{block_names[instruction.targets[0]]}, @{zero_label}",
                        f"@{zero_label}",
                        f"\t{zero} =l ceql %r{args[0]}, 0",
                        f"\tjnz {zero}, @{block_names[instruction.targets[1]]}, @{block_names[instruction.targets[2]]}",
                    ]
                )
            elif op is IROpcode.RETURN:
                lines.append(f"\tret %r{args[0]}")
            else:
                raise AssertionError(f"validated opcode was not translated: {op}")
        if block_index == 0 and block.instructions[-1].opcode not in {
            IROpcode.RETURN,
            IROpcode.JUMP,
            IROpcode.BRANCH3,
        }:
            raise AssertionError("verified S3 block has no terminator")
    lines.append("}")
    return lines


def _qbe_type(type_: IRType) -> str:
    try:
        return _QBE_TYPES[type_]
    except KeyError as error:
        raise QBETranslationError(f"unsupported S3 type {type_.value}") from error


def _register_type(function: IRFunction, register: int) -> IRType:
    for item in function.registers:
        if item.index == register:
            return item.type
    raise QBETranslationError(
        f"function '{function.name}' references missing register r{register}"
    )


def _result_type(function: IRFunction, instruction: IRInstruction) -> IRType:
    if instruction.result is None:
        _unsupported(function, "?", instruction, "missing result")
    return _register_type(function, instruction.result)


def _format_constant(value: int | float, type_: IRType) -> str:
    if type_ is IRType.F64:
        return "d_" + repr(float(value))
    return str(int(value))


def _comparison_suffix(type_: IRType) -> tuple[str, str]:
    if type_ is IRType.I64:
        return "csltl", "csgtl"
    if type_ is IRType.F64:
        return "cltd", "cgtd"
    raise QBETranslationError(f"comparison for {type_.value} is outside QBE oracle V1")


def _qbe_predicate(relation: int, type_: IRType) -> str:
    names = {0: "ceq", 1: "cne", 2: "clt", 3: "cle", 4: "cgt", 5: "cge"}
    if relation not in names:
        raise QBETranslationError(f"unknown S3 relation code {relation}")
    suffix = "l" if type_ is IRType.I64 else "d" if type_ is IRType.F64 else None
    if suffix is None:
        raise QBETranslationError(f"relation for {type_.value} is outside QBE oracle V1")
    if type_ is IRType.I64 and relation in {2, 3, 4, 5}:
        names.update({2: "cslt", 3: "csle", 4: "csgt", 5: "csge"})
    return names[relation] + suffix


def _temporary(function_index: int, index: int, stem: str) -> str:
    return f"%s3_f{function_index}_{stem}_{index}"


def _label(function_index: int, index: int, stem: str) -> str:
    return f"s3_f{function_index}_{stem}_{index}"


def _unsupported(
    function: IRFunction,
    block: str,
    instruction: IRInstruction,
    reason: str,
) -> None:
    op = instruction.opcode.value if isinstance(instruction.opcode, IROpcode) else instruction.opcode
    raise QBETranslationError(
        f"function '{function.name}' block '{block}': {reason} is outside "
        f"QBE oracle V1 (opcode {op})"
    )
