"""Shared identity helpers for compile-time-specialized composite vectors."""

from __future__ import annotations

import base64

from . import ast


COMPOSITE_VECTOR_BUILTIN_PREFIX = "__s3_composite_vector__"


def type_key(type_name: ast.DeclaredType) -> str:
    """Return the deterministic key used by generic specialization and lowering."""

    if isinstance(type_name, ast.TypeName):
        return type_name.value
    if isinstance(type_name, ast.TypeParameterType):
        return type_name.name
    if isinstance(type_name, ast.VectorType):
        return f"vector__{type_key(type_name.element_type)}"
    if isinstance(type_name, ast.NominalType):
        if type_name.type_arguments:
            return f"{type_name.name}__" + "__".join(
                type_key(argument) for argument in type_name.type_arguments
            )
        return type_name.name
    if isinstance(type_name, ast.ArrayType):
        return f"{type_key(type_name.element_type)}_array{type_name.length}"
    if isinstance(type_name, ast.ReferenceType):
        return f"ref_{'mut' if type_name.mutable else 'shared'}_{type_key(type_name.target)}"
    if isinstance(type_name, ast.SliceType):
        return f"slice_{'mut' if type_name.mutable else 'shared'}_{type_name.element_type.value}"
    raise TypeError(f"unsupported generic type argument {type_name!r}")


def composite_vector_builtin_name(operation: str) -> str:
    return COMPOSITE_VECTOR_BUILTIN_PREFIX + operation


def is_composite_vector_builtin(name: str) -> bool:
    return name.startswith(COMPOSITE_VECTOR_BUILTIN_PREFIX)


def composite_vector_runtime_name(
    element_type: ast.DeclaredType,
    cell_type_codes: tuple[str, ...],
    operation: str,
) -> str:
    encoded = base64.urlsafe_b64encode(type_key(element_type).encode("utf-8")).decode(
        "ascii"
    ).rstrip("=")
    cells = "-".join(cell_type_codes) or "empty"
    return f"{COMPOSITE_VECTOR_BUILTIN_PREFIX}{encoded}__{cells}__{operation}"

