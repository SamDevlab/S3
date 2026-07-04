"""Canonical, versioned JSON serialization for verified S3 IR."""

from __future__ import annotations

import json
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
    IRType,
)
from .verifier import verify_ir


IR_FORMAT = "s3-ir"
IR_FORMAT_VERSION = "0.5.0"
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


class IRSerializationError(S3Error):
    category = "IR artifact error"
    diagnostic_category = DiagnosticCategory.ARTIFACT
    diagnostic_code = DiagnosticCode.ARTIFACT_INVALID_IR
    diagnostic_phase = DiagnosticPhase.ARTIFACT_READ


def _source_to_data(location: SourceLocation | None) -> dict[str, int] | None:
    return None if location is None else location.to_dict()


def _instruction_to_data(instruction: IRInstruction) -> dict[str, Any]:
    return {
        "callee": instruction.callee,
        "immediate": instruction.immediate,
        "initialization": instruction.initialization,
        "memory": instruction.memory,
        "opcode": instruction.opcode.value,
        "operands": list(instruction.operands),
        "result": instruction.result,
        "source": _source_to_data(instruction.location),
        "targets": list(instruction.targets),
    }


def _module_to_data(module: IRModule) -> dict[str, Any]:
    return {
        "format": IR_FORMAT,
        "module": {
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
                        }
                        for parameter in function.parameters
                    ],
                    "registers": [
                        {
                            "index": register.index,
                            "source": _source_to_data(register.location),
                            "type": register.type.value,
                        }
                        for register in function.registers
                    ],
                    "return_type": function.return_type.value,
                    "source": _source_to_data(function.location),
                }
                for function in module.functions
            ]
        },
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


def _string(value: Any, path: str) -> str:
    if not isinstance(value, str):
        raise IRSerializationError(f"{path} must be a string")
    return value


def _identifier(value: Any, path: str) -> str:
    result = _string(value, path)
    if _IDENTIFIER.fullmatch(result) is None:
        raise IRSerializationError(f"{path} is not a valid identifier")
    return result


def _integer(value: Any, path: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise IRSerializationError(f"{path} must be an integer")
    return value


def _optional_integer(value: Any, path: str) -> int | None:
    return None if value is None else _integer(value, path)


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


def _instruction(value: Any, path: str) -> IRInstruction:
    data = _object(value, path)
    _exact_keys(
        data,
        {
            "callee",
            "immediate",
            "initialization",
            "memory",
            "opcode",
            "operands",
            "result",
            "source",
            "targets",
        },
        path,
    )
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
    return IRInstruction(
        opcode,
        result=_optional_integer(data["result"], f"{path}.result"),
        operands=operands,
        immediate=_optional_integer(data["immediate"], f"{path}.immediate"),
        callee=callee,
        targets=targets,
        memory=_optional_integer(data["memory"], f"{path}.memory"),
        initialization=_boolean(
            data["initialization"],
            f"{path}.initialization",
        ),
        location=_location(data["source"], f"{path}.source"),
    )


def _function(value: Any, path: str) -> IRFunction:
    data = _object(value, path)
    _exact_keys(
        data,
        {
            "blocks",
            "memory_objects",
            "name",
            "parameters",
            "registers",
            "return_type",
            "source",
        },
        path,
    )
    parameters: list[IRParameter] = []
    for index, raw in enumerate(
        _array(data["parameters"], f"{path}.parameters")
    ):
        item_path = f"{path}.parameters[{index}]"
        item = _object(raw, item_path)
        _exact_keys(item, {"name", "register", "source", "type"}, item_path)
        parameters.append(
            IRParameter(
                _identifier(item["name"], f"{item_path}.name"),
                _integer(item["register"], f"{item_path}.register"),
                _ir_type(item["type"], f"{item_path}.type"),
                _location(item["source"], f"{item_path}.source"),
            )
        )

    registers: list[IRRegister] = []
    for index, raw in enumerate(
        _array(data["registers"], f"{path}.registers")
    ):
        item_path = f"{path}.registers[{index}]"
        item = _object(raw, item_path)
        _exact_keys(item, {"index", "source", "type"}, item_path)
        registers.append(
            IRRegister(
                _integer(item["index"], f"{item_path}.index"),
                _ir_type(item["type"], f"{item_path}.type"),
                _location(item["source"], f"{item_path}.source"),
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

    return IRFunction(
        _identifier(data["name"], f"{path}.name"),
        tuple(parameters),
        _ir_type(data["return_type"], f"{path}.return_type"),
        tuple(registers),
        tuple(blocks),
        _location(data["source"], f"{path}.source"),
        tuple(memories),
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
    if version != IR_FORMAT_VERSION:
        raise IRSerializationError(
            f"unsupported S3 IR version {version}; "
            f"expected {IR_FORMAT_VERSION}",
            diagnostic_category=DiagnosticCategory.VERSION,
            diagnostic_code=DiagnosticCode.ARTIFACT_UNSUPPORTED_VERSION,
        )
    module_data = _object(envelope["module"], "artifact.module")
    _exact_keys(module_data, {"functions"}, "artifact.module")
    module = IRModule(
        tuple(
            _function(function, f"artifact.module.functions[{index}]")
            for index, function in enumerate(
                _array(
                    module_data["functions"],
                    "artifact.module.functions",
                )
            )
        )
    )
    verify_ir(module)
    return module
