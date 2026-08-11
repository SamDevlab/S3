"""Canonical, versioned JSON serialization for verified S3 IR."""

from __future__ import annotations

import json
import math
import re
from typing import Any

from .diagnostics import (
    DiagnosticCategory,
    DiagnosticCode,
    DiagnosticPhase,
    DiagnosticSource,
    S3Error,
    SourceLocation,
)
from .ir import (
    IRBasicBlock,
    IRFunction,
    IRInstruction,
    IRMemoryObject,
    IRModule,
    IROpcode,
    IRParameter,
    IRRegister,
    IRStaticString,
    IRType,
)
from .verifier import verify_ir


IR_FORMAT = "s3-ir"
IR_FORMAT_VERSION = "0.6.0"
IR_LEGACY_FORMAT_VERSION = "0.5.0"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_STATIC_STRING_ID = re.compile(r"^s[0-9]+$")


class IRSerializationError(S3Error):
    category = "IR artifact error"
    diagnostic_category = DiagnosticCategory.ARTIFACT
    diagnostic_code = DiagnosticCode.ARTIFACT_INVALID_IR
    diagnostic_phase = DiagnosticPhase.ARTIFACT_READ


def _source_to_data(location: SourceLocation | None) -> dict[str, int] | None:
    return None if location is None else location.to_dict()


def _instruction_to_data(instruction: IRInstruction) -> dict[str, Any]:
    result = {
        "callee": instruction.callee,
        "immediate": instruction.immediate,
        "initialization": instruction.initialization,
        "memory": instruction.memory,
        "opcode": instruction.opcode.value,
        "operands": list(instruction.operands),
        "result": instruction.result if len(instruction.results) <= 1 else None,
        "results": list(instruction.results),
        "source": _source_to_data(instruction.location),
        "targets": list(instruction.targets),
    }
    if instruction.static_string is not None:
        result["static_string"] = instruction.static_string
    if instruction.reference_target is not None:
        result["reference_target"] = instruction.reference_target.value
        result["reference_mutable"] = instruction.reference_mutable
        result["reference_is_slice"] = instruction.reference_is_slice
    if instruction.slice_length_result is not None:
        result["slice_length_result"] = instruction.slice_length_result
    return result


def _static_string_to_data(entry: IRStaticString) -> dict[str, Any]:
    return {
        "id": entry.id,
        "value": entry.value,
        "utf8_bytes": list(entry.utf8_bytes),
        "byte_count": entry.byte_count,
        "sha256": entry.sha256,
    }


def _module_to_data(module: IRModule) -> dict[str, Any]:
    module_data: dict[str, Any] = {
        "functions": [
            {
                "blocks": [
                    {
                        "instructions": [
                            _instruction_to_data(instruction)
                            for instruction in block.instructions
                        ],
                        "name": block.name,
                        "source": _source_to_data(block.location),
                    }
                    for block in function.blocks
                ],
                "memory_objects": [
                    {
                        "element_type": memory.element_type.value,
                        "index": memory.index,
                        "length": memory.length,
                        "mutable": memory.mutable,
                        "source": _source_to_data(memory.location),
                    }
                    for memory in function.memory_objects
                ],
                "name": function.name,
                "parameters": [
                    {
                        "name": parameter.name,
                        "register": parameter.register,
                        "source": _source_to_data(parameter.location),
                        "type": parameter.type.value,
                        **(
                            {
                                "reference_target": parameter.reference_target.value,
                                "reference_mutable": parameter.reference_mutable,
                                "reference_is_slice": parameter.reference_is_slice,
                                **({"slice_length_register": parameter.slice_length_register} if parameter.slice_length_register is not None else {}),
                            }
                            if parameter.reference_target is not None else {}
                        ),
                    }
                    for parameter in function.parameters
                ],
                "registers": [
                    {
                        "index": register.index,
                        "source": _source_to_data(register.location),
                        "type": register.type.value,
                        **(
                            {
                                "reference_target": register.reference_target.value,
                                "reference_mutable": register.reference_mutable,
                                "reference_is_slice": register.reference_is_slice,
                                **({"slice_length_register": register.slice_length_register} if register.slice_length_register is not None else {}),
                            }
                            if register.reference_target is not None else {}
                        ),
                    }
                    for register in function.registers
                ],
                "return_type": function.return_type.value,
                "result_types": [
                    type_name.value for type_name in function.result_types
                ],
                "source": _source_to_data(function.location),
            }
            for function in module.functions
        ]
    }
    if module.static_strings:
        module_data["static_strings"] = [
            _static_string_to_data(entry) for entry in module.static_strings
        ]
    return {
        "format": IR_FORMAT,
        "module": module_data,
        "version": IR_FORMAT_VERSION,
    }


