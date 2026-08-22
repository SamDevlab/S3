"""Canonical API documentation generated from validated S3 AST declarations."""

from __future__ import annotations

import json
from typing import Any

from . import ast
from .parser import parse
from .pipeline import compile_source


class DocumentationError(ValueError):
    """Raised when documentation input cannot be semantically validated."""


def _type_name(value: ast.DeclaredType) -> str:
    if isinstance(value, ast.TypeName):
        return value.value
    if isinstance(value, ast.TypeParameterType):
        return value.name
    if isinstance(value, ast.ArrayType):
        return f"{_type_name(value.element_type)}[{value.length}]"
    if isinstance(value, ast.ReferenceType):
        return "&" + ("mut " if value.mutable else "") + _type_name(value.target)
    if isinstance(value, ast.SliceType):
        return "&" + ("mut " if value.mutable else "") + f"[{value.element_type.value}]"
    if isinstance(value, ast.NominalType):
        args = ""
        if value.type_arguments:
            args = "<" + ", ".join(_type_name(item) for item in value.type_arguments) + ">"
        return value.name + args
    return "<unknown>"


def _function_payload(function: ast.FunctionDeclaration) -> dict[str, Any]:
    return {
        "kind": "function",
        "name": function.name,
        "exported": function.exported,
        "parameters": [
            {"name": item.name, "type": _type_name(item.type_name)}
            for item in function.parameters
        ],
        "return_type": _type_name(function.return_type),
    }


def _program_payload(program: ast.Program, *, public_only: bool) -> dict[str, object]:
    functions = [item for item in program.functions if not public_only or item.exported]
    records = [item for item in program.records if not public_only or item.exported]
    enums = [item for item in program.enums if not public_only or item.exported]
    return {
        "schema": "s3-api-documentation",
        "schema_version": "1",
        "module": program.module.name if program.module is not None else None,
        "functions": [_function_payload(item) for item in sorted(functions, key=lambda x: x.name)],
        "records": [
            {
                "kind": "record",
                "name": item.name,
                "exported": item.exported,
                "fields": [
                    {"name": field.name, "type": _type_name(field.type_name)}
                    for field in sorted(item.fields, key=lambda x: x.name)
                ],
            }
            for item in sorted(records, key=lambda x: x.name)
        ],
        "enums": [
            {
                "kind": "enum",
                "name": item.name,
                "exported": item.exported,
                "variants": [
                    {
                        "name": variant.name,
                        "payload": [
                            {"name": field.name, "type": _type_name(field.type_name)}
                            for field in sorted(variant.payload_fields, key=lambda x: x.name)
                        ],
                    }
                    for variant in sorted(item.variants, key=lambda x: x.name)
                ],
            }
            for item in sorted(enums, key=lambda x: x.name)
        ],
    }


def build_documentation(source: str, *, public_only: bool = True) -> dict[str, object]:
    if not isinstance(source, str):
        raise DocumentationError("source must be text")
    try:
        compile_source(source)
        program = parse(source)
    except Exception as error:
        raise DocumentationError("source must pass compiler validation") from error
    return _program_payload(program, public_only=public_only)


def render_markdown(source: str, *, public_only: bool = True) -> str:
    payload = build_documentation(source, public_only=public_only)
    lines = ["# S3 API", ""]
    if payload["module"] is not None:
        lines.extend((f"Module: `{payload['module']}`", ""))
    for section, heading in (("functions", "Functions"), ("records", "Records"), ("enums", "Enums")):
        lines.extend((f"## {heading}", ""))
        entries = payload[section]
        if not entries:
            lines.extend(("None.", ""))
            continue
        for entry in entries:
            if section == "functions":
                params = ", ".join(f"{item['name']}: {item['type']}" for item in entry["parameters"])
                lines.append(f"- `{entry['name']}({params}) -> {entry['return_type']}`")
            elif section == "records":
                fields = ", ".join(f"{item['name']}: {item['type']}" for item in entry["fields"])
                lines.append(f"- `{entry['name']}({fields})`")
            else:
                variants = ", ".join(item["name"] for item in entry["variants"])
                lines.append(f"- `{entry['name']}`: {variants}")
        lines.append("")
    return "\n".join(lines)


def render_json(source: str, *, public_only: bool = True) -> str:
    return json.dumps(build_documentation(source, public_only=public_only), ensure_ascii=True, sort_keys=True, indent=2) + "\n"
