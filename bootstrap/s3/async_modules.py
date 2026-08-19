"""Module-aware async/Future preparation for M1.82."""

from __future__ import annotations

from dataclasses import replace

from . import ast
from .async_language import (
    AsyncExecutableFunction,
    AsyncExecutableProgram,
    AsyncFunctionMarker,
    AsyncLanguageSyntax,
    AsyncModulePreparation,
    ParsedAsyncLanguageSource,
    SourceCollection,
    _contains_control_flow,
    _future_declarations,
    _internal_function_name,
    _lower_block_actions,
    _module_from_path,
    _source_items,
    parse_async_language_source,
)
from .async_validation import validate_async_language_semantics
from .diagnostics import DiagnosticCode, SemanticError, SourceLocation
from .lexer import SyntaxMode
from .module_graph import ModuleId


def prepare_async_modules(
    sources: SourceCollection,
    *,
    entry_module: str = "main",
    mode: SyntaxMode = SyntaxMode.V0_6,
) -> AsyncModulePreparation:
    items = _source_items(sources)
    parsed_items = tuple((path, parse_async_language_source(source, mode=mode)) for path, source in items)
    module_by_path: dict[str, ModuleId] = {}
    parsed_by_module: dict[ModuleId, ParsedAsyncLanguageSource] = {}
    for path, parsed in parsed_items:
        module = ModuleId.parse(parsed.program.module.name if parsed.program.module is not None else _module_from_path(path))
        if module in parsed_by_module:
            raise SemanticError(f"duplicate module '{module}'", diagnostic_code=DiagnosticCode.MODULE_DUPLICATE)
        module_by_path[path] = module
        parsed_by_module[module] = parsed

    entry = ModuleId.parse(entry_module)
    internal_names: dict[tuple[ModuleId, str], str] = {}
    async_functions: set[tuple[ModuleId, str]] = set()
    for module, parsed in parsed_by_module.items():
        for function in parsed.program.functions:
            internal_names[(module, function.name)] = _internal_function_name(module, function.name, entry)
            if function.name in parsed.syntax.async_function_names:
                async_functions.add((module, function.name))

    all_exec: list[AsyncExecutableFunction] = []
    validated_items: list[tuple[str, ParsedAsyncLanguageSource]] = []
    for path, parsed in parsed_items:
        module = module_by_path[path]
        external_async: dict[str, str] = {}
        for imported in parsed.program.imports:
            target_module = ModuleId.parse(imported.module_name)
            key = (target_module, imported.symbol_name)
            if key in async_functions:
                external_async[imported.alias or imported.symbol_name] = internal_names[key]

        # Validation only needs the names to know that an awaited imported
        # symbol is async; fake markers are never emitted as declarations.
        validation_syntax = AsyncLanguageSyntax(
            parsed.syntax.functions
            + tuple(
                AsyncFunctionMarker(name, SourceLocation(0, 1, 1), -1)
                for name in sorted(external_async)
            ),
            parsed.syntax.awaits,
            parsed.syntax.futures,
            parsed.syntax.source_sha256,
        )
        validation_parsed = ParsedAsyncLanguageSource(parsed.tokens, parsed.program, validation_syntax, parsed.core_source)
        validate_async_language_semantics(validation_parsed)
        validated_items.append((path, parsed))

        local_async = parsed.syntax.async_function_names
        accepted_async_names = frozenset(set(local_async) | set(external_async))
        await_by_offset = {item.parsed_expression_offset: item for item in parsed.syntax.awaits}
        future_names_all = {item.name for item in parsed.syntax.futures if item.name is not None}
        observed: set[int] = set()
        call_map = {
            function.name: internal_names[(module, function.name)]
            for function in parsed.program.functions
        }
        call_map.update(external_async)

        for function in parsed.program.functions:
            is_async = function.name in local_async
            function_future_names = {
                parameter.name for parameter in function.parameters if parameter.name in future_names_all
            }
            function_future_names.update(_future_declarations(function.body, future_names_all))
            if not is_async and not function_future_names:
                continue
            if is_async and _contains_control_flow(function.body):
                raise SemanticError(
                    "M1.81 V1 requires linear async bodies; suspension inside control flow needs explicit async CFG lowering",
                    function.location,
                    diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
                )
            actions = _lower_block_actions(
                function,
                async_names=accepted_async_names,
                await_by_offset=await_by_offset,
                future_names=function_future_names,
                observed_awaits=observed,
                call_map=call_map,
            )
            frame_slots = tuple(parameter.name for parameter in function.parameters) + tuple(
                statement.name
                for statement in function.body.statements
                if isinstance(statement, ast.VariableDeclaration)
            )
            all_exec.append(
                AsyncExecutableFunction(
                    internal_names[(module, function.name)],
                    function.name,
                    tuple(parameter.name for parameter in function.parameters),
                    tuple(parameter.name for parameter in function.parameters if parameter.name in function_future_names),
                    frame_slots,
                    actions,
                    is_async,
                    tuple((item.name, item.constraint) for item in function.signature.type_parameters),
                )
            )
        missing = set(await_by_offset) - observed
        if missing:
            marker = await_by_offset[min(missing)]
            raise SemanticError(
                "await marker is not a complete supported initializer/return/discard expression",
                marker.keyword_location,
                diagnostic_code=DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
            )

    return AsyncModulePreparation(
        tuple((path, parsed.core_source) for path, parsed in parsed_items),
        tuple(validated_items),
        AsyncExecutableProgram(tuple(all_exec), entry="main"),
    )
