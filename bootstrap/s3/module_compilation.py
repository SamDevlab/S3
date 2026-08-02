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


@dataclass(frozen=True, slots=True)
class _RewriteContext:
    module: ModuleId
    graph: ModuleGraph
    program_by_module: dict[ModuleId, ast.Program]
    module_functions: dict[ModuleId, dict[str, ast.FunctionDeclaration]]
    function_namespace: dict[str, str]
    type_namespace: dict[str, str]
    internal_names: dict[tuple[ModuleId, str], str]
    internal_type_names: dict[ModuleId, dict[str, str]]
    imported_modules: frozenset[ModuleId]
    local_names: frozenset[str]


@dataclass(frozen=True, slots=True)
class _ModuleTypeSymbols:
    records: dict[str, ast.RecordDeclaration]
    enums: dict[str, ast.EnumDeclaration]

    def get(self, name: str) -> ast.RecordDeclaration | ast.EnumDeclaration | None:
        return self.records.get(name) or self.enums.get(name)


@dataclass(frozen=True, slots=True)
class _ResolvedNamespaces:
    functions: dict[ModuleId, dict[str, str]]
    types: dict[ModuleId, dict[str, str]]


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
    module_types = _collect_module_types(graph, program_by_module)
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
        module_types,
        internal_names,
        internal_type_names,
    )

    functions: list[ast.FunctionDeclaration] = []
    records: list[ast.RecordDeclaration] = []
    enums: list[ast.EnumDeclaration] = []
    for module in graph.ordered_modules:
        program = program_by_module[module]
        namespace = namespaces.functions[module]
        type_namespace = namespaces.types[module]
        context = _RewriteContext(
            module,
            graph,
            program_by_module,
            module_functions,
            namespace,
            type_namespace,
            internal_names,
            internal_type_names,
            frozenset(
                edge.imported_module
                for edge in graph.imports
                if edge.importing_module == module
            ),
            frozenset(),
        )
        records.extend(
            _rewrite_record(record, context)
            for record in program.records
        )
        enums.extend(
            _rewrite_enum(enum, context)
            for enum in program.enums
        )
        for function in program.functions:
            functions.append(
                _rewrite_function(
                    function,
                    internal_names[(module, function.name)],
                    replace(
                        context,
                        local_names=_function_local_names(function),
                    ),
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


def _collect_module_types(
    graph: ModuleGraph,
    program_by_module: dict[ModuleId, ast.Program],
) -> dict[ModuleId, _ModuleTypeSymbols]:
    result: dict[ModuleId, _ModuleTypeSymbols] = {}
    for module in graph.ordered_modules:
        records: dict[str, ast.RecordDeclaration] = {}
        enums: dict[str, ast.EnumDeclaration] = {}
        for record in program_by_module[module].records:
            if record.name in records or record.name in enums:
                raise SemanticError(
                    f"duplicate type '{record.name}' in module '{module}'",
                    record.location,
                )
            records[record.name] = record
        for enum in program_by_module[module].enums:
            if enum.name in records or enum.name in enums:
                raise SemanticError(
                    f"duplicate type '{enum.name}' in module '{module}'",
                    enum.location,
                )
            enums[enum.name] = enum
        result[module] = _ModuleTypeSymbols(records, enums)
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
    module_types: dict[ModuleId, _ModuleTypeSymbols],
    internal_names: dict[tuple[ModuleId, str], str],
    internal_type_names: dict[ModuleId, dict[str, str]],
) -> _ResolvedNamespaces:
    imports_by_module: dict[ModuleId, list[ImportEdge]] = {
        module: [] for module in graph.ordered_modules
    }
    for edge in graph.imports:
        imports_by_module[edge.importing_module].append(edge)

    function_namespaces: dict[ModuleId, dict[str, str]] = {}
    type_namespaces: dict[ModuleId, dict[str, str]] = {}
    for module in graph.ordered_modules:
        function_namespace = {
            name: internal_names[(module, name)]
            for name in module_functions[module]
        }
        type_namespace = dict(internal_type_names[module])
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
            type_target = module_types[edge.imported_module].get(edge.symbol)
            if target is not None and target.exported and type_target is not None and type_target.exported:
                raise SemanticError(
                    (
                        f"imported symbol '{edge.symbol}' in module "
                        f"'{edge.imported_module}' is ambiguous between "
                        "function and type"
                    ),
                    edge.location,
                    diagnostic_code=DiagnosticCode.IMPORT_CONFLICT,
                )
            if target is not None and (target.exported or type_target is None):
                if not target.exported:
                    raise SemanticError(
                        (
                            f"function '{edge.symbol}' in module "
                            f"'{edge.imported_module}' is private"
                        ),
                        edge.location,
                        diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                    )
                function_namespace[edge.local_name] = internal_names[
                    (edge.imported_module, edge.symbol)
                ]
                continue
            if type_target is not None:
                if edge.alias is not None:
                    raise SemanticError(
                        "type import aliases are not supported yet",
                        edge.location,
                        diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                    )
                if edge.local_name in type_namespace:
                    raise SemanticError(
                        (
                            f"import local name '{edge.local_name}' conflicts with "
                            f"type in module '{module}'"
                        ),
                        edge.location,
                        diagnostic_code=DiagnosticCode.IMPORT_CONFLICT,
                    )
                if not type_target.exported:
                    raise SemanticError(
                        (
                            f"type '{edge.symbol}' in module "
                            f"'{edge.imported_module}' is private"
                        ),
                        edge.location,
                        diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                    )
                type_namespace[edge.local_name] = internal_type_names[
                    edge.imported_module
                ][edge.symbol]
                continue
            if target is None:
                raise SemanticError(
                    (
                        f"module '{edge.imported_module}' does not export "
                        f"unknown symbol '{edge.symbol}'"
                    ),
                    edge.location,
                    diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
                )
        program = program_by_module[module]
        if module == graph.entry_module and "main" not in module_functions[module]:
            raise SemanticError(
                f"entry module '{module}' must declare a 'main' function",
                program.location,
                diagnostic_code=DiagnosticCode.MODULE_ENTRY_INVALID,
            )
        function_namespaces[module] = function_namespace
        type_namespaces[module] = type_namespace
    return _ResolvedNamespaces(function_namespaces, type_namespaces)


def _rewrite_function(
    function: ast.FunctionDeclaration,
    internal_name: str,
    context: _RewriteContext,
) -> ast.FunctionDeclaration:
    signature = replace(
        function.signature,
        name=internal_name,
        parameters=tuple(
            replace(
                parameter,
                type_name=_rewrite_type(parameter.type_name, context),
            )
            for parameter in function.parameters
        ),
        return_type=_rewrite_type(function.return_type, context),
    )
    return ast.FunctionDeclaration(
        signature,
        _rewrite_block(function.body, context),
        function.location,
        function.exported,
    )


def _rewrite_record(
    record: ast.RecordDeclaration,
    context: _RewriteContext,
) -> ast.RecordDeclaration:
    return replace(
        record,
        name=context.type_namespace.get(record.name, record.name),
        fields=tuple(
            replace(
                field,
                type_name=_rewrite_type(field.type_name, context),
            )
            for field in record.fields
        ),
    )


def _rewrite_enum(
    enum: ast.EnumDeclaration,
    context: _RewriteContext,
) -> ast.EnumDeclaration:
    return replace(
        enum,
        name=context.type_namespace.get(enum.name, enum.name),
        variants=tuple(
            replace(
                variant,
                payload_fields=tuple(
                    replace(
                        field,
                        type_name=_rewrite_type(field.type_name, context),
                    )
                    for field in variant.payload_fields
                ),
            )
            for variant in enum.variants
        ),
    )


def _rewrite_type(
    type_name: ast.DeclaredType,
    context: _RewriteContext,
) -> ast.DeclaredType:
    if isinstance(type_name, ast.NominalType):
        return replace(
            type_name,
            name=_rewrite_nominal_type_name(
                type_name.name,
                type_name.location,
                context,
            ),
        )
    if isinstance(type_name, ast.ArrayType):
        return replace(
            type_name,
            element_type=_rewrite_type(type_name.element_type, context),
        )
    return type_name


def _rewrite_nominal_type_name(
    name: str,
    location,
    context: _RewriteContext,
) -> str:
    if "." not in name:
        return context.type_namespace.get(name, name)
    parts = tuple(name.split("."))
    module_match = _module_for_parts(parts, context)
    if module_match is None:
        return context.type_namespace.get(name, name)
    module, module_length = module_match
    member_parts = parts[module_length:]
    if len(member_parts) != 1:
        raise SemanticError(
            f"type '{name}' is not a nominal type",
            location,
        )
    member = member_parts[0]
    type_member = _module_type(module, member, context)
    if type_member is None:
        if context.module_functions[module].get(member) is not None:
            raise SemanticError(
                f"function '{module}.{member}' cannot be used as a type",
                location,
            )
        raise SemanticError(
            f"module '{module}' has no type '{member}'",
            location,
            diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        )
    if not type_member.exported:
        raise SemanticError(
            f"type '{member}' in module '{module}' is private",
            location,
            diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        )
    return context.internal_type_names[module][member]


def _rewrite_constructor_type_name(
    name: str,
    location,
    context: _RewriteContext,
) -> str:
    if "." in name:
        enum_name, variant_name = name.rsplit(".", 1)
        try:
            rewritten_enum = _rewrite_nominal_type_name(enum_name, location, context)
            return f"{rewritten_enum}.{variant_name}"
        except SemanticError:
            pass
    return _rewrite_nominal_type_name(name, location, context)


def _rewrite_block(
    block: ast.Block,
    context: _RewriteContext,
) -> ast.Block:
    return replace(
        block,
        statements=tuple(
            _rewrite_statement(statement, context)
            for statement in block.statements
        ),
    )


def _rewrite_statement(
    statement: ast.Statement,
    context: _RewriteContext,
) -> ast.Statement:
    if isinstance(statement, ast.VariableDeclaration):
        return replace(
            statement,
            type_name=_rewrite_type(statement.type_name, context),
            initializer=_rewrite_initializer(
                statement.initializer,
                context,
            ),
        )
    if isinstance(statement, ast.AssignmentStatement):
        return replace(
            statement,
            target=_rewrite_target(statement.target, context),
            value=_rewrite_initializer(
                statement.value,
                context,
            ),
        )
    if isinstance(statement, ast.CompoundAssignmentStatement):
        return replace(
            statement,
            target=_rewrite_target(statement.target, context),
            value=_rewrite_initializer(
                statement.value,
                context,
            ),
        )
    if isinstance(statement, ast.DiscardStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                context,
            ),
        )
    if isinstance(statement, ast.ReturnStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                context,
            ),
        )
    if isinstance(statement, ast.SwitchStatement):
        return replace(
            statement,
            expression=_rewrite_expression(
                statement.expression,
                context,
            ),
            cases=tuple(
                replace(
                    case,
                    label=_rewrite_match_label(
                        case.label,
                        context,
                    ),
                    body=_rewrite_block(case.body, context),
                )
                for case in statement.cases
            ),
        )
    if isinstance(statement, ast.WhileStatement):
        return replace(
            statement,
            condition=_rewrite_expression(
                statement.condition,
                context,
            ),
            body=_rewrite_block(statement.body, context),
        )
    if isinstance(statement, ast.ForStatement):
        return replace(
            statement,
            start_expression=_rewrite_expression(
                statement.start_expression,
                context,
            ),
            end_expression=_rewrite_expression(
                statement.end_expression,
                context,
            ),
            step_expression=_rewrite_expression(
                statement.step_expression,
                context,
            ),
            body=_rewrite_block(statement.body, context),
        )
    return statement


