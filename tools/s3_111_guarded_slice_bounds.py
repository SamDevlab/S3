"""Prove bounded slice indices in two pinned loop workloads, analysis-only."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bootstrap.s3 import ast
from bootstrap.s3.ir import IRFunction, IRInstruction, IROpcode, IRType
from bootstrap.s3.optimizer import OptimizationLevel
from bootstrap.s3.parser import parse
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.ssa_optimizer import loops as loop_analysis
from bootstrap.s3.ternary import TRYTE_MAX, TRYTE_MIN
from tools.s3_111_loop_predicate_diagnostics import WORKLOADS, _definitions
from tools.s3_111_loop_recurrence_probe import probe_loop_recurrence

_I64_MIN = -(1 << 63)
_I64_MAX = (1 << 63) - 1
EXPERIMENT_CONTROL_SHA = "832b1cc04fe1f6174e482eb3a245e08af3d53211"
EXPERIMENT_CONTROL_TREE = "dc1138890655169088f9371ce32a9050cfc3af8d"


def _source_sha256(data: bytes) -> str:
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


@dataclass(frozen=True, slots=True)
class Interval:
    low: int
    high: int

    def intersect(self, low: int, high: int) -> Interval | None:
        result = Interval(max(self.low, low), min(self.high, high))
        return result if result.low <= result.high else None


@dataclass(frozen=True, slots=True)
class Affine:
    constant: int = 0
    coefficients: tuple[tuple[str, int], ...] = ()

    @classmethod
    def variable(cls, name: str) -> Affine:
        return cls(0, ((name, 1),))

    def add(self, other: Affine) -> Affine:
        coefficients: dict[str, int] = dict(self.coefficients)
        for name, coefficient in other.coefficients:
            coefficients[name] = coefficients.get(name, 0) + coefficient
        return Affine(
            self.constant + other.constant,
            tuple(sorted((name, value) for name, value in coefficients.items() if value)),
        )

    def scale(self, factor: int) -> Affine:
        return Affine(
            self.constant * factor,
            tuple((name, value * factor) for name, value in self.coefficients if value * factor),
        )

    def to_dict(self) -> dict[str, Any]:
        return {"constant": self.constant, "coefficients": dict(self.coefficients)}


@dataclass(frozen=True, slots=True)
class Value:
    interval: Interval | None
    affine: Affine | None
    length_source: str | None = None
    safe: bool = True
    exclusive_upper_source: str | None = None
    row_major_columns: tuple[str, str] | None = None
    row_major_neighbor: bool = False


@dataclass(slots=True)
class State:
    intervals: dict[str, Interval] = field(default_factory=dict)
    affines: dict[str, Affine | None] = field(default_factory=dict)
    length_sources: dict[str, str | None] = field(default_factory=dict)
    types: dict[str, str] = field(default_factory=dict)
    safe_values: dict[str, bool] = field(default_factory=dict)
    equalities: set[tuple[Affine, Affine]] = field(default_factory=set)
    product_equalities: set[tuple[str, str, str]] = field(default_factory=set)
    induction_bounds: dict[str, str] = field(default_factory=dict)
    proven_inductions: set[str] = field(default_factory=set)
    exclusive_upper_sources: dict[str, str | None] = field(default_factory=dict)
    row_major_columns: dict[str, tuple[str, str]] = field(default_factory=dict)
    neighbor_upper_sources: dict[str, str] = field(default_factory=dict)
    row_major_neighbors: set[str] = field(default_factory=set)

    def clone(self) -> State:
        return State(
            intervals=dict(self.intervals),
            affines=dict(self.affines),
            length_sources=dict(self.length_sources),
            types=dict(self.types),
            safe_values=dict(self.safe_values),
            equalities=set(self.equalities),
            product_equalities=set(self.product_equalities),
            induction_bounds=dict(self.induction_bounds),
            proven_inductions=set(self.proven_inductions),
            exclusive_upper_sources=dict(self.exclusive_upper_sources),
            row_major_columns=dict(self.row_major_columns),
            neighbor_upper_sources=dict(self.neighbor_upper_sources),
            row_major_neighbors=set(self.row_major_neighbors),
        )


def _identity(name: str) -> Affine:
    return Affine.variable(name)


def _same_equation(state: State, left: Affine, right: Affine) -> bool:
    return (left, right) in state.equalities or (right, left) in state.equalities


def _guarded_product_equality(expression: Any) -> tuple[str, str, str] | None:
    if not isinstance(expression, ast.BinaryExpression) or expression.operator.value != "==":
        return None
    left, right = expression.left, expression.right
    product: Any = None
    result: Any = None
    if isinstance(left, ast.Identifier) and isinstance(right, ast.BinaryExpression):
        result, product = left, right
    elif isinstance(right, ast.Identifier) and isinstance(left, ast.BinaryExpression):
        result, product = right, left
    if (
        result is None
        or product.operator.value != "*"
        or not isinstance(product.left, ast.Identifier)
        or not isinstance(product.right, ast.Identifier)
    ):
        return None
    first, second = sorted((product.left.name, product.right.name))
    return result.name, first, second


def _rectangular_row_major_bound(expression: Any, state: State) -> Value | None:
    if not isinstance(expression, ast.BinaryExpression) or expression.operator.value != "+":
        return None
    product: Any = None
    column: Any = None
    if isinstance(expression.left, ast.BinaryExpression) and isinstance(expression.right, ast.Identifier):
        product, column = expression.left, expression.right
    elif isinstance(expression.right, ast.BinaryExpression) and isinstance(expression.left, ast.Identifier):
        product, column = expression.right, expression.left
    if (
        product is None
        or product.operator.value != "*"
        or not isinstance(product.left, ast.Identifier)
        or not isinstance(product.right, ast.Identifier)
    ):
        return None

    names = (product.left.name, product.right.name)
    for row_name, width_name in (names, names[::-1]):
        height_name = state.induction_bounds.get(row_name)
        if (
            height_name is None
            or row_name not in state.proven_inductions
            or state.induction_bounds.get(column.name) != width_name
            or column.name not in state.proven_inductions
        ):
            continue
        dimensions = tuple(sorted((width_name, height_name)))
        count_name = next(
            (count for count, width, height in state.product_equalities
             if (width, height) == dimensions),
            None,
        )
        if count_name is None:
            continue
        row_interval = state.intervals.get(row_name)
        column_interval = state.intervals.get(column.name)
        width_interval = state.intervals.get(width_name)
        height_interval = state.intervals.get(height_name)
        count_interval = state.intervals.get(count_name)
        if any(item is None for item in (
            row_interval, column_interval, width_interval, height_interval, count_interval
        )):
            continue
        assert row_interval and column_interval and width_interval and height_interval and count_interval
        if (
            width_interval.low < 1
            or height_interval.low < 1
            or count_interval.low < 1
            or count_interval.high > TRYTE_MAX + 1
            or row_interval.low < 0
            or row_interval.high > height_interval.high - 1
            or column_interval.low < 0
            or column_interval.high > width_interval.high - 1
        ):
            continue
        # With positive dimensions and count = width * height,
        # row * width + column is in [0, count - 1].
        return Value(
            Interval(0, count_interval.high - 1),
            None,
            safe=True,
            exclusive_upper_source=count_name,
            row_major_columns=(column.name, width_name),
        )
    return None


def _unwrap_tryte(expression: Any) -> Any:
    if (
        isinstance(expression, ast.CallExpression)
        and expression.function_name == "to_tryte"
        and len(expression.arguments) == 1
    ):
        return expression.arguments[0].expression
    return expression


def _column_neighbor_condition(expression: Any) -> tuple[str, str] | None:
    if not isinstance(expression, ast.BinaryExpression) or expression.operator.value != "<":
        return None
    left = _unwrap_tryte(expression.left)
    right = _unwrap_tryte(expression.right)
    if not isinstance(right, ast.Identifier) or not isinstance(left, ast.BinaryExpression):
        return None
    if left.operator.value != "+":
        return None
    if isinstance(left.left, ast.Identifier) and isinstance(left.right, ast.IntegerLiteral) and left.right.value == 1:
        column = left.left
    elif isinstance(left.right, ast.Identifier) and isinstance(left.left, ast.IntegerLiteral) and left.left.value == 1:
        column = left.right
    else:
        return None
    return column.name, right.name


def _rectangular_neighbor_bound(expression: Any, state: State) -> Value | None:
    if not isinstance(expression, ast.BinaryExpression) or expression.operator.value != "+":
        return None
    index: Any = None
    if isinstance(expression.left, ast.Identifier) and isinstance(expression.right, ast.IntegerLiteral) and expression.right.value == 1:
        index = expression.left
    elif isinstance(expression.right, ast.Identifier) and isinstance(expression.left, ast.IntegerLiteral) and expression.left.value == 1:
        index = expression.right
    if index is None:
        return None
    count_name = state.neighbor_upper_sources.get(index.name)
    count_interval = state.intervals.get(count_name) if count_name is not None else None
    if count_name is None or count_interval is None:
        return None
    if count_interval.high > TRYTE_MAX + 1:
        return None
    # The recorded strict column guard and nonnegative induction imply width >= 2;
    # positive height and the retained product equality therefore imply count >= 2.
    return Value(
        Interval(1, count_interval.high - 1),
        None,
        safe=True,
        exclusive_upper_source=count_name,
        row_major_neighbor=True,
    )


def _bounds_binary(operator: str, left: Interval, right: Interval) -> Interval | None:
    if operator == "+":
        low, high = left.low + right.low, left.high + right.high
    elif operator == "*":
        values = (
            left.low * right.low,
            left.low * right.high,
            left.high * right.low,
            left.high * right.high,
        )
        low, high = min(values), max(values)
    else:
        return None
    if low < _I64_MIN or high > _I64_MAX:
        return None
    return Interval(low, high)


def _eval(expression: Any, state: State) -> Value:
    if isinstance(expression, ast.IntegerLiteral):
        return Value(Interval(expression.value, expression.value), Affine(expression.value))
    if isinstance(expression, ast.Identifier):
        return Value(
            state.intervals.get(expression.name),
            state.affines.get(expression.name) or _identity(expression.name),
            state.length_sources.get(expression.name),
            state.safe_values.get(expression.name, True),
            state.exclusive_upper_sources.get(expression.name),
            state.row_major_columns.get(expression.name),
            expression.name in state.row_major_neighbors,
        )
    if isinstance(expression, ast.LenExpression):
        source = expression.argument.name if isinstance(expression.argument, ast.Identifier) else None
        return Value(Interval(0, _I64_MAX), None, source)
    if isinstance(expression, ast.CallExpression):
        name = expression.function_name
        if name != "to_tryte" or len(expression.arguments) != 1:
            return Value(None, None, safe=False)
        argument = _eval(expression.arguments[0].expression, state)
        if argument.interval is None or not (
            TRYTE_MIN <= argument.interval.low <= argument.interval.high <= TRYTE_MAX
        ):
            return Value(None, None, safe=False)
        return Value(
            argument.interval,
            argument.affine,
            safe=argument.safe,
            exclusive_upper_source=argument.exclusive_upper_source,
            row_major_columns=argument.row_major_columns,
            row_major_neighbor=argument.row_major_neighbor,
        )
    if isinstance(expression, ast.BinaryExpression):
        operator = expression.operator.value
        if operator == "+":
            rectangular = _rectangular_row_major_bound(expression, state)
            if rectangular is not None:
                return rectangular
            neighbor = _rectangular_neighbor_bound(expression, state)
            if neighbor is not None:
                return neighbor
        left, right = _eval(expression.left, state), _eval(expression.right, state)
        if left.interval is None or right.interval is None:
            return Value(None, None, safe=left.safe and right.safe)
        bounds = _bounds_binary(operator, left.interval, right.interval)
        if bounds is None:
            return Value(None, None, safe=False)
        affine: Affine | None = None
        if operator == "+" and left.affine is not None and right.affine is not None:
            affine = left.affine.add(right.affine)
        elif operator == "*" and left.affine is not None and right.affine is not None:
            if not left.affine.coefficients:
                affine = right.affine.scale(left.affine.constant)
            elif not right.affine.coefficients:
                affine = left.affine.scale(right.affine.constant)
        return Value(bounds, affine, safe=left.safe and right.safe)
    return Value(None, None, safe=False)


def _refine(state: State, expression: Any, truth: bool) -> State | None:
    if not isinstance(expression, ast.BinaryExpression):
        return state.clone()
    operator = expression.operator.value
    if operator not in {"<", "<=", ">", ">=", "==", "!="}:
        return state.clone()
    left_value, right_value = _eval(expression.left, state), _eval(expression.right, state)
    child = state.clone()
    if operator in {"==", "!="}:
        equal = truth if operator == "==" else not truth
        if equal:
            product_equality = _guarded_product_equality(expression)
            if product_equality is not None:
                child.product_equalities.add(product_equality)
            if left_value.affine is not None and right_value.affine is not None:
                child.equalities.add((left_value.affine, right_value.affine))
            if isinstance(expression.left, ast.Identifier) and right_value.interval is not None:
                current = child.intervals.get(expression.left.name)
                narrowed = right_value.interval if current is None else current.intersect(
                    right_value.interval.low, right_value.interval.high
                )
                if narrowed is None:
                    return None
                child.intervals[expression.left.name] = narrowed
            elif isinstance(expression.right, ast.Identifier) and left_value.interval is not None:
                current = child.intervals.get(expression.right.name)
                narrowed = left_value.interval if current is None else current.intersect(
                    left_value.interval.low, left_value.interval.high
                )
                if narrowed is None:
                    return None
                child.intervals[expression.right.name] = narrowed
        return child

    if operator == "<" and truth:
        neighbor_condition = _column_neighbor_condition(expression)
        if neighbor_condition is not None:
            column_name, width_name = neighbor_condition
            for index_name, dimensions in child.row_major_columns.items():
                if dimensions == (column_name, width_name):
                    count_name = child.exclusive_upper_sources.get(index_name)
                    if count_name is not None:
                        child.neighbor_upper_sources[index_name] = count_name

    variable: ast.Identifier | None = None
    constant: int | None = None
    reverse = False
    if isinstance(expression.left, ast.Identifier) and isinstance(expression.right, ast.IntegerLiteral):
        variable, constant = expression.left, expression.right.value
    elif isinstance(expression.right, ast.Identifier) and isinstance(expression.left, ast.IntegerLiteral):
        variable, constant, reverse = expression.right, expression.left.value, True
    if variable is None or constant is None:
        return child

    if reverse:
        operator = {"<": ">", "<=": ">=", ">": "<", ">=": "<="}[operator]
    if not truth:
        operator = {"<": ">=", "<=": ">", ">": "<=", ">=": "<"}[operator]
    limits = {
        "<": (_I64_MIN, constant - 1),
        "<=": (_I64_MIN, constant),
        ">": (constant + 1, _I64_MAX),
        ">=": (constant, _I64_MAX),
    }
    low, high = limits[operator]
    current = child.intervals.get(variable.name, Interval(_I64_MIN, _I64_MAX))
    narrowed = current.intersect(low, high)
    if narrowed is None:
        return None
    child.intervals[variable.name] = narrowed
    return child


def _relation_case_truth(label: Any) -> bool | None:
    # Source relational lowering emits -1 for true and 0 for false.
    if label == -1:
        return True
    if label == 0:
        return False
    if label == 1:
        return None
    return None


def _case_is_unreachable(expression: Any, label: Any) -> bool:
    return (
        label == 1
        and isinstance(expression, ast.BinaryExpression)
        and expression.operator.value in {"<", "<=", ">", ">=", "==", "!="}
    )


def _write_value(state: State, name: str, value: Value, type_name: str | None = None) -> None:
    state.product_equalities = {
        fact for fact in state.product_equalities if name not in fact
    }
    state.equalities = {
        (left, right)
        for left, right in state.equalities
        if name not in dict(left.coefficients) and name not in dict(right.coefficients)
    }
    for induction, bound in list(state.induction_bounds.items()):
        if induction == name or bound == name:
            state.induction_bounds.pop(induction)
            state.proven_inductions.discard(induction)
    for index_name, dimensions in list(state.row_major_columns.items()):
        if index_name == name or name in dimensions or state.exclusive_upper_sources.get(index_name) == name:
            state.row_major_columns.pop(index_name)
            state.exclusive_upper_sources[index_name] = None
            state.neighbor_upper_sources.pop(index_name, None)
            state.row_major_neighbors.discard(index_name)
    for index_name, count_name in list(state.neighbor_upper_sources.items()):
        if index_name == name or count_name == name:
            state.neighbor_upper_sources.pop(index_name)
    state.intervals[name] = value.interval or Interval(_I64_MIN, _I64_MAX)
    state.affines[name] = value.affine or _identity(name)
    state.length_sources[name] = value.length_source
    state.safe_values[name] = value.safe
    state.exclusive_upper_sources[name] = value.exclusive_upper_source
    if value.row_major_columns is None:
        state.row_major_columns.pop(name, None)
    else:
        state.row_major_columns[name] = value.row_major_columns
    if value.row_major_neighbor:
        state.row_major_neighbors.add(name)
    else:
        state.row_major_neighbors.discard(name)
    if type_name is not None:
        state.types[name] = type_name


def _walk_indexes(expression: Any) -> list[ast.IndexExpression]:
    found: list[ast.IndexExpression] = []
    if isinstance(expression, ast.IndexExpression):
        found.append(expression)
        found.extend(_walk_indexes(expression.target))
        found.extend(_walk_indexes(expression.index))
    elif isinstance(expression, ast.BinaryExpression):
        found.extend(_walk_indexes(expression.left))
        found.extend(_walk_indexes(expression.right))
    elif isinstance(expression, ast.CallExpression):
        found.extend(_walk_indexes(expression.callee))
        for argument in expression.arguments:
            found.extend(_walk_indexes(argument.expression))
    elif isinstance(expression, ast.LenExpression):
        found.extend(_walk_indexes(expression.argument))
    elif isinstance(expression, ast.UnaryExpression):
        found.extend(_walk_indexes(expression.operand))
    elif isinstance(expression, ast.SliceExpression):
        for part in (expression.target, expression.start, expression.end):
            found.extend(_walk_indexes(part))
    return found


def _known_function(ir: Any, source_name: str) -> IRFunction:
    matches = [item for item in ir.functions if item.name == source_name or item.name.endswith("__" + source_name)]
    if len(matches) != 1:
        raise RuntimeError(f"expected one IR function {source_name}, found {len(matches)}")
    return matches[0]


def _ir_slice_loads(function: IRFunction) -> dict[tuple[str, int], list[dict[str, Any]]]:
    parameter_names = {parameter.register: parameter.name for parameter in function.parameters}
    types = {register.index: register.type for register in function.registers}
    rows: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for block in function.blocks:
        for index, instruction in enumerate(block.instructions):
            if instruction.opcode is not IROpcode.SLICE_LOAD or instruction.location is None:
                continue
            if len(instruction.operands) != 3:
                raise RuntimeError("unexpected SLICE_LOAD operand shape")
            base, _length, subscript = instruction.operands
            parameter_name = parameter_names.get(base)
            rows.setdefault((parameter_name or "", instruction.location.line), []).append({
                "block": block.name,
                "instruction_index": index,
                "index_register_type": types[subscript].value,
                "inside_loop": False,
            })
    return rows


def _constant_register(register: int, definitions: dict[int, IRInstruction]) -> int | None:
    seen: set[int] = set()
    current = register
    while current not in seen:
        seen.add(current)
        instruction = definitions.get(current)
        if instruction is None:
            return None
        if instruction.opcode is IROpcode.CONST and isinstance(instruction.immediate, int):
            return instruction.immediate
        if instruction.opcode is not IROpcode.MOVE or len(instruction.operands) != 1:
            return None
        current = instruction.operands[0]
    return None


def _loop_ir_proof(function: IRFunction, loop: Any) -> dict[str, Any]:
    blocks = {block.name: block for block in function.blocks}
    definitions = _definitions(function)
    recurrence = probe_loop_recurrence(function, loop)
    memory = recurrence.get("candidate_memory")
    if memory is None:
        return {"status": "NOT_PROVEN", "recurrence": recurrence}
    preheader_stores = [
        instruction for instruction in blocks[loop.preheaders[0]].instructions
        if instruction.opcode is IROpcode.STORE and instruction.memory == memory
    ] if len(loop.preheaders) == 1 else []
    initial = None
    if len(preheader_stores) == 1 and len(preheader_stores[0].operands) == 2:
        initial = _constant_register(preheader_stores[0].operands[1], definitions)
    no_escape = not any(
        instruction.opcode is IROpcode.ADDRESS_OF and instruction.memory == memory
        for block in function.blocks for instruction in block.instructions
    )
    updates = recurrence.get("recurrence_store_sites_in_loop", [])
    status = (
        "PASS"
        if initial == 0
        and recurrence.get("all_reachable_abstract_backedge_states_one_update") is True
        and updates
        and all(item.get("step") == 1 for item in updates)
        and all(item.get("other_store") is False for item in recurrence.get("abstract_backedge_states", []))
        and not recurrence.get("opaque_terminators")
        and no_escape
        else "NOT_PROVEN"
    )
    return {
        "status": status,
        "induction_memory": memory,
        "initializer": initial,
        "backedge_steps": [item.get("step") for item in updates],
        "all_abstract_backedges_update_once": recurrence.get("all_reachable_abstract_backedge_states_one_update"),
        "induction_storage_does_not_escape": no_escape,
        "condition_recognizer": recurrence.get("condition_recognizer"),
        "backedges": recurrence.get("abstract_backedge_states", []),
        "scope": "IR CFG over-approximation plus source while condition; not a general loop proof or SIMD legality result",
    }


def _length_relation(
    state: State,
    length_name: str,
    bound_affine: Affine,
    index_affine: Affine,
    induction_name: str,
) -> tuple[int, int] | None:
    length_affine = state.affines.get(length_name, _identity(length_name))
    if length_affine == bound_affine:
        expected = Affine.variable(induction_name)
        if index_affine.coefficients == expected.coefficients:
            return (1, index_affine.constant)
    for left, right in state.equalities:
        if left == length_affine:
            scaled = right
        elif right == length_affine:
            scaled = left
        else:
            continue
        coeff = dict(bound_affine.coefficients)
        sc = dict(scaled.coefficients)
        if coeff and set(coeff) == set(sc):
            factors = {sc[name] // coeff[name] for name in coeff if coeff[name] and sc[name] % coeff[name] == 0}
            if len(factors) == 1:
                stride = factors.pop()
                if stride > 0 and scaled.constant == stride * bound_affine.constant:
                    index_coeff = dict(index_affine.coefficients)
                    if index_coeff == {induction_name: stride}:
                        return (stride, index_affine.constant)
    return None


def _prove_access(
    expression: ast.IndexExpression,
    state: State,
    ir_load: dict[str, Any],
    loop_context: dict[str, Any] | None,
) -> dict[str, Any]:
    array_name = expression.array_name
    index_value = _eval(expression.index, state)
    length_name = next((name for name, source in state.length_sources.items() if source == array_name), None)
    length_interval = state.intervals.get(length_name) if length_name is not None else None
    result: dict[str, Any] = {
        "array": array_name,
        "source_line": expression.location.line,
        "index_interval": None if index_value.interval is None else [index_value.interval.low, index_value.interval.high],
        "index_affine": None if index_value.affine is None else index_value.affine.to_dict(),
        "length_symbol": length_name,
        "length_interval": None if length_interval is None else [length_interval.low, length_interval.high],
        "ir_index_type": ir_load["index_register_type"],
        "loop_header": None,
        "conversion_safe": index_value.safe,
        "bounds_status": "UNKNOWN",
        "proof_kind": None,
    }
    if index_value.interval is None or not index_value.safe or ir_load["index_register_type"] != IRType.TRYTE.value:
        return result
    if not (TRYTE_MIN <= index_value.interval.low <= index_value.interval.high <= TRYTE_MAX):
        return result
    if length_interval is None or index_value.interval.low < 0:
        return result
    bound_source = index_value.exclusive_upper_source
    if bound_source is not None and length_name is not None:
        bound_affine = state.affines.get(bound_source, _identity(bound_source))
        length_affine = state.affines.get(length_name, _identity(length_name))
        if bound_source == length_name or bound_affine == length_affine or _same_equation(
            state, bound_affine, length_affine
        ):
            if loop_context is not None:
                result["loop_header"] = loop_context["header"]
            result.update(
                bounds_status="PROVEN",
                proof_kind=(
                    "GUARDED_RECTANGULAR_ROW_MAJOR_NEIGHBOR"
                    if index_value.row_major_neighbor
                    else "GUARDED_RECTANGULAR_ROW_MAJOR_INDEX"
                ),
            )
            return result
    if loop_context is None:
        if length_interval.low > index_value.interval.high:
            result.update(bounds_status="PROVEN", proof_kind="STATIC_INDEX_BELOW_GUARDED_SLICE_LENGTH")
        return result

    result["loop_header"] = loop_context["header"]
    if loop_context["ir_proof"]["status"] != "PASS" or length_name is None or index_value.affine is None:
        return result
    relation = _length_relation(
        state,
        length_name,
        loop_context["bound_affine"],
        index_value.affine,
        loop_context["induction_name"],
    )
    if relation is None:
        return result
    stride, offset = relation
    if stride <= 0 or offset < 0 or offset >= stride:
        return result
    result.update(
        bounds_status="PROVEN",
        proof_kind=("COUNTED_LOOP_SAME_LENGTH" if stride == 1 else "COUNTED_LOOP_AFFINE_GROUPED_SLICE"),
        induction_range=[0, loop_context["bound_interval"].high - 1],
        bound_range=[loop_context["bound_interval"].low, loop_context["bound_interval"].high],
        stride=stride,
        offset=offset,
    )
    return result


def _collect_loop_accesses(
    block: ast.Block,
    initial_state: State,
    loop_context: dict[str, Any],
    ir_loads: dict[tuple[str, int], list[dict[str, Any]]],
    function: IRFunction | None = None,
    loop_by_line: dict[int, Any] | None = None,
    nested_loop_rows: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    state = initial_state.clone()
    induction_name = loop_context["induction_name"]
    bound = loop_context["bound_interval"]
    if bound.low <= 0 or bound.high <= 0:
        return []
    state.intervals[induction_name] = Interval(0, bound.high - 1)
    state.affines[induction_name] = _identity(induction_name)
    state.length_sources[induction_name] = None
    state.types[induction_name] = "i64"
    state.induction_bounds[induction_name] = loop_context["bound_name"]
    if loop_context["ir_proof"]["status"] == "PASS":
        state.proven_inductions.add(induction_name)
    result: list[dict[str, Any]] = []

    def visit_expr(expression: Any, local: State) -> None:
        for index_expression in _walk_indexes(expression):
            loads = ir_loads.get((index_expression.array_name, index_expression.location.line), [])
            if len(loads) != 1:
                result.append({
                    "array": index_expression.array_name,
                    "source_line": index_expression.location.line,
                    "bounds_status": "UNKNOWN",
                    "blocker": "IR_SLICE_LOAD_NOT_UNIQUELY_MATCHED_BY_SOURCE_LINE_AND_PARAMETER",
                })
                continue
            ir_load = dict(loads[0])
            ir_load["inside_loop"] = ir_load["block"] in loop_context["blocks"]
            if not ir_load["inside_loop"]:
                result.append({
                    "array": index_expression.array_name,
                    "source_line": index_expression.location.line,
                    "bounds_status": "UNKNOWN",
                    "blocker": "SOURCE_ACCESS_NOT_IN_MATCHED_NATURAL_LOOP",
                })
                continue
            result.append(_prove_access(index_expression, local, ir_load, loop_context))

    def visit_statements(statements: tuple[Any, ...], local: State) -> None:
        for statement in statements:
            if isinstance(statement, ast.VariableDeclaration):
                if isinstance(statement.initializer, ast.ArrayLiteral):
                    for item in statement.initializer.elements:
                        visit_expr(item, local)
                    value = Value(None, None, safe=False)
                else:
                    visit_expr(statement.initializer, local)
                    value = _eval(statement.initializer, local)
                _write_value(local, statement.name, value, getattr(statement.type_name, "value", str(statement.type_name)))
            elif isinstance(statement, ast.AssignmentStatement):
                visit_expr(statement.value, local)
                if isinstance(statement.target, ast.VariableTarget):
                    _write_value(local, statement.target.name, _eval(statement.value, local))
            elif isinstance(statement, ast.CompoundAssignmentStatement):
                visit_expr(statement.value, local)
            elif isinstance(statement, ast.SwitchStatement):
                visit_expr(statement.expression, local)
                for case in statement.cases:
                    if _case_is_unreachable(statement.expression, case.label):
                        continue
                    branch_truth = _relation_case_truth(case.label)
                    child = local.clone() if branch_truth is None else _refine(local, statement.expression, branch_truth)
                    if child is not None:
                        visit_statements(case.body.statements, child)
            elif isinstance(statement, ast.WhileStatement):
                condition = statement.condition
                line = statement.location.line
                nested_loop = (loop_by_line or {}).get(line)
                if (
                    function is None
                    or nested_loop is None
                    or not isinstance(condition, ast.BinaryExpression)
                    or condition.operator.value != "<"
                    or not isinstance(condition.left, ast.Identifier)
                    or not isinstance(condition.right, ast.Identifier)
                ):
                    if nested_loop_rows is not None:
                        nested_loop_rows.append({
                            "source_line": line,
                            "status": "NOT_PROVEN",
                            "blocker": "NESTED_LOOP_CONTEXT_UNAVAILABLE",
                        })
                    visit_statements(statement.body.statements, local.clone())
                    continue
                induction_name = condition.left.name
                bound_name = condition.right.name
                bound_interval = local.intervals.get(bound_name)
                ir_proof = _loop_ir_proof(function, nested_loop)
                nested_context = {
                    "header": nested_loop.header,
                    "blocks": nested_loop.blocks,
                    "induction_name": induction_name,
                    "bound_name": bound_name,
                    "bound_interval": bound_interval or Interval(_I64_MIN, _I64_MAX),
                    "bound_affine": local.affines.get(bound_name, _identity(bound_name)),
                    "ir_proof": ir_proof,
                }
                nested_accesses = _collect_loop_accesses(
                    statement.body, local, nested_context, ir_loads,
                    function, loop_by_line, nested_loop_rows,
                )
                result.extend(nested_accesses)
                if nested_loop_rows is not None:
                    nested_loop_rows.append({
                        "source_line": line,
                        "header": nested_loop.header,
                        "induction": induction_name,
                        "bound": bound_name,
                        "bound_interval": None if bound_interval is None else [bound_interval.low, bound_interval.high],
                        "ir_recurrence": ir_proof,
                        "slice_accesses": len(nested_accesses),
                        "all_accesses_proven": bool(nested_accesses) and all(
                            item.get("bounds_status") == "PROVEN" for item in nested_accesses
                        ),
                    })
            elif isinstance(statement, ast.ReturnStatement):
                visit_expr(statement.expression, local)

    visit_statements(block.statements, state)
    return result


def _record_indexes(
    expression: Any,
    state: State,
    ir_loads: dict[tuple[str, int], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for index_expression in _walk_indexes(expression):
        loads = ir_loads.get((index_expression.array_name, index_expression.location.line), [])
        if len(loads) != 1:
            result.append({
                "array": index_expression.array_name,
                "source_line": index_expression.location.line,
                "bounds_status": "UNKNOWN",
                "blocker": "IR_SLICE_LOAD_NOT_UNIQUELY_MATCHED_BY_SOURCE_LINE_AND_PARAMETER",
            })
            continue
        result.append(_prove_access(index_expression, state, loads[0], None))
    return result


def _analyze_function(
    workload: str,
    source_path: str,
    function_name: str,
    source_bytes: bytes,
) -> dict[str, Any]:
    source = source_bytes.decode("utf-8")
    program = parse(source)
    function_ast = next((item for item in program.functions if item.name == function_name), None)
    if function_ast is None:
        raise RuntimeError(f"source function {function_name} not found")
    compilation = compile_source(source, OptimizationLevel.O1)
    ir, _assembly = compilation.require_ordinary_artifacts()
    function = _known_function(ir, function_name)
    loops = list(loop_analysis.discover_loop_info(function))
    blocks = {item.name: item for item in function.blocks}
    loop_by_line: dict[int, Any] = {}
    for loop in loops:
        terminator = blocks[loop.header].instructions[-1]
        if terminator.location is None:
            raise RuntimeError(f"loop {loop.header} has no source location")
        loop_by_line[terminator.location.line] = loop
    ir_loads = _ir_slice_loads(function)
    state = State()
    for parameter in function.parameters:
        state.types[parameter.name] = parameter.type.value
        if parameter.type is IRType.I64:
            state.intervals[parameter.name] = Interval(_I64_MIN, _I64_MAX)
            state.affines[parameter.name] = _identity(parameter.name)

    accesses: list[dict[str, Any]] = []
    loop_rows: list[dict[str, Any]] = []

    def visit_block(block: ast.Block, incoming: list[State]) -> list[State]:
        states = incoming
        for statement in block.statements:
            next_states: list[State] = []
            for current in states:
                if isinstance(statement, ast.VariableDeclaration):
                    if isinstance(statement.initializer, ast.ArrayLiteral):
                        for item in statement.initializer.elements:
                            accesses.extend(_record_indexes(item, current, ir_loads))
                        value = Value(None, None, safe=False)
                    else:
                        accesses.extend(_record_indexes(statement.initializer, current, ir_loads))
                        value = _eval(statement.initializer, current)
                    child = current.clone()
                    _write_value(child, statement.name, value, getattr(statement.type_name, "value", str(statement.type_name)))
                    next_states.append(child)
                elif isinstance(statement, ast.AssignmentStatement):
                    accesses.extend(_record_indexes(statement.value, current, ir_loads))
                    child = current.clone()
                    if isinstance(statement.target, ast.VariableTarget):
                        _write_value(child, statement.target.name, _eval(statement.value, current))
                    next_states.append(child)
                elif isinstance(statement, ast.CompoundAssignmentStatement):
                    accesses.extend(_record_indexes(statement.value, current, ir_loads))
                    next_states.append(current.clone())
                elif isinstance(statement, ast.ReturnStatement):
                    accesses.extend(_record_indexes(statement.expression, current, ir_loads))
                elif isinstance(statement, ast.SwitchStatement):
                    for case in statement.cases:
                        if _case_is_unreachable(statement.expression, case.label):
                            continue
                        truth = _relation_case_truth(case.label)
                        child = current.clone() if truth is None else _refine(current, statement.expression, truth)
                        if child is not None:
                            next_states.extend(visit_block(case.body, [child]))
                elif isinstance(statement, ast.WhileStatement):
                    accesses.extend(_record_indexes(statement.condition, current, ir_loads))
                    condition = statement.condition
                    if not (
                        isinstance(condition, ast.BinaryExpression)
                        and condition.operator.value == "<"
                        and isinstance(condition.left, ast.Identifier)
                        and isinstance(condition.right, ast.Identifier)
                    ):
                        loop_rows.append({"source_line": statement.location.line, "status": "NOT_PROVEN", "blocker": "UNSUPPORTED_WHILE_CONDITION"})
                        next_states.append(current.clone())
                        continue
                    line = statement.location.line
                    loop = loop_by_line.get(line)
                    if loop is None:
                        loop_rows.append({"source_line": line, "status": "NOT_PROVEN", "blocker": "NATURAL_LOOP_NOT_MATCHED_BY_SOURCE_LINE"})
                        next_states.append(current.clone())
                        continue
                    induction_name = condition.left.name
                    bound_name = condition.right.name
                    bound_interval = current.intervals.get(bound_name)
                    ir_proof = _loop_ir_proof(function, loop)
                    loop_context = {
                        "header": loop.header,
                        "blocks": loop.blocks,
                        "induction_name": induction_name,
                        "bound_name": bound_name,
                        "bound_interval": bound_interval or Interval(_I64_MIN, _I64_MAX),
                        "bound_affine": current.affines.get(bound_name, _identity(bound_name)),
                        "ir_proof": ir_proof,
                    }
                    nested_loop_rows: list[dict[str, Any]] = []
                    loop_accesses = _collect_loop_accesses(
                        statement.body, current, loop_context, ir_loads,
                        function, loop_by_line, nested_loop_rows,
                    )
                    loop_rows.extend(nested_loop_rows)
                    for access in loop_accesses:
                        accesses.append(access)
                    loop_rows.append({
                        "source_line": line,
                        "header": loop.header,
                        "induction": induction_name,
                        "bound": bound_name,
                        "bound_interval": None if bound_interval is None else [bound_interval.low, bound_interval.high],
                        "ir_recurrence": ir_proof,
                        "slice_accesses": len(loop_accesses),
                        "all_accesses_proven": bool(loop_accesses) and all(item.get("bounds_status") == "PROVEN" for item in loop_accesses),
                    })
                    next_states.append(current.clone())
                else:
                    next_states.append(current.clone())
            states = next_states
            if not states:
                break
        return states

    visit_block(function_ast.body, [state])
    loop_rows.sort(key=lambda row: row["source_line"])
    return {
        "workload": workload,
        "source_path": source_path,
        "source_sha256": _source_sha256(source_bytes),
        "function": function_name,
        "loops": loop_rows,
        "slice_reads": accesses,
        "all_slice_reads_proven": bool(accesses) and all(item.get("bounds_status") == "PROVEN" for item in accesses),
    }


def _checkout_identity() -> tuple[str, str]:
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    return commit, tree


def analyze_workloads() -> dict[str, Any]:
    selected = [item for item in WORKLOADS if item[0] in {"energy", "point-cloud"}]
    functions = [
        _analyze_function(name, path, function, (ROOT / path).read_bytes())
        for name, path, function in selected
    ]
    proven = sum(
        item.get("bounds_status") == "PROVEN"
        for function in functions for item in function["slice_reads"]
    )
    total = sum(len(function["slice_reads"]) for function in functions)
    checkout_sha, checkout_tree = _checkout_identity()
    return {
        "schema": "s3-1.11-guarded-slice-bounds-v2",
        "experiment_control_sha": EXPERIMENT_CONTROL_SHA,
        "experiment_control_tree": EXPERIMENT_CONTROL_TREE,
        "checkout_sha": checkout_sha,
        "checkout_tree": checkout_tree,
        "optimization": "O1",
        "python": platform.python_version(),
        "language_contracts": {
            "i64_arithmetic": "checked; interval overflow causes UNKNOWN",
            "i64_to_tryte": f"checked conversion to [{TRYTE_MIN}, {TRYTE_MAX}]",
            "relational_match": "RELATE yields -1 for true and 0 for false",
            "slice_index_ir_type_required": "tryte",
        },
        "functions": functions,
        "summary": {
            "functions": len(functions),
            "slice_reads": total,
            "slice_bounds_proven": proven,
            "slice_bounds_unknown": total - proven,
            "vectorization_authorized": False,
            "dependence_proofs": 0,
        },
        "limitations": [
            "Only the exact recognized source guard forms and counted-loop form are analyzed.",
            "Loop reasoning requires zero initialization and unit updates on every abstract CFG backedge.",
            "This proves the observed scalar slice bounds only; it does not prove aliasing, dependence, vector legality, or timing benefit.",
            "Unknown syntax, arithmetic overflow, missing equality guards, or an unrecognized recurrence remains UNKNOWN.",
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    encoded = json.dumps(analyze_workloads(), sort_keys=True, indent=2, allow_nan=False) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(encoded, encoding="utf-8")
    else:
        print(encoded, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