def serialize_ir(module: IRModule) -> str:
    verify_ir(module)
    return (
        json.dumps(
            _module_to_data(module),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n"
    )


def _object(value: Any, path: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise IRSerializationError(f"{path} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise IRSerializationError(f"{path} keys must be strings")
    return value


def _array(value: Any, path: str) -> list[Any]:
    if not isinstance(value, list):
        raise IRSerializationError(f"{path} must be an array")
    return value


def _exact_keys(
    value: dict[str, Any],
    expected: set[str],
    path: str,
) -> None:
    missing = sorted(expected - value.keys())
    unknown = sorted(value.keys() - expected)
    if missing:
        raise IRSerializationError(
            f"{path} is missing required field(s): {', '.join(missing)}"
        )
    if unknown:
        raise IRSerializationError(
            f"{path} has unknown field(s): {', '.join(unknown)}"
        )


def _keys(
    value: dict[str, Any],
    required: set[str],
    optional: set[str],
    path: str,
) -> None:
    missing = sorted(required - value.keys())
    unknown = sorted(value.keys() - required - optional)
    if missing:
        raise IRSerializationError(
            f"{path} is missing required field(s): {', '.join(missing)}"
        )
    if unknown:
        raise IRSerializationError(
            f"{path} has unknown field(s): {', '.join(unknown)}"
        )


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise IRSerializationError(f"{path} must be a string")
    return value


def _identifier(value: Any, path: str) -> str:
    result = _string(value, path)
    if _IDENTIFIER.fullmatch(result) is None:
        raise IRSerializationError(f"{path} is not a valid identifier")
    return result


def _static_string_id(value: Any, path: str) -> str:
    result = _string(value, path)
    if _STATIC_STRING_ID.fullmatch(result) is None:
        raise IRSerializationError(f"{path} is not a valid static string id")
    return result


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRSerializationError(f"{path} must be an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    return None if value is None else _integer(value, path)


def _optional_number(value: Any, path: str) -> int | float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IRSerializationError(f"{path} must be a finite number")
    if isinstance(value, float) and not math.isfinite(value):
        raise IRSerializationError(f"{path} must be a finite number")
    return value


def _byte_array(value: Any, path: str) -> list[int]:
    result: list[int] = []
    for index, raw in enumerate(_array(value, path)):
        byte = _integer(raw, f"{path}[{index}]")
        if not 0 <= byte <= 255:
            raise IRSerializationError(
                f"{path}[{index}] must be a byte in range [0, 255]"
            )
        result.append(byte)
    return result


def _boolean(value: Any, path: str) -> bool:
    if not isinstance(value, bool):
        raise IRSerializationError(f"{path} must be a boolean")
    return value


def _location(value: Any, path: str) -> SourceLocation | None:
    if value is None:
        return None
    data = _object(value, path)
    _exact_keys(data, {"offset", "line", "column"}, path)
    offset = _integer(data["offset"], f"{path}.offset")
    line = _integer(data["line"], f"{path}.line")
    column = _integer(data["column"], f"{path}.column")
    if offset < 0 or line < 1 or column < 1:
        raise IRSerializationError(
            f"{path} requires offset >= 0 and line/column >= 1"
        )
    return SourceLocation(offset, line, column)


def _ir_type(value: Any, path: str) -> IRType:
    text = _string(value, path)
    try:
        return IRType(text)
    except ValueError as error:
        raise IRSerializationError(f"{path} has unknown type {text!r}") from error


def _register_list(value: Any, path: str) -> tuple[int, ...]:
    return tuple(
        _integer(register, f"{path}[{index}]")
        for index, register in enumerate(_array(value, path))
    )


def _instruction(value: Any, path: str, *, version: str) -> IRInstruction:
    data = _object(value, path)
    base_required = {
        "callee",
        "immediate",
        "initialization",
        "memory",
        "opcode",
        "operands",
        "result",
        "source",
        "targets",
    }
    if version == IR_LEGACY_FORMAT_VERSION:
        _keys(data, base_required, {"static_string"}, path)
        if "results" in data:
            raise IRSerializationError(
                f"{path} contains 0.6.0 result fields under 0.5.0"
            )
    else:
        _keys(data, base_required | {"results"}, {"static_string", "reference_target", "reference_mutable", "reference_is_slice", "slice_length_result"}, path)
    opcode_text = _string(data["opcode"], f"{path}.opcode")
    try:
        opcode = IROpcode(opcode_text)
    except ValueError as error:
        raise IRSerializationError(
            f"{path}.opcode has unknown opcode {opcode_text!r}"
        ) from error
    operands = tuple(
        _integer(operand, f"{path}.operands[{index}]")
        for index, operand in enumerate(
            _array(data["operands"], f"{path}.operands")
        )
    )
    targets = tuple(
        _identifier(target, f"{path}.targets[{index}]")
        for index, target in enumerate(
            _array(data["targets"], f"{path}.targets")
        )
    )
    callee = (
        None
        if data["callee"] is None
        else _identifier(data["callee"], f"{path}.callee")
    )
    result = _optional_integer(data["result"], f"{path}.result")
    if version == IR_LEGACY_FORMAT_VERSION:
        results = () if result is None else (result,)
    else:
        results = _register_list(data["results"], f"{path}.results")
        if result is not None and results != (result,):
            raise IRSerializationError(
                f"{path}.result must agree with {path}.results for width 1"
            )
    return IRInstruction(
        opcode,
        result=result if len(results) <= 1 else None,
        operands=operands,
        immediate=_optional_number(data["immediate"], f"{path}.immediate"),
        static_string=(
            None
            if "static_string" not in data
            else _static_string_id(data["static_string"], f"{path}.static_string")
        ),
        callee=callee,
        targets=targets,
        memory=_optional_integer(data["memory"], f"{path}.memory"),
        initialization=_boolean(
            data["initialization"],
            f"{path}.initialization",
        ),
        location=_location(data["source"], f"{path}.source"),
        results=results,
        reference_target=(
            None if "reference_target" not in data
            else _ir_type(data["reference_target"], f"{path}.reference_target")
        ),
        reference_mutable=_boolean(data.get("reference_mutable", False), f"{path}.reference_mutable"),
        reference_is_slice=_boolean(data.get("reference_is_slice", False), f"{path}.reference_is_slice"),
        slice_length_result=(
            None if "slice_length_result" not in data
            else _integer(data["slice_length_result"], f"{path}.slice_length_result")
        ),
    )


def _static_string(value: Any, path: str) -> IRStaticString:
    data = _object(value, path)
    _exact_keys(
        data,
        {"byte_count", "id", "sha256", "utf8_bytes", "value"},
        path,
    )
    entry = IRStaticString(
        _static_string_id(data["id"], f"{path}.id"),
        _string(data["value"], f"{path}.value"),
    )
    utf8_bytes = _byte_array(data["utf8_bytes"], f"{path}.utf8_bytes")
    byte_count = _integer(data["byte_count"], f"{path}.byte_count")
    sha256 = _string(data["sha256"], f"{path}.sha256")
    if utf8_bytes != list(entry.utf8_bytes):
        raise IRSerializationError(f"{path}.utf8_bytes does not match value")
    if byte_count != entry.byte_count:
        raise IRSerializationError(f"{path}.byte_count does not match value")
    if sha256 != entry.sha256:
        raise IRSerializationError(f"{path}.sha256 does not match value")
    return entry


def _function(value: Any, path: str, *, version: str) -> IRFunction:
    data = _object(value, path)
    required = {
        "blocks",
        "memory_objects",
        "name",
        "parameters",
        "registers",
        "return_type",
        "source",
    }
    if version == IR_LEGACY_FORMAT_VERSION:
        if "result_types" in data:
            raise IRSerializationError(
                f"{path} contains 0.6.0 result fields under 0.5.0"
            )
        _exact_keys(data, required, path)
    else:
        _exact_keys(data, required | {"result_types"}, path)
    parameters: list[IRParameter] = []
    for index, raw in enumerate(
        _array(data["parameters"], f"{path}.parameters")
    ):
        item_path = f"{path}.parameters[{index}]"
        item = _object(raw, item_path)
        _keys(item, {"name", "register", "source", "type"}, {"reference_target", "reference_mutable", "reference_is_slice", "slice_length_register"}, item_path)
        parameters.append(
            IRParameter(
                _identifier(item["name"], f"{item_path}.name"),
                _integer(item["register"], f"{item_path}.register"),
                _ir_type(item["type"], f"{item_path}.type"),
                _location(item["source"], f"{item_path}.source"),
                None if "reference_target" not in item else _ir_type(item["reference_target"], f"{item_path}.reference_target"),
                _boolean(item.get("reference_mutable", False), f"{item_path}.reference_mutable"),
                _boolean(item.get("reference_is_slice", False), f"{item_path}.reference_is_slice"),
                None if "slice_length_register" not in item else _integer(item["slice_length_register"], f"{item_path}.slice_length_register"),
            )
        )

    registers: list[IRRegister] = []
    for index, raw in enumerate(
        _array(data["registers"], f"{path}.registers")
    ):
        item_path = f"{path}.registers[{index}]"
        item = _object(raw, item_path)
        _keys(item, {"index", "source", "type"}, {"reference_target", "reference_mutable", "reference_is_slice", "slice_length_register"}, item_path)
        registers.append(
            IRRegister(
                _integer(item["index"], f"{item_path}.index"),
                _ir_type(item["type"], f"{item_path}.type"),
                _location(item["source"], f"{item_path}.source"),
                None if "reference_target" not in item else _ir_type(item["reference_target"], f"{item_path}.reference_target"),
                _boolean(item.get("reference_mutable", False), f"{item_path}.reference_mutable"),
                _boolean(item.get("reference_is_slice", False), f"{item_path}.reference_is_slice"),
                None if "slice_length_register" not in item else _integer(item["slice_length_register"], f"{item_path}.slice_length_register"),
            )
        )

    memories: list[IRMemoryObject] = []
    for index, raw in enumerate(
        _array(data["memory_objects"], f"{path}.memory_objects")
    ):
        item_path = f"{path}.memory_objects[{index}]"
        item = _object(raw, item_path)
        _exact_keys(
            item,
            {"element_type", "index", "length", "mutable", "source"},
            item_path,
        )
        memories.append(
            IRMemoryObject(
                _integer(item["index"], f"{item_path}.index"),
                _ir_type(item["element_type"], f"{item_path}.element_type"),
                _integer(item["length"], f"{item_path}.length"),
                _boolean(item["mutable"], f"{item_path}.mutable"),
                _location(item["source"], f"{item_path}.source"),
            )
        )

    blocks: list[IRBasicBlock] = []
    for index, raw in enumerate(_array(data["blocks"], f"{path}.blocks")):
        item_path = f"{path}.blocks[{index}]"
        item = _object(raw, item_path)
        _exact_keys(item, {"instructions", "name", "source"}, item_path)
        blocks.append(
            IRBasicBlock(
                _identifier(item["name"], f"{item_path}.name"),
                tuple(
                    _instruction(
                        instruction,
                        f"{item_path}.instructions[{instruction_index}]",
                        version=version,
                    )
                    for instruction_index, instruction in enumerate(
                        _array(
                            item["instructions"],
                            f"{item_path}.instructions",
                        )
                    )
                ),
                _location(item["source"], f"{item_path}.source"),
            )
        )

    return_type = _ir_type(data["return_type"], f"{path}.return_type")
    if version == IR_LEGACY_FORMAT_VERSION:
        result_types = (return_type,)
    else:
        result_types = tuple(
            _ir_type(item, f"{path}.result_types[{index}]")
            for index, item in enumerate(
                _array(data["result_types"], f"{path}.result_types")
            )
        )
        if not result_types:
            raise IRSerializationError(f"{path}.result_types must not be empty")
    return IRFunction(
        _identifier(data["name"], f"{path}.name"),
        tuple(parameters),
        return_type,
        tuple(registers),
        tuple(blocks),
        _location(data["source"], f"{path}.source"),
        tuple(memories),
        result_types,
    )


def deserialize_ir(source: str) -> IRModule:
    try:
        raw = json.loads(source)
    except json.JSONDecodeError as error:
        raise IRSerializationError(
            f"invalid JSON at line {error.lineno}, column {error.colno}",
            diagnostic_code=DiagnosticCode.ARTIFACT_INVALID_JSON,
            diagnostic_context={
                "source": DiagnosticSource(
                    offset=error.pos,
                    line=error.lineno,
                    column=error.colno,
                ),
            },
        ) from error
    envelope = _object(raw, "artifact")
    _exact_keys(envelope, {"format", "module", "version"}, "artifact")
    format_name = _string(envelope["format"], "artifact.format")
    if format_name != IR_FORMAT:
        raise IRSerializationError(
            f"unsupported artifact format {format_name!r}",
            diagnostic_code=DiagnosticCode.ARTIFACT_UNSUPPORTED_FORMAT,
        )
    version = _string(envelope["version"], "artifact.version")
    if version not in {IR_FORMAT_VERSION, IR_LEGACY_FORMAT_VERSION}:
        raise IRSerializationError(
            f"unsupported S3 IR version {version}; "
            f"expected {IR_FORMAT_VERSION}",
            diagnostic_category=DiagnosticCategory.VERSION,
            diagnostic_code=DiagnosticCode.ARTIFACT_UNSUPPORTED_VERSION,
        )
    module_data = _object(envelope["module"], "artifact.module")
    _keys(module_data, {"functions"}, {"static_strings"}, "artifact.module")
    static_strings = tuple(
        _static_string(entry, f"artifact.module.static_strings[{index}]")
        for index, entry in enumerate(
            _array(
                module_data.get("static_strings", []),
                "artifact.module.static_strings",
            )
        )
    )
    module = IRModule(
        tuple(
            _function(
                function,
                f"artifact.module.functions[{index}]",
                version=version,
            )
            for index, function in enumerate(
                _array(
                    module_data["functions"],
                    "artifact.module.functions",
                )
            )
        ),
        static_strings,
    )
    verify_ir(module)
    return module