def _rewrite_target(
    target: ast.AssignmentTarget,
    context: _RewriteContext,
) -> ast.AssignmentTarget:
    if isinstance(target, ast.IndexTarget):
        return replace(
            target,
            index=_rewrite_expression(target.index, context),
        )
    return target


def _rewrite_initializer(
    initializer: ast.Initializer,
    context: _RewriteContext,
) -> ast.Initializer:
    if isinstance(initializer, ast.ArrayLiteral):
        return replace(
            initializer,
            elements=tuple(
                _rewrite_expression(element, context)
                for element in initializer.elements
            ),
        )
    return _rewrite_expression(initializer, context)


def _rewrite_expression(
    expression: ast.Expression,
    context: _RewriteContext,
) -> ast.Expression:
    if isinstance(expression, ast.CallExpression):
        if isinstance(expression.callee, ast.Identifier) and _is_visible_module(
            expression.callee.name,
            context,
        ):
            raise SemanticError(
                f"module '{expression.callee.name}' cannot be called",
                expression.location,
            )
        qualified_call = _rewrite_qualified_module_call(expression, context)
        if qualified_call is not None:
            return qualified_call
        callee = expression.callee
        if isinstance(callee, ast.Identifier):
            callee = replace(
                callee,
                name=context.function_namespace.get(callee.name, callee.name),
            )
        else:
            callee = _rewrite_expression(callee, context)
        return replace(
            expression,
            callee=callee,
            arguments=tuple(
                replace(
                    argument,
                    expression=_rewrite_expression(
                        argument.expression,
                        context,
                    ),
                )
                for argument in expression.arguments
            ),
        )
    if isinstance(expression, ast.RecordExpression):
        return replace(
            expression,
            type_name=_rewrite_constructor_type_name(
                expression.type_name,
                expression.location,
                context,
            ),
            fields=tuple(
                replace(
                    field,
                    expression=_rewrite_expression(
                        field.expression,
                        context,
                    ),
                )
                for field in expression.fields
            ),
        )
    if isinstance(expression, ast.FieldAccessExpression):
        qualified = _rewrite_qualified_module_member(expression, context)
        if qualified is not None:
            return qualified
        return replace(expression, target=_rewrite_field_access_target(expression.target, context))
    if isinstance(expression, ast.IndexExpression):
        if isinstance(expression.target, ast.Identifier) and _is_visible_module(
            expression.target.name,
            context,
        ):
            raise SemanticError(
                f"module '{expression.target.name}' cannot be indexed",
                expression.location,
            )
        return replace(
            expression,
            target=_rewrite_expression(expression.target, context),
            index=_rewrite_expression(expression.index, context),
        )
    if isinstance(expression, ast.SliceExpression):
        return replace(
            expression,
            target=_rewrite_expression(expression.target, context),
            start=_rewrite_expression(expression.start, context),
            end=_rewrite_expression(expression.end, context),
        )
    if isinstance(expression, ast.UnaryExpression):
        return replace(
            expression,
            operand=_rewrite_expression(
                expression.operand,
                context,
            ),
        )
    if isinstance(expression, ast.BinaryExpression):
        return replace(
            expression,
            left=_rewrite_expression(expression.left, context),
            right=_rewrite_expression(expression.right, context),
        )
    if isinstance(expression, ast.MatchExpression):
        return replace(
            expression,
            selector=_rewrite_expression(
                expression.selector,
                context,
            ),
            cases=tuple(
                replace(
                    case,
                    label=_rewrite_match_label(
                        case.label,
                        context,
                    ),
                    expression=_rewrite_expression(
                        case.expression,
                        context,
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
                context,
            ),
        )
    if isinstance(expression, ast.Identifier) and _is_visible_module(
        expression.name,
        context,
    ):
        raise SemanticError(
            f"module '{expression.name}' cannot be used as a value",
            expression.location,
        )
    return expression


def _rewrite_match_label(
    label: ast.MatchCaseLabel,
    context: _RewriteContext,
) -> ast.MatchCaseLabel:
    if isinstance(label, ast.MatchPayloadLabel):
        rewritten = _rewrite_expression(label.variant, context)
        assert isinstance(rewritten, ast.FieldAccessExpression)
        return replace(label, variant=rewritten)
    if isinstance(label, ast.FieldAccessExpression):
        rewritten = _rewrite_expression(label, context)
        assert isinstance(rewritten, ast.FieldAccessExpression)
        return rewritten
    return label


def _rewrite_field_access_target(
    target: ast.Expression,
    context: _RewriteContext,
) -> ast.Expression:
    if isinstance(target, ast.Identifier) and target.name in context.type_namespace:
        return replace(target, name=context.type_namespace[target.name])
    return _rewrite_expression(target, context)


def _function_local_names(function: ast.FunctionDeclaration) -> frozenset[str]:
    names = {parameter.name for parameter in function.parameters}

    def visit_match_label(label: ast.MatchCaseLabel) -> None:
        if isinstance(label, ast.MatchPayloadLabel):
            names.update(label.bindings)

    def visit_expression(expression: ast.Expression) -> None:
        if isinstance(expression, ast.CallExpression):
            visit_expression(expression.callee)
            for argument in expression.arguments:
                visit_expression(argument.expression)
        elif isinstance(expression, ast.RecordExpression):
            for field in expression.fields:
                visit_expression(field.expression)
        elif isinstance(expression, ast.FieldAccessExpression):
            visit_expression(expression.target)
        elif isinstance(expression, ast.IndexExpression):
            visit_expression(expression.target)
            visit_expression(expression.index)
        elif isinstance(expression, ast.SliceExpression):
            visit_expression(expression.target)
            visit_expression(expression.start)
            visit_expression(expression.end)
        elif isinstance(expression, ast.UnaryExpression):
            visit_expression(expression.operand)
        elif isinstance(expression, ast.BinaryExpression):
            visit_expression(expression.left)
            visit_expression(expression.right)
        elif isinstance(expression, ast.MatchExpression):
            visit_expression(expression.selector)
            for case in expression.cases:
                visit_match_label(case.label)
                visit_expression(case.expression)
        elif isinstance(expression, ast.LenExpression):
            visit_expression(expression.argument)

    def visit_initializer(initializer: ast.Initializer) -> None:
        if isinstance(initializer, ast.ArrayLiteral):
            for expression in initializer.elements:
                visit_expression(expression)
            return
        visit_expression(initializer)

    def visit_block(block: ast.Block) -> None:
        for statement in block.statements:
            if isinstance(statement, ast.VariableDeclaration):
                names.add(statement.name)
                visit_initializer(statement.initializer)
            elif isinstance(statement, ast.AssignmentStatement):
                visit_initializer(statement.value)
            elif isinstance(statement, ast.CompoundAssignmentStatement):
                visit_initializer(statement.value)
            elif isinstance(statement, ast.DiscardStatement):
                visit_expression(statement.expression)
            elif isinstance(statement, ast.ReturnStatement):
                visit_expression(statement.expression)
            elif isinstance(statement, ast.SwitchStatement):
                visit_expression(statement.expression)
                for case in statement.cases:
                    visit_match_label(case.label)
                    visit_block(case.body)
            elif isinstance(statement, ast.WhileStatement):
                visit_expression(statement.condition)
                visit_block(statement.body)
            elif isinstance(statement, ast.ForStatement):
                names.add(statement.variable_name)
                visit_expression(statement.start_expression)
                visit_expression(statement.end_expression)
                visit_expression(statement.step_expression)
                visit_block(statement.body)

    visit_block(function.body)
    return frozenset(names)


def _is_visible_module(name: str, context: _RewriteContext) -> bool:
    return (
        name not in context.local_names
        and any(str(module) == name for module in context.imported_modules)
    )


def _qualified_parts(expression: ast.Expression) -> tuple[str, ...] | None:
    if isinstance(expression, ast.Identifier):
        return (expression.name,)
    if isinstance(expression, ast.FieldAccessExpression):
        target = _qualified_parts(expression.target)
        if target is None:
            return None
        return (*target, expression.field_name)
    return None


def _module_for_parts(
    parts: tuple[str, ...],
    context: _RewriteContext,
) -> tuple[ModuleId, int] | None:
    if (
        not parts
        or parts[0] in context.local_names
        or parts[0] in context.type_namespace
        or parts[0] in context.function_namespace
    ):
        return None
    matches = [
        (module, len(module.parts))
        for module in context.graph.ordered_modules
        if len(module.parts) <= len(parts) and module.parts == parts[: len(module.parts)]
    ]
    if not matches:
        if len(parts) > 1:
            raise SemanticError(
                f"module '{parts[0]}' was not found",
                diagnostic_code=DiagnosticCode.MODULE_NOT_FOUND,
            )
        return None
    module, length = max(matches, key=lambda item: item[1])
    if module not in context.imported_modules:
        raise SemanticError(
            f"module '{module}' is not imported",
            diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
        )
    return module, length


def _rewrite_qualified_module_call(
    expression: ast.CallExpression,
    context: _RewriteContext,
) -> ast.CallExpression | None:
    parts = _qualified_parts(expression.callee)
    if parts is None or len(parts) < 2:
        return None
    module_match = _module_for_parts(parts, context)
    if module_match is None:
        return None
    module, module_length = module_match
    member_parts = parts[module_length:]
    if not member_parts:
        raise SemanticError(
            f"module '{module}' cannot be called",
            expression.location,
        )
    if len(member_parts) != 1:
        raise SemanticError(
            f"symbol '{'.'.join(parts)}' is not callable",
            expression.location,
        )
    member = member_parts[0]
    function = context.module_functions[module].get(member)
    if function is None:
        type_member = _module_type(module, member, context)
        if type_member is not None:
            if not type_member.exported:
                raise SemanticError(
                    f"type '{member}' in module '{module}' is private",
                    expression.location,
                    diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                )
            raise SemanticError(
                f"type '{module}.{member}' is not callable",
                expression.location,
            )
        raise SemanticError(
            f"module '{module}' has no member '{member}'",
            expression.location,
            diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        )
    if not function.exported:
        raise SemanticError(
            f"function '{member}' in module '{module}' is private",
            expression.location,
            diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        )
    return replace(
        expression,
        callee=ast.Identifier(
            context.internal_names[(module, member)],
            expression.callee.location,
        ),
        arguments=tuple(
            replace(argument, expression=_rewrite_expression(argument.expression, context))
            for argument in expression.arguments
        ),
    )


def _rewrite_qualified_module_member(
    expression: ast.FieldAccessExpression,
    context: _RewriteContext,
) -> ast.Expression | None:
    parts = _qualified_parts(expression)
    if parts is None or len(parts) < 2:
        return None
    module_match = _module_for_parts(parts, context)
    if module_match is None:
        return None
    module, module_length = module_match
    member_parts = parts[module_length:]
    if not member_parts:
        raise SemanticError(
            f"module '{module}' cannot be used as a value",
            expression.location,
        )
    if len(member_parts) == 1:
        member = member_parts[0]
        type_member = _module_type(module, member, context)
        if type_member is not None:
            if not type_member.exported:
                raise SemanticError(
                    f"type '{member}' in module '{module}' is private",
                    expression.location,
                    diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                )
            raise SemanticError(
                f"type '{module}.{member}' cannot be used as a value",
                expression.location,
            )
        function = context.module_functions[module].get(member)
        if function is not None:
            if not function.exported:
                raise SemanticError(
                    f"function '{member}' in module '{module}' is private",
                    expression.location,
                    diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                )
            raise SemanticError(
                f"function '{module}.{member}' cannot be used as a value",
                expression.location,
            )
        raise SemanticError(
            f"module '{module}' has no member '{member}'",
            expression.location,
            diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        )
    enum_name = member_parts[0]
    enum = _module_enum(module, enum_name, context)
    if enum is None:
        type_member = _module_type(module, enum_name, context)
        if type_member is not None and not type_member.exported:
            raise SemanticError(
                f"type '{enum_name}' in module '{module}' is private",
                expression.location,
                diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
            )
        function = context.module_functions[module].get(enum_name)
        if function is not None:
            if not function.exported:
                raise SemanticError(
                    f"function '{enum_name}' in module '{module}' is private",
                    expression.location,
                    diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
                )
            raise SemanticError(
                f"function '{module}.{enum_name}' cannot be used as a value",
                expression.location,
            )
        raise SemanticError(
            f"module '{module}' has no member '{enum_name}'",
            expression.location,
            diagnostic_code=DiagnosticCode.IMPORT_UNKNOWN_SYMBOL,
        )
    if not enum.exported:
        raise SemanticError(
            f"type '{enum_name}' in module '{module}' is private",
            expression.location,
            diagnostic_code=DiagnosticCode.IMPORT_PRIVATE_SYMBOL,
        )
    variant_name = member_parts[1]
    if not any(variant.name == variant_name for variant in enum.variants):
        raise SemanticError(
            f"enum '{module}.{enum_name}' has no variant '{variant_name}'",
            expression.location,
            diagnostic_code=DiagnosticCode.ENUM_VARIANT_UNKNOWN,
        )
    rewritten: ast.Expression = ast.FieldAccessExpression(
        ast.Identifier(
            context.internal_type_names[module][enum_name],
            expression.location,
        ),
        variant_name,
        expression.location,
    )
    for member in member_parts[2:]:
        rewritten = ast.FieldAccessExpression(rewritten, member, expression.location)
    return rewritten


def _module_enum(
    module: ModuleId,
    name: str,
    context: _RewriteContext,
) -> ast.EnumDeclaration | None:
    for enum in context.program_by_module[module].enums:
        if enum.name == name:
            return enum
    return None


def _module_type(
    module: ModuleId,
    name: str,
    context: _RewriteContext,
) -> ast.RecordDeclaration | ast.EnumDeclaration | None:
    for record in context.program_by_module[module].records:
        if record.name == name:
            return record
    enum = _module_enum(module, name, context)
    if enum is not None:
        return enum
    return None
