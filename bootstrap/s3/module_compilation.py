"""Prepare deterministic multi-file S3 programs for the existing pipeline."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, replace

from . import ast
from .diagnostics import DiagnosticCode, SemanticError
from .lexer import SyntaxMode, Token, tokenize
from .module_graph import (
    ImportEdge,
    ModuleGraph,
    ModuleId,
    SourceUnit,
    import_edges_from_program,
    normalize_logical_path,
    source_unit_from_program,
)
from .parser import parse_tokens


SourceCollection = Mapping[str, str] | Iterable[tuple[str, str]]


@dataclass(frozen=True, slots=True)
class ModuleCompilationPlan:
    tokens: tuple[Token, ...]
    program: ast.Program
    graph: ModuleGraph


def prepare_module_compilation(
    sources: SourceCollection,
    *,
    entry_module: ModuleId | str = "main",
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> ModuleCompilationPlan:
    if mode is not SyntaxMode.V0_6:
        raise SemanticError(
            "multi-file compilation requires source syntax 0.6",
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )
    parsed = _parse_source_units(sources, mode)
    units = tuple(unit for unit, _program, _tokens in parsed)
    imports = tuple(
        edge
        for unit, program, _tokens in parsed
        for edge in import_edges_from_program(unit.module_id, program)
    )
    graph = ModuleGraph.build(units, imports, entry_module=entry_module)
    program_by_module = {
        unit.module_id: program for unit, program, _tokens in parsed
    }
    synthetic = _build_synthetic_program(graph, program_by_module)
    tokens = tuple(token for _unit, _program, tokens in parsed for token in tokens)
    return ModuleCompilationPlan(tokens, synthetic, graph)


def _parse_source_units(
    sources: SourceCollection,
    mode: SyntaxMode,
) -> tuple[tuple[SourceUnit, ast.Program, tuple[Token, ...]], ...]:
    items = _source_items(sources)
    if not items:
        raise SemanticError(
            "multi-file compilation requires at least one source unit",
            diagnostic_code=DiagnosticCode.MODULE_ENTRY_INVALID,
        )
    parsed: list[tuple[SourceUnit, ast.Program, tuple[Token, ...]]] = []
    for logical_path, source in items:
        tokens = tokenize(source, mode=mode)
        program = parse_tokens(tokens, mode=mode)
        unit = source_unit_from_program(logical_path, source, program)
        parsed.append((unit, program, tokens))
    return tuple(parsed)


def _source_items(sources: SourceCollection) -> tuple[tuple[str, str], ...]:
    raw_items = sources.items() if isinstance(sources, Mapping) else sources
    by_path: dict[str, str] = {}
    for logical_path, source in raw_items:
        normalized = normalize_logical_path(logical_path)
        if normalized in by_path:
            raise SemanticError(
                f"duplicate source unit path '{normalized}'",
                diagnostic_code=DiagnosticCode.MODULE_DUPLICATE,
            )
        by_path[normalized] = source
    return tuple(sorted(by_path.items()))


def _build_synthetic_program(
    graph: ModuleGraph,
    program_by_module: dict[ModuleId, ast.Program],
) -> ast.Program:
    module_functions = _collect_module_functions(graph, program_by_module)
    internal_names = _internal_function_names(
        graph,
        module_functions,
        entry_module=graph.entry_module,
    )
    internal_type_names = _internal_type_names(
        graph,
        program_by_module,
        entry_module=graph.entry_module,
    )
    namespaces = _resolve_namespaces(
        graph,
        program_by_module,
        module_functions,
        internal_names,
    )

    functions: list[ast.FunctionDeclaration] = []
    records: list[ast.RecordDeclaration] = []
    enums: list[ast.EnumDeclaration] = []
    for module in graph.ordered_modules:
        program = program_by_module[module]
        namespace = namespaces[module]
        type_namespace = internal_type_names[module]
        records.extend(
            _rewrite_record(record, type_namespace)
            for record in program.records
        )
        enums.extend(
            _rewrite_enum(enum, type_namespace)
            for enum in program.enums
        )
        for function in program.functions:
            functions.append(
                _rewrite_function(
                    function,
                    internal_names[(module, function.name)],
                    namespace,
                    type_namespace,
                )
            )
    location = functions[0].location if functions else next(iter(program_by_module.values())).location
    return ast.Program(
        tuple(functions),
        location,
        records=tuple(records),
        enums=tuple(enums),
    )


def _collect_module_functions(
    graph: ModuleGraph,
    program_by_module: dict[ModuleId, ast.Program],
) -> dict[ModuleId, dict[str, ast.FunctionDeclaration]]:
    result: dict[ModuleId, dict[str, ast.FunctionDeclaration]] = {}
    for module in graph.ordered_modules:
        functions: dict[str, ast.FunctionDeclaration] = {}
        for function in program_by_module[module].functions:
            if function.name in functions:
                raise SemanticError(
                    f"duplicate function '{function.name}' in module '{module}'",
                    function.location,
                )
            functions[function.name] = function
        result[module] = functions
    return result


def _internal_function_names(
    graph: ModuleGraph,
    module_functions: dict[ModuleId, dict[str, ast.FunctionDeclaration]],
    *,
    entry_module: ModuleId,
) -> dict[tuple[ModuleId, str], str]:
    names: dict[tuple[ModuleId, str], str] = {}
    for module in graph.ordered_modules:
        for name in sorted(module_functions[module]):
            if module == entry_module and name == "main":
                internal = "main"
            else:
                internal = f"__s3mod_{'_'.join(module.parts)}__{name}"
            names[(module, name)] = internal
    return names


def _internal_type_names(
    graph: ModuleGraph,
    program_by_module: dict[ModuleId, ast.Program],
    *,
    entry_module: ModuleId,
) -> dict[ModuleId, dict[str, str]]:
    names: dict[ModuleId, dict[str, str]] = {}
    for module in graph.ordered_modules:
        program = program_by_module[module]
        module_names: dict[str, str] = {}
        for name in sorted(
            {record.name for record in program.records}
            | {enum.name for enum in program.enums}
        ):
            if module == entry_module:
                internal = name
            else:
                internal = f"__s3mod_{'_'.join(module.parts)}__type_{name}"
            module_names[name] = internal
        names[module] = module_names
    return names


def _resolve_namespaces(
    graph: ModuleGraph,
    program_by_module: dict[ModuleId, ast.Program],
    module_functions: dict[ModuleId, dict[str, ast.FunctionDeclaration]],
    internal_names: dict[tuple[ModuleId, str], str],
) -> dict[ModuleId, dict[str, str]]:
    imports_by_module: dict[ModuleId, list[ImportEdge]] = {
        module: [] for module in graph.ordered_modules
    }
    for edge in graph.imports:
        imports_by_module[edge.importing_module].append(edge)

    namespaces: dict[ModuleId, dict[str, str]] = {}
    for module in graph.ordered_modules:
        namespace = {
            name: internal_names[(module, name)]
            for name in module_functions[module]
        }
        for edge in imports_by_module[module]:
            if edge.local_name in module_functions[module]:
                raise SemanticError(
                    (
                        f"import local name '{edge.local_name}' conflicts with "
                        f"function in module '{module}'"
                    ),
                    edge.location,
                    diagnostic_code=DiagnosticCode.IMPORT_CONFLICT,
                )
            target = module_functions[edge.imported_module].get(edge.symbol)
            if target is None:
                raise SemanticError(
                    (
                        f"module '{edge.imported_module}' does not export "
                        f"unknown symbol '{edge.symbol}'"
                    ),
                    edge.location,
                    diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
                )
            if not target.exported:
                raise SemanticError(
                    (
                        f"function '{edge.symbol}' in module "
                        f"'{edge.imported_module}' is private"
                    ),
                    edge.location,
                    diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                )
            namespace[edge.local_name] = internal_names[
                (edge.imported_module, edge.symbol)
            ]
        program = program_by_module[module]
        if module == graph.entry_module and "main" not in module_functions[module]:
            raise SemanticError(
                f"entry module '{module}' must declare a 'main' function",
                program.location,
                diagnostic_code=DiagnosticCode.MODULE_ENTRY_INVALID,
            )
        namespaces[module] = namespace
    return namespaces


def _rewrite_function(
    function: ast.FunctionDeclaration,
    internal_name: str,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.FunctionDeclaration:
    signature = replace(
        function.signature,
        name=internal_name,
        parameters=tuple(
            replace(
                parameter,
                type_name=_rewrite_type(parameter.type_name, type_namespace),
            )
            for parameter in function.parameters
        ),
        return_type=_rewrite_type(function.return_type, type_namespace),
    )
    return ast.FunctionDeclaration(
        signature,
        _rewrite_block(function.body, namespace, type_namespace),
        function.location,
        function.exported,
    )


def _rewrite_record(
    record: ast.RecordDeclaration,
    type_namespace: dict[str, str],
) -> ast.RecordDeclaration:
    return replace(
        record,
        name=type_namespace.get(record.name, record.name),
        fields=tuple(
            replace(
                field,
                type_name=_rewrite_type(field.type_name, type_namespace),
            )
            for field in record.fields
        ),
    )


def _rewrite_enum(
    enum: ast.EnumDeclaration,
    type_namespace: dict[str, str],
) -> ast.EnumDeclaration:
    return replace(enum, name=type_namespace.get(enum.name, enum.name))


def _rewrite_type(
    type_name: ast.DeclaredType,
    type_namespace: dict[str, str],
) -> ast.DeclaredType:
    if isinstance(type_name, ast.NominalType):
        return replace(
            type_name,
            name=type_namespace.get(type_name.name, type_name.name),
        )
    if isinstance(type_name, ast.ArrayType):
        return replace(
            type_name,
            element_type=_rewrite_type(type_name.element_type, type_namespace),
        )
    return type_name


def _rewrite_block(
    block: ast.Block,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.Block:
    return replace(
        block,
        statements=tuple(
            _rewrite_statement(statement, namespace, type_namespace)
            for statement in block.statements
        ),
    )


def _rewrite_statement(
    statement: ast.Statement,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.Statement:
    if isinstance(statement, ast.VariableDeclaration):
        return replace(
            statement,
            type_name=_rewrite_type(statement.type_name, type_namespace),
            initializer=_rewrite_initializer(
                statement.initializer,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(statement, ast.AssignmentStatement):
        return replace(
            statement,
            target=_rewrite_target(statement.target, namespace, type_namespace),
            value=_rewrite_initializer(
                statement.value,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(statement, ast.CompoundAssignmentStatement):
        return replace(
            statement,
            target=_rewrite_target(statement.target, namespace, type_namespace),
            value=_rewrite_initializer(
                statement.value,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(statement, ast.DiscardStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(statement, ast.ReturnStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(statement, ast.SwitchStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                namespace,
                type_namespace,
            ),
            cases=tuple(
                replace(
                    case,
                    label=_rewrite_match_label(
                        case.label,
                        namespace,
                        type_namespace,
                    ),
                    body=_rewrite_block(case.body, namespace, type_namespace),
                )
                for case in statement.cases
            ),
        )
    if isinstance(statement, ast.WhileStatement):
        return replace(
            statement,
            condition=_rewrite_expression(
                statement.condition,
                namespace,
                type_namespace,
            ),
            body=_rewrite_block(statement.body, namespace, type_namespace),
        )
    if isinstance(statement, ast.ForStatement):
        return replace(
            statement,
            start_expression=_rewrite_expression(
                statement.start_expression,
                namespace,
                type_namespace,
            ),
            end_expression=_rewrite_expression(
                statement.end_expression,
                namespace,
                type_namespace,
            ),
            step_expression=_rewrite_expression(
                statement.step_expression,
                namespace,
                type_namespace,
            ),
            body=_rewrite_block(statement.body, namespace, type_namespace),
        )
    return statement


def _rewrite_target(
    target: ast.AssignmentTarget,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.AssignmentTarget:
    if isinstance(target, ast.IndexTarget):
        return replace(
            target,
            index=_rewrite_expression(target.index, namespace, type_namespace),
        )
    return target


def _rewrite_initializer(
    initializer: ast.Initializer,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.Initializer:
    if isinstance(initializer, ast.ArrayLiteral):
        return replace(
            initializer,
            elements=tuple(
                _rewrite_expression(element, namespace, type_namespace)
                for element in initializer.elements
            ),
        )
    return _rewrite_expression(initializer, namespace, type_namespace)


def _rewrite_expression(
    expression: ast.Expression,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.Expression:
    if isinstance(expression, ast.CallExpression):
        callee = expression.callee
        if isinstance(callee, ast.Identifier):
            callee = replace(
                callee,
                name=namespace.get(callee.name, callee.name),
            )
        else:
            callee = _rewrite_expression(callee, namespace, type_namespace)
        return replace(
            expression,
            callee=callee,
            arguments=tuple(
                replace(
                    argument,
                    expression=_rewrite_expression(
                        argument.expression,
                        namespace,
                        type_namespace,
                    ),
                )
                for argument in expression.arguments
            ),
        )
    if isinstance(expression, ast.RecordExpression):
        return replace(
            expression,
            type_name=type_namespace.get(expression.type_name, expression.type_name),
            fields=tuple(
                replace(
                    field,
                    expression=_rewrite_expression(
                        field.expression,
                        namespace,
                        type_namespace,
                    ),
                )
                for field in expression.fields
            ),
        )
    if isinstance(expression, ast.FieldAccessExpression):
        return replace(
            expression,
            target=_rewrite_field_access_target(
                expression.target,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(expression, ast.IndexExpression):
        return replace(
            expression,
            target=_rewrite_expression(expression.target, namespace, type_namespace),
            index=_rewrite_expression(expression.index, namespace, type_namespace),
        )
    if isinstance(expression, ast.SliceExpression):
        return replace(
            expression,
            target=_rewrite_expression(expression.target, namespace, type_namespace),
            start=_rewrite_expression(expression.start, namespace, type_namespace),
            end=_rewrite_expression(expression.end, namespace, type_namespace),
        )
    if isinstance(expression, ast.UnaryExpression):
        return replace(
            expression,
            operand=_rewrite_expression(
                expression.operand,
                namespace,
                type_namespace,
            ),
        )
    if isinstance(expression, ast.BinaryExpression):
        return replace(
            expression,
            left=_rewrite_expression(expression.left, namespace, type_namespace),
            right=_rewrite_expression(expression.right, namespace, type_namespace),
        )
    if isinstance(expression, ast.MatchExpression):
        return replace(
            expression,
            selector=_rewrite_expression(
                expression.selector,
                namespace,
                type_namespace,
            ),
            cases=tuple(
                replace(
                    case,
                    label=_rewrite_match_label(
                        case.label,
                        namespace,
                        type_namespace,
                    ),
                    expression=_rewrite_expression(
                        case.expression,
                        namespace,
                        type_namespace,
                    ),
                )
                for case in expression.cases
            ),
        )
    if isinstance(expression, ast.LenExpression):
        return replace(
            expression,
            argument=_rewrite_expression(
                expression.argument,
                namespace,
                type_namespace,
            ),
        )
    return expression


def _rewrite_match_label(
    label: ast.MatchCaseLabel,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.MatchCaseLabel:
    if isinstance(label, ast.FieldAccessExpression):
        rewritten = _rewrite_expression(label, namespace, type_namespace)
        assert isinstance(rewritten, ast.FieldAccessExpression)
        return rewritten
    return label


def _rewrite_field_access_target(
    target: ast.Expression,
    namespace: dict[str, str],
    type_namespace: dict[str, str],
) -> ast.Expression:
    if isinstance(target, ast.Identifier) and target.name in type_namespace:
        return replace(target, name=type_namespace[target.name])
    return _rewrite_expression(target, namespace, type_namespace)
