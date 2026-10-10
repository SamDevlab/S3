"""Independent generic recursive-descent parser over TokenArena.

The parser consumes the direct-ID generic token arena and writes the existing
flat SyntaxArena directly.  It does not import or construct bootstrap.s3.ast
objects and it does not call bootstrap.s3.parser.

V1 targets the current default V0.6 grammar.  V0.5 remains owned by the Python
reference parser until separately migrated.
"""

from __future__ import annotations

from dataclasses import dataclass

from .async_limits import MAX_SELECT_ARITY
from .compiler_substrate import SymbolInterner
from .diagnostics import DiagnosticCode, ParseError, SourceLocation
from .frontend_token_arena import TokenArena, TokenRecord
from .generic_syntax import (
    DeclarationPayload,
    FloatPayload,
    FunctionPayload,
    IntegerPayload,
    NodeKind,
    OperatorPayload,
    SymbolPayload,
    SyntaxArena,
    SyntaxSpan,
    TextPayload,
    TypePayload,
)
from .lexer import SyntaxMode, TokenKind


class GenericParserError(RuntimeError):
    """Internal parser-contract failure, distinct from source ParseError."""


@dataclass(frozen=True, slots=True)
class IndependentParseResult:
    syntax_arena: SyntaxArena
    symbol_names: tuple[str, ...]
    parser_backend: str = "independent_generic_recursive_descent"

    @property
    def root_id(self) -> int:
        if self.syntax_arena.root_id is None:
            raise GenericParserError("syntax arena has no root")
        return self.syntax_arena.root_id


_BINARY_OPERATOR_IDS = {
    TokenKind.PLUS: 0,
    TokenKind.MINUS: 1,
    TokenKind.STAR: 2,
    TokenKind.SLASH: 3,
    TokenKind.AMPERSAND: 4,
    TokenKind.PIPE: 5,
    TokenKind.COMPARE: 6,
    TokenKind.EQUAL_EQUAL: 7,
    TokenKind.NOT_EQUAL: 8,
    TokenKind.LESS: 9,
    TokenKind.LESS_EQUAL: 10,
    TokenKind.GREATER: 11,
    TokenKind.GREATER_EQUAL: 12,
}

_UNARY_OPERATOR_IDS = {
    TokenKind.TILDE: 0,
    TokenKind.MINUS: 1,
}

_PRIMITIVE_IDENTIFIER_TYPES = {
    "string",
    "bytes",
    "text",
    "tryte_vector",
    "i64_vector",
    "f64_vector",
    "i64_map",
    "i64_set",
    "host_capability",
    "resource_handle",
}


class GenericParser:
    """V0.6 parser that emits SyntaxArena nodes directly."""

    def __init__(
        self,
        token_arena: TokenArena,
        *,
        interner: SymbolInterner | None = None,
    ) -> None:
        if token_arena.mode is not SyntaxMode.V0_6:
            raise ValueError("independent generic parser currently supports V0.6 only")
        self.token_arena = token_arena
        self.tokens = tuple(record for _, record in token_arena.tokens.items())
        if not self.tokens or self.tokens[-1].kind is not TokenKind.EOF:
            raise GenericParserError("TokenArena must terminate with EOF")
        self.current = 0
        self.interner = interner if interner is not None else SymbolInterner()
        self.arena = SyntaxArena(symbol_count=0, type_count=0)
        self._active_type_parameters: set[str] = set()

    def parse_program(self) -> IndependentParseResult:
        start = self._peek()
        children: list[int] = []
        function_count = 0

        self._skip_newlines()
        if self._match(TokenKind.MODULE):
            children.append(self._parse_module_declaration(self._previous()))
            self._skip_newlines()

        while self._check(TokenKind.FROM):
            children.extend(self._parse_import_declarations())
            self._skip_newlines()

        while not self._check(TokenKind.EOF):
            self._skip_newlines()
            if self._check(TokenKind.EOF):
                break
            exported = self._match(TokenKind.EXPORT)
            if self._match(TokenKind.FOREIGN):
                children.append(self._parse_foreign_function())
            elif self._check(TokenKind.RECORD):
                children.append(self._parse_record_declaration(exported=exported))
            elif self._check(TokenKind.ENUM):
                children.append(self._parse_enum_declaration(exported=exported))
            else:
                children.append(self._parse_function(exported=exported))
                function_count += 1

        if function_count == 0:
            self._raise("expected at least one function")

        root = self._append(NodeKind.PROGRAM, start, children=tuple(children))
        self.arena.symbol_count = self.interner.length
        self.arena.set_root(root)
        self.arena.validate()
        names = tuple(
            self.interner.name(symbol_id)
            for symbol_id in range(self.interner.length)
        )
        return IndependentParseResult(self.arena, names)

    # ------------------------------------------------------------------
    # Declarations and types
    # ------------------------------------------------------------------

    def _parse_module_declaration(self, start: TokenRecord) -> int:
        name = self._parse_module_name()
        self._consume_statement_newline("expected newline after module declaration")
        return self._append(
            NodeKind.MODULE_DECLARATION,
            start,
            payload=DeclarationPayload(self._symbol(name), -1, 0),
        )

    def _parse_import_declarations(self) -> list[int]:
        start = self._consume(TokenKind.FROM, "expected 'from'")
        module_name = self._parse_module_name()
        self._consume(TokenKind.IMPORT, "expected 'import' after module name")
        imports: list[int] = []
        while True:
            symbol = self._consume(TokenKind.IDENTIFIER, "expected imported symbol")
            alias: TokenRecord | None = None
            if self._match(TokenKind.AS):
                alias = self._consume(TokenKind.IDENTIFIER, "expected import alias")
            module_node = self._identifier(module_name, start)
            symbol_node = self._identifier(symbol.text, symbol)
            child_nodes = [module_node, symbol_node]
            flags = 0
            if alias is not None:
                flags = 1
                child_nodes.append(self._identifier(alias.text, alias))
            imports.append(
                self._append(
                    NodeKind.IMPORT_DECLARATION,
                    start,
                    payload=DeclarationPayload(self._symbol(module_name), -1, flags),
                    children=tuple(child_nodes),
                )
            )
            if not self._match(TokenKind.COMMA):
                break
        self._consume_statement_newline("expected newline after import declaration")
        return imports

    def _parse_module_name(self) -> str:
        parts = [self._consume(TokenKind.IDENTIFIER, "expected module name").text]
        while self._match(TokenKind.DOT):
            parts.append(
                self._consume(
                    TokenKind.IDENTIFIER,
                    "expected module name after '.'",
                ).text
            )
        return ".".join(parts)

    def _parse_foreign_function(self) -> int:
        start = self._consume(TokenKind.FN, "expected 'fn' after 'foreign'")
        name = self._consume_identifier("expected foreign function name")
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after foreign function name")
        parameters = self._parse_parameters()
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after parameters")
        self._consume(TokenKind.ARROW, "expected '->' before foreign return type")
        return_type = self._parse_type()
        self._consume_statement_newline("expected newline after foreign declaration")
        children = parameters + (return_type,)
        return self._append(
            NodeKind.FOREIGN_FUNCTION,
            start,
            payload=FunctionPayload(
                self._symbol(name.text),
                -1,
                parameters[0] if parameters else 0,
                len(parameters),
                -1,
            ),
            children=children,
        )

    def _parse_function(self, *, exported: bool) -> int:
        start = self._consume(TokenKind.FN, "expected 'fn'")
        name = self._consume_identifier("expected function name")
        type_parameters, type_parameter_names = self._parse_type_parameters()

        previous = self._active_type_parameters
        self._active_type_parameters = set(type_parameter_names)
        try:
            self._consume(TokenKind.LEFT_PAREN, "expected '(' after function name")
            parameters = self._parse_parameters()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after parameters")
            self._consume(TokenKind.ARROW, "expected '->' before return type")
            return_type = self._parse_type()
            if self._check(TokenKind.LEFT_BRACE):
                self._raise(
                    "obsolete brace syntax",
                    code=DiagnosticCode.PARSE_OBSOLETE_BRACE,
                )
            self._consume(TokenKind.COLON, "expected ':' after return type")
            self._consume(TokenKind.NEWLINE, "expected newline after ':'")
            self._consume(TokenKind.INDENT, "expected indented block")
            body = self._parse_block_v0_6()
        finally:
            self._active_type_parameters = previous

        children = type_parameters + parameters + (return_type, body)
        return self._append(
            NodeKind.FUNCTION,
            start,
            payload=FunctionPayload(
                self._symbol(name.text),
                -1,
                parameters[0] if parameters else 0,
                len(parameters),
                body,
                1 if exported else 0,
            ),
            children=children,
        )

    def _parse_type_parameters(self) -> tuple[tuple[int, ...], tuple[str, ...]]:
        if not self._match(TokenKind.LESS):
            return (), ()
        nodes: list[int] = []
        names: list[str] = []
        while True:
            token = self._consume(TokenKind.IDENTIFIER, "expected type parameter name")
            constraint = "value"
            constraint_token = token
            if self._match(TokenKind.COLON):
                constraint_token = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected type parameter constraint",
                )
                constraint = constraint_token.text
            constraint_node = self._identifier(constraint, constraint_token)
            nodes.append(
                self._append(
                    NodeKind.TYPE_PARAMETER,
                    token,
                    payload=DeclarationPayload(self._symbol(token.text), -1, 0),
                    children=(constraint_node,),
                )
            )
            names.append(token.text)
            if not self._match(TokenKind.COMMA):
                break
            if self._check(TokenKind.GREATER):
                self._raise("expected type parameter after ','")
        self._consume(TokenKind.GREATER, "expected '>' after type parameters")
        if len(set(names)) != len(names):
            self._raise("duplicate type parameter")
        return tuple(nodes), tuple(names)

    def _parse_record_declaration(self, *, exported: bool) -> int:
        start = self._consume(TokenKind.RECORD, "expected 'record'")
        name = self._consume(TokenKind.IDENTIFIER, "expected record name")
        type_parameters, type_parameter_names = self._parse_type_parameters()

        previous = self._active_type_parameters
        self._active_type_parameters = set(type_parameter_names)
        try:
            self._consume(TokenKind.COLON, "expected ':' after record name")
            self._consume(TokenKind.NEWLINE, "expected newline after record ':'")
            self._consume(TokenKind.INDENT, "expected indented record fields")
            fields: list[int] = []
            while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
                field_name = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected record field name",
                )
                self._consume(TokenKind.COLON, "expected ':' after record field name")
                field_type = self._parse_type()
                self._consume_statement_newline("expected newline after record field")
                fields.append(
                    self._append(
                        NodeKind.RECORD_FIELD,
                        field_name,
                        payload=DeclarationPayload(self._symbol(field_name.text), -1, 0),
                        children=(field_type,),
                    )
                )
            if not fields:
                self._raise("expected at least one record field", name)
            self._consume(TokenKind.DEDENT, "expected dedent after record declaration")
        finally:
            self._active_type_parameters = previous

        return self._append(
            NodeKind.RECORD_DECLARATION,
            start,
            payload=DeclarationPayload(
                self._symbol(name.text),
                -1,
                1 if exported else 0,
            ),
            children=type_parameters + tuple(fields),
        )

    def _parse_enum_declaration(self, *, exported: bool) -> int:
        start = self._consume(TokenKind.ENUM, "expected 'enum'")
        name = self._consume(TokenKind.IDENTIFIER, "expected enum name")
        type_parameters, type_parameter_names = self._parse_type_parameters()

        previous = self._active_type_parameters
        self._active_type_parameters = set(type_parameter_names)
        try:
            self._consume(TokenKind.COLON, "expected ':' after enum name")
            self._consume(TokenKind.NEWLINE, "expected newline after enum ':'")
            self._consume(TokenKind.INDENT, "expected indented enum variants")
            variants: list[int] = []
            while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
                variant = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected enum variant name",
                )
                fields: list[int] = []
                if self._match(TokenKind.LEFT_PAREN):
                    if self._check(TokenKind.RIGHT_PAREN):
                        self._raise("expected enum payload field")
                    while True:
                        field_name = self._consume(
                            TokenKind.IDENTIFIER,
                            "expected enum payload field name",
                        )
                        self._consume(
                            TokenKind.COLON,
                            "expected ':' after enum payload field name",
                        )
                        field_type = self._parse_type()
                        fields.append(
                            self._append(
                                NodeKind.RECORD_FIELD,
                                field_name,
                                payload=DeclarationPayload(
                                    self._symbol(field_name.text), -1, 0
                                ),
                                children=(field_type,),
                            )
                        )
                        if not self._match(TokenKind.COMMA):
                            break
                        if self._check(TokenKind.RIGHT_PAREN):
                            self._raise("expected enum payload field after ','")
                    self._consume(
                        TokenKind.RIGHT_PAREN,
                        "expected ')' after enum payload fields",
                    )
                self._consume_statement_newline("expected newline after enum variant")
                variants.append(
                    self._append(
                        NodeKind.ENUM_VARIANT,
                        variant,
                        payload=DeclarationPayload(self._symbol(variant.text), -1, 0),
                        children=tuple(fields),
                    )
                )
            if not variants:
                self._raise("expected at least one enum variant", name)
            self._consume(TokenKind.DEDENT, "expected dedent after enum declaration")
        finally:
            self._active_type_parameters = previous

        return self._append(
            NodeKind.ENUM_DECLARATION,
            start,
            payload=DeclarationPayload(
                self._symbol(name.text),
                -1,
                1 if exported else 0,
            ),
            children=type_parameters + tuple(variants),
        )

    def _parse_parameters(self) -> tuple[int, ...]:
        parameters: list[int] = []
        if self._check(TokenKind.RIGHT_PAREN):
            return ()
        while True:
            name = self._consume(TokenKind.IDENTIFIER, "expected parameter name")
            self._consume(TokenKind.COLON, "expected ':' after parameter name")
            type_node = self._parse_type()
            parameters.append(
                self._append(
                    NodeKind.PARAMETER,
                    name,
                    payload=DeclarationPayload(self._symbol(name.text), -1, 0),
                    children=(type_node,),
                )
            )
            if not self._match(TokenKind.COMMA):
                return tuple(parameters)
            if self._check(TokenKind.RIGHT_PAREN):
                self._raise("expected parameter after ','")

    def _parse_type(self) -> int:
        start = self._peek()
        if self._match(TokenKind.AMPERSAND):
            mutable = self._match(TokenKind.MUT)
            if self._match(TokenKind.LEFT_BRACKET):
                element = self._parse_type()
                if self.arena.node(element).kind is not NodeKind.TYPE_NAME:
                    self._raise(
                        "slice element type must be a scalar type",
                        start,
                    )
                self._consume(
                    TokenKind.RIGHT_BRACKET,
                    "expected ']' after slice element type",
                )
                return self._append(
                    NodeKind.SLICE_TYPE,
                    start,
                    payload=IntegerPayload(1 if mutable else 0),
                    children=(element,),
                )
            target = self._parse_type()
            return self._append(
                NodeKind.REFERENCE_TYPE,
                start,
                payload=IntegerPayload(1 if mutable else 0),
                children=(target,),
            )

        if self._match(TokenKind.TRIT, TokenKind.TRYTE, TokenKind.I64, TokenKind.F64):
            token = self._previous()
            result = self._type_name_node(token.text, token)
        elif self._check(TokenKind.IDENTIFIER) and self._peek().text in _PRIMITIVE_IDENTIFIER_TYPES:
            token = self._advance()
            result = self._type_name_node(token.text, token)
        elif self._check(TokenKind.IDENTIFIER):
            nominal = self._advance()
            if nominal.text in self._active_type_parameters:
                result = self._append(
                    NodeKind.TYPE_PARAMETER_TYPE,
                    nominal,
                    payload=SymbolPayload(self._symbol(nominal.text)),
                )
                if self._check(TokenKind.LEFT_BRACKET):
                    self._raise(
                        "type parameter arrays require a concrete specialization",
                        nominal,
                    )
                return result
            parts = [nominal.text]
            while self._match(TokenKind.DOT):
                parts.append(
                    self._consume(
                        TokenKind.IDENTIFIER,
                        "expected nominal type name after '.'",
                    ).text
                )
            arguments = self._parse_type_arguments()
            result = self._append(
                NodeKind.NOMINAL_TYPE,
                nominal,
                payload=SymbolPayload(self._symbol(".".join(parts))),
                children=arguments,
            )
        else:
            self._raise(
                "expected type 'trit', 'tryte', 'i64', 'f64', 'string', or nominal type"
            )
            raise AssertionError("unreachable")

        while self._match(TokenKind.LEFT_BRACKET):
            negative = self._match(TokenKind.MINUS)
            length = self._consume(TokenKind.INTEGER, "expected static array length")
            value = int(length.text)
            if negative:
                value = -value
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after array length")
            result = self._append(
                NodeKind.ARRAY_TYPE,
                start,
                payload=IntegerPayload(value),
                children=(result,),
            )
        return result

    def _parse_type_arguments(self) -> tuple[int, ...]:
        if not self._match(TokenKind.LESS):
            return ()
        arguments: list[int] = []
        while True:
            arguments.append(self._parse_type())
            if not self._match(TokenKind.COMMA):
                break
            if self._check(TokenKind.GREATER):
                self._raise("expected type argument after ','")
        self._consume(TokenKind.GREATER, "expected '>' after type arguments")
        return tuple(arguments)

    # ------------------------------------------------------------------
    # Statements
    # ------------------------------------------------------------------

    def _parse_block_v0_6(self) -> int:
        start = self._previous()
        statements: list[int] = []
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            statements.append(self._parse_statement())
        if not statements:
            self._raise("expected at least one statement in block")
        self._consume(TokenKind.DEDENT, "expected dedent after block")
        return self._append(NodeKind.BLOCK, start, children=tuple(statements))

    def _parse_statement(self) -> int:
        if self._check(TokenKind.LEFT_BRACE) or self._check(TokenKind.RIGHT_BRACE):
            self._raise(
                "obsolete brace syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_BRACE,
            )
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        if self._check(TokenKind.SWITCH):
            self._raise(
                "obsolete 'switch' syntax, use 'match'",
                code=DiagnosticCode.PARSE_OBSOLETE_SWITCH,
            )

        if self._match(TokenKind.BREAK):
            return self._parse_break(self._previous())
        if self._match(TokenKind.CONTINUE):
            return self._parse_continue(self._previous())
        if self._match(TokenKind.RETURN):
            return self._parse_return(self._previous())
        if self._match(TokenKind.MATCH):
            return self._parse_match_statement(self._previous())
        if self._check(TokenKind.SELECT) and self._next_kind() is TokenKind.COLON:
            self._advance()
            return self._parse_select(self._previous())
        if self._match(TokenKind.WHILE):
            return self._parse_while(self._previous())
        if self._match(TokenKind.FOR):
            return self._parse_for(self._previous())
        if self._match(TokenKind.DISCARD):
            return self._parse_discard(self._previous())
        if self._check(TokenKind.MUT):
            return self._parse_variable_declaration()
        if self._check(TokenKind.IDENTIFIER) or self._check(TokenKind.SELECT) or self._check(TokenKind.CASE):
            next_token = self.tokens[self.current + 1] if self.current + 1 < len(self.tokens) else None
            if next_token is not None and next_token.kind is TokenKind.COLON:
                return self._parse_variable_declaration()
            return self._parse_assignment()
        if self._check(TokenKind.STAR):
            return self._parse_assignment()

        self._raise(
            "expected variable declaration, 'return', 'while', 'for', 'break', 'continue', or assignment"
        )
        raise AssertionError("unreachable")

    def _parse_variable_declaration(self) -> int:
        start = self._peek()
        mutable = self._match(TokenKind.MUT)
        name = self._consume(TokenKind.IDENTIFIER, "expected variable name")
        self._consume(TokenKind.COLON, "expected ':' after variable name")
        type_node = self._parse_type()
        self._consume(TokenKind.EQUAL, "expected '=' after variable type")
        initializer = self._parse_initializer()
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume_statement_newline("expected newline after declaration")
        return self._append(
            NodeKind.VARIABLE_DECLARATION,
            start,
            payload=DeclarationPayload(
                self._symbol(name.text), -1, 1 if mutable else 0
            ),
            children=(type_node, initializer),
        )

    def _parse_assignment(self) -> int:
        if self._match(TokenKind.STAR):
            start = self._previous()
            reference = self._parse_unary()
            target = self._append(
                NodeKind.DEREFERENCE_TARGET,
                start,
                children=(reference,),
            )
            self._consume(TokenKind.EQUAL, "expected '=' after dereference target")
            value = self._parse_initializer()
            self._consume_statement_newline("expected newline after assignment")
            return self._append(
                NodeKind.ASSIGNMENT,
                start,
                payload=DeclarationPayload(self._symbol("*"), -1, 0),
                children=(target, value),
            )

        name = self._consume(TokenKind.IDENTIFIER, "expected assignment target")
        target, assignment_symbol = self._parse_assignment_target_tail(name)

        if self._match(TokenKind.PLUS_EQUAL):
            operator_id = _BINARY_OPERATOR_IDS[TokenKind.PLUS]
        else:
            self._consume(
                TokenKind.EQUAL,
                "expected '=' or '+=' after assignment target",
            )
            operator_id = None

        value = self._parse_initializer()
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume_statement_newline("expected newline after assignment")

        if operator_id is not None:
            operator = self._append(
                NodeKind.BINARY,
                name,
                payload=OperatorPayload(operator_id),
            )
            return self._append(
                NodeKind.COMPOUND_ASSIGNMENT,
                name,
                payload=DeclarationPayload(assignment_symbol, -1, 0),
                children=(target, operator, value),
            )
        return self._append(
            NodeKind.ASSIGNMENT,
            name,
            payload=DeclarationPayload(assignment_symbol, -1, 0),
            children=(target, value),
        )

    def _parse_assignment_target_tail(
        self,
        name: TokenRecord,
    ) -> tuple[int, int]:
        if self._match(TokenKind.LEFT_BRACKET):
            index = self._parse_expression()
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
            identifier = self._identifier(name.text, name)
            base = self._append(
                NodeKind.INDEX,
                name,
                children=(identifier, index),
            )
            if self._match(TokenKind.DOT):
                return self._parse_field_target_tail(base)
            return (
                self._append(
                    NodeKind.INDEX_TARGET,
                    name,
                    payload=DeclarationPayload(self._symbol(name.text), -1, 0),
                    children=(index,),
                ),
                self._symbol(name.text),
            )

        if self._match(TokenKind.DOT):
            identifier = self._identifier(name.text, name)
            return self._parse_field_target_tail(identifier)

        symbol = self._symbol(name.text)
        return (
            self._append(
                NodeKind.ASSIGNMENT_TARGET,
                name,
                payload=DeclarationPayload(symbol, -1, 0),
            ),
            symbol,
        )

    def _parse_field_target_tail(self, base: int) -> tuple[int, int]:
        field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
        while self._match(TokenKind.DOT):
            base = self._append(
                NodeKind.FIELD_ACCESS,
                field,
                payload=SymbolPayload(self._symbol(field.text)),
                children=(base,),
            )
            field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
        symbol = self._symbol(field.text)
        return (
            self._append(
                NodeKind.FIELD_TARGET,
                field,
                payload=DeclarationPayload(symbol, -1, 0),
                children=(base,),
            ),
            symbol,
        )

    def _parse_initializer(self) -> int:
        if self._match(TokenKind.LEFT_BRACKET):
            return self._finish_array_literal(self._previous())
        return self._parse_expression()

    def _finish_array_literal(self, start: TokenRecord) -> int:
        elements: list[int] = []
        if not self._check(TokenKind.RIGHT_BRACKET):
            while True:
                elements.append(self._parse_expression())
                if not self._match(TokenKind.COMMA):
                    break
                if self._check(TokenKind.RIGHT_BRACKET):
                    self._raise("expected array element after ','")
        end = self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after array literal")
        return self._append(
            NodeKind.ARRAY_LITERAL,
            start,
            children=tuple(elements),
            end=end,
        )

    def _parse_return(self, start: TokenRecord) -> int:
        expression = self._parse_expression()
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume_statement_newline("expected newline after return value")
        return self._append(NodeKind.RETURN, start, children=(expression,))

    def _parse_discard(self, start: TokenRecord) -> int:
        expression = self._parse_expression()
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume_statement_newline("expected newline after discard expression")
        return self._append(NodeKind.DISCARD, start, children=(expression,))

    def _parse_break(self, start: TokenRecord) -> int:
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume(TokenKind.NEWLINE, "expected newline after break")
        return self._append(NodeKind.BREAK, start)

    def _parse_continue(self, start: TokenRecord) -> int:
        if self._check(TokenKind.SEMICOLON):
            self._raise(
                "obsolete ';' syntax",
                code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON,
            )
        self._consume(TokenKind.NEWLINE, "expected newline after continue")
        return self._append(NodeKind.CONTINUE, start)

    def _parse_while(self, start: TokenRecord) -> int:
        condition = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after while condition")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")
        body = self._parse_block_v0_6()
        return self._append(
            NodeKind.WHILE,
            start,
            children=(condition, body),
        )

    def _parse_for(self, start: TokenRecord) -> int:
        variable = self._consume(TokenKind.IDENTIFIER, "expected loop variable name")
        self._consume(TokenKind.COLON, "expected ':' after loop variable name")
        variable_type = self._parse_type()
        self._consume(TokenKind.IN, "expected 'in' after loop variable type")
        range_token = self._consume(TokenKind.RANGE, "expected 'range' after 'in'")
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'range'")
        arg1 = self._parse_expression()
        if self._match(TokenKind.COMMA):
            arg2 = self._parse_expression()
            if self._match(TokenKind.COMMA):
                arg3 = self._parse_expression()
                start_expression, end_expression, step_expression = arg1, arg2, arg3
            else:
                start_expression, end_expression = arg1, arg2
                step_expression = self._integer_literal(1, range_token)
        else:
            start_expression = self._integer_literal(0, range_token)
            end_expression = arg1
            step_expression = self._integer_literal(1, range_token)
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after range bounds")
        self._consume(TokenKind.COLON, "expected ':' after range clause")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")
        body = self._parse_block_v0_6()
        return self._append(
            NodeKind.FOR,
            start,
            payload=DeclarationPayload(self._symbol(variable.text), -1, 0),
            children=(
                variable_type,
                start_expression,
                end_expression,
                step_expression,
                body,
            ),
        )

    def _parse_match_statement(self, start: TokenRecord) -> int:
        selector = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after match expression")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")

        cases: list[int] = []
        had_fallback = False
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            if had_fallback:
                self._raise(
                    "explicit case arm after fallback arm in match statement",
                    code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                )
            case, fallback = self._parse_statement_match_case()
            had_fallback = had_fallback or fallback
            cases.append(case)

        if not cases:
            self._raise(
                "expected at least one match arm",
                code=DiagnosticCode.PARSE_EXPECTED_MATCH_ARM,
            )
        self._consume(TokenKind.DEDENT, "expected dedent after match block")
        return self._append(
            NodeKind.SWITCH,
            start,
            children=(selector,) + tuple(cases),
        )

    def _parse_statement_match_case(self) -> tuple[int, bool]:
        if self._match(TokenKind.ELSE):
            start = self._previous()
            self._consume(TokenKind.COLON, "expected ':' after 'else'")
            self._consume(TokenKind.NEWLINE, "expected newline after ':'")
            self._consume(TokenKind.INDENT, "expected indented block")
            body = self._parse_block_v0_6()
            return (
                self._append(NodeKind.MATCH_CASE, start, children=(body,)),
                True,
            )

        label, start = self._parse_match_case_label()
        self._consume(TokenKind.COLON, "expected ':' after case label")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")
        body = self._parse_block_v0_6()
        return (
            self._append(
                NodeKind.MATCH_CASE,
                start,
                children=(label, body),
            ),
            False,
        )

    def _parse_select(self, start: TokenRecord) -> int:
        self._consume(TokenKind.COLON, "expected ':' after select")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented select block")
        arms: list[int] = []
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            if len(arms) >= MAX_SELECT_ARITY:
                self._raise(
                    f"select supports at most {MAX_SELECT_ARITY} arms",
                    code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                )
            arm_start = self._consume(TokenKind.CASE, "expected 'case' in select")
            operation = self._parse_expression()
            self._consume(TokenKind.COLON, "expected ':' after select operation")
            self._consume(TokenKind.NEWLINE, "expected newline after ':'")
            self._consume(TokenKind.INDENT, "expected indented select arm")
            body = self._parse_block_v0_6()
            arms.append(
                self._append(
                    NodeKind.SELECT_ARM,
                    arm_start,
                    children=(operation, body),
                )
            )
        if not arms:
            self._raise("expected at least one select arm")
        self._consume(TokenKind.DEDENT, "expected dedent after select block")
        return self._append(NodeKind.SELECT, start, children=tuple(arms))

    # ------------------------------------------------------------------
    # Expressions
    # ------------------------------------------------------------------

    def _parse_expression(self) -> int:
        return self._parse_relational()

    def _parse_relational(self) -> int:
        return self._parse_left_associative(
            self._parse_compare,
            (
                TokenKind.EQUAL_EQUAL,
                TokenKind.NOT_EQUAL,
                TokenKind.LESS,
                TokenKind.LESS_EQUAL,
                TokenKind.GREATER,
                TokenKind.GREATER_EQUAL,
            ),
        )

    def _parse_compare(self) -> int:
        return self._parse_left_associative(
            self._parse_maximum,
            (TokenKind.COMPARE,),
        )

    def _parse_maximum(self) -> int:
        return self._parse_left_associative(
            self._parse_minimum,
            (TokenKind.PIPE,),
        )

    def _parse_minimum(self) -> int:
        return self._parse_left_associative(
            self._parse_additive,
            (TokenKind.AMPERSAND,),
        )

    def _parse_additive(self) -> int:
        return self._parse_left_associative(
            self._parse_multiplicative,
            (TokenKind.PLUS, TokenKind.MINUS),
        )

    def _parse_multiplicative(self) -> int:
        return self._parse_left_associative(
            self._parse_unary,
            (TokenKind.STAR, TokenKind.SLASH),
        )

    def _parse_left_associative(
        self,
        operand_parser,
        operators: tuple[TokenKind, ...],
    ) -> int:
        expression = operand_parser()
        while self._peek().kind in operators:
            operator = self._advance()
            right = operand_parser()
            expression = self._append(
                NodeKind.BINARY,
                operator,
                payload=OperatorPayload(_BINARY_OPERATOR_IDS[operator.kind]),
                children=(expression, right),
            )
        return expression

    def _parse_unary(self) -> int:
        if self._match(TokenKind.AMPERSAND):
            token = self._previous()
            mutable = self._match(TokenKind.MUT)
            operand = self._parse_unary()
            return self._append(
                NodeKind.ADDRESS_OF,
                token,
                payload=IntegerPayload(1 if mutable else 0),
                children=(operand,),
            )
        if self._match(TokenKind.STAR):
            token = self._previous()
            operand = self._parse_unary()
            return self._append(
                NodeKind.DEREFERENCE,
                token,
                children=(operand,),
            )
        if self._match(TokenKind.TILDE, TokenKind.MINUS):
            token = self._previous()
            operand = self._parse_unary()
            return self._append(
                NodeKind.UNARY,
                token,
                payload=OperatorPayload(_UNARY_OPERATOR_IDS[token.kind]),
                children=(operand,),
            )
        return self._parse_postfix()

    def _parse_postfix(self) -> int:
        expression = self._parse_primary_atom()
        while True:
            if self._match(TokenKind.LEFT_PAREN):
                if (
                    self._qualified_name(expression) is not None
                    and self._is_record_field_argument_start()
                ):
                    expression = self._finish_record_expression(expression)
                else:
                    expression = self._finish_call(expression)
                continue

            if self.arena.node(expression).kind is NodeKind.IDENTIFIER and self._is_generic_call_start():
                arguments = self._parse_type_arguments()
                self._consume(TokenKind.LEFT_PAREN, "expected '(' after type arguments")
                if self._is_record_field_argument_start():
                    expression = self._finish_record_expression(
                        expression,
                        type_arguments=arguments,
                    )
                else:
                    expression = self._finish_call(
                        expression,
                        type_arguments=arguments,
                    )
                continue

            if self.arena.node(expression).kind is NodeKind.IDENTIFIER and self._is_generic_type_qualifier_start():
                type_arguments = self._parse_type_arguments()
                expression = self._append_from_node(
                    NodeKind.GENERIC_TYPE,
                    expression,
                    payload=TypePayload(-1),
                    children=(expression,) + type_arguments,
                )
                continue

            if self._match(TokenKind.LEFT_BRACKET):
                start = self._previous()
                index_or_start = self._parse_expression()
                if self._match(TokenKind.COLON):
                    end_expression = self._parse_expression()
                    close = self._consume(
                        TokenKind.RIGHT_BRACKET,
                        "expected ']' after slice",
                    )
                    expression = self._append_from_node(
                        NodeKind.SLICE,
                        expression,
                        children=(expression, index_or_start, end_expression),
                        end=close,
                    )
                    continue
                close = self._consume(
                    TokenKind.RIGHT_BRACKET,
                    "expected ']' after index",
                )
                expression = self._append_from_node(
                    NodeKind.INDEX,
                    expression,
                    children=(expression, index_or_start),
                    end=close,
                )
                continue

            if self._match(TokenKind.DOT):
                field = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected member name after '.'",
                )
                expression = self._append_from_node(
                    NodeKind.FIELD_ACCESS,
                    expression,
                    payload=SymbolPayload(self._symbol(field.text)),
                    children=(expression,),
                    end=field,
                )
                continue
            break
        return expression

    def _parse_primary_atom(self) -> int:
        if self._match(TokenKind.MATCH):
            return self._parse_match_expression(self._previous())
        if self._match(TokenKind.LEN):
            return self._parse_len(self._previous())
        if self._match(TokenKind.INTEGER):
            token = self._previous()
            return self._integer_literal(int(token.text), token)
        if self._match(TokenKind.FLOAT):
            token = self._previous()
            return self._append(
                NodeKind.FLOAT_LITERAL,
                token,
                payload=FloatPayload(float(token.text)),
            )
        if self._match(TokenKind.STRING_LITERAL):
            token = self._previous()
            return self._append(
                NodeKind.STRING_LITERAL,
                token,
                payload=TextPayload(token.text[1:-1]),
            )
        if self._check(TokenKind.IDENTIFIER) or self._check(TokenKind.SELECT) or self._check(TokenKind.CASE):
            token = self._advance()
            return self._identifier(token.text, token)
        if self._match(TokenKind.LEFT_PAREN):
            expression = self._parse_expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after expression")
            return expression
        self._raise("expected expression")
        raise AssertionError("unreachable")

    def _finish_call(
        self,
        callee: int,
        *,
        type_arguments: tuple[int, ...] = (),
    ) -> int:
        arguments: list[int] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                expression = self._parse_expression()
                arguments.append(
                    self._append_from_node(
                        NodeKind.CALL_ARGUMENT,
                        expression,
                        children=(expression,),
                    )
                )
                if not self._match(TokenKind.COMMA):
                    break
                if self._check(TokenKind.RIGHT_PAREN):
                    self._raise("expected argument after ','")
        close = self._consume(TokenKind.RIGHT_PAREN, "expected ')' after arguments")
        return self._append_from_node(
            NodeKind.CALL,
            callee,
            children=(callee,) + type_arguments + tuple(arguments),
            end=close,
        )

    def _finish_record_expression(
        self,
        type_name_node: int,
        *,
        type_arguments: tuple[int, ...] = (),
    ) -> int:
        record_name = self._qualified_name(type_name_node)
        if record_name is None:
            self._raise("record constructor must be a nominal type name")
        if not type_arguments:
            type_arguments = self._embedded_type_arguments(type_name_node)
        fields: list[int] = []
        while True:
            field = self._consume(TokenKind.IDENTIFIER, "expected record field name")
            self._consume(TokenKind.EQUAL, "expected '=' after record field name")
            expression = self._parse_expression()
            fields.append(
                self._append(
                    NodeKind.RECORD_FIELD_VALUE,
                    field,
                    payload=DeclarationPayload(self._symbol(field.text), -1, 0),
                    children=(expression,),
                )
            )
            if not self._match(TokenKind.COMMA):
                break
            if self._check(TokenKind.RIGHT_PAREN):
                self._raise("expected record field after ','")
        close = self._consume(TokenKind.RIGHT_PAREN, "expected ')' after record fields")
        return self._append_from_node(
            NodeKind.RECORD_CONSTRUCTION,
            type_name_node,
            payload=SymbolPayload(self._symbol(record_name)),
            children=type_arguments + tuple(fields),
            end=close,
        )

    def _parse_len(self, start: TokenRecord) -> int:
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'len'")
        argument = self._parse_expression()
        close = self._consume(TokenKind.RIGHT_PAREN, "expected ')' after 'len' argument")
        return self._append(
            NodeKind.LEN,
            start,
            children=(argument,),
            end=close,
        )

    def _parse_match_expression(self, start: TokenRecord) -> int:
        selector = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after match expression selector")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected block indentation")
        cases: list[int] = []
        had_fallback = False
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            if had_fallback:
                self._raise(
                    "explicit case arm after fallback arm in match expression",
                    code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                )
            case, fallback = self._parse_expression_match_case()
            had_fallback = had_fallback or fallback
            cases.append(case)
        if not cases:
            self._raise("expected at least one match arm")
        self._consume(TokenKind.DEDENT, "expected dedent after match arms")
        return self._append(
            NodeKind.MATCH,
            start,
            children=(selector,) + tuple(cases),
        )

    def _parse_expression_match_case(self) -> tuple[int, bool]:
        if self._match(TokenKind.ELSE):
            start = self._previous()
            self._consume(TokenKind.COLON, "expected ':' after 'else'")
            expression = self._parse_expression()
            self._consume_statement_newline(
                "expected newline after match arm expression"
            )
            return (
                self._append(
                    NodeKind.MATCH_CASE,
                    start,
                    children=(expression,),
                ),
                True,
            )

        label, start = self._parse_match_case_label()
        self._consume(TokenKind.COLON, "expected ':' after case label")
        expression = self._parse_expression()
        self._consume_statement_newline(
            "expected newline after match arm expression"
        )
        return (
            self._append(
                NodeKind.MATCH_CASE,
                start,
                children=(label, expression),
            ),
            False,
        )

    def _parse_match_case_label(self) -> tuple[int, TokenRecord]:
        negative = self._match(TokenKind.MINUS)
        start = self._previous() if negative else self._peek()
        if self._check(TokenKind.INTEGER):
            integer = self._advance()
            value = int(integer.text)
            if negative:
                value = -value
            return self._integer_literal(value, start), start
        if negative:
            self._raise(
                "expected integer case label or 'else'",
                code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
            )

        if self._check(TokenKind.IDENTIFIER):
            enum_name = self._advance()
            enum_target = self._identifier(enum_name.text, enum_name)
            if self._is_generic_type_qualifier_start():
                type_arguments = self._parse_type_arguments()
                enum_target = self._append_from_node(
                    NodeKind.GENERIC_TYPE,
                    enum_target,
                    payload=TypePayload(-1),
                    children=(enum_target,) + type_arguments,
                )
            if not self._match(TokenKind.DOT):
                self._raise(
                    "expected integer case label or 'else'",
                    enum_name,
                    code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                )
            member = self._consume(
                TokenKind.IDENTIFIER,
                "expected enum variant in case label",
            )
            label = self._append_from_node(
                NodeKind.FIELD_ACCESS,
                enum_target,
                payload=SymbolPayload(self._symbol(member.text)),
                children=(enum_target,),
                end=member,
            )
            while self._match(TokenKind.DOT):
                member = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected enum variant in case label",
                )
                label = self._append_from_node(
                    NodeKind.FIELD_ACCESS,
                    label,
                    payload=SymbolPayload(self._symbol(member.text)),
                    children=(label,),
                    end=member,
                )
            if self._match(TokenKind.LEFT_PAREN):
                bindings: list[int] = []
                if self._check(TokenKind.RIGHT_PAREN):
                    self._raise(
                        "expected payload binding name",
                        code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                    )
                while True:
                    binding = self._consume(
                        TokenKind.IDENTIFIER,
                        "expected payload binding name",
                    )
                    bindings.append(self._identifier(binding.text, binding))
                    if not self._match(TokenKind.COMMA):
                        break
                    if self._check(TokenKind.RIGHT_PAREN):
                        self._raise(
                            "expected payload binding name after ','",
                            code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                        )
                close = self._consume(
                    TokenKind.RIGHT_PAREN,
                    "expected ')' after payload bindings",
                )
                return (
                    self._append(
                        NodeKind.MATCH_PAYLOAD_LABEL,
                        enum_name,
                        children=(label,) + tuple(bindings),
                        end=close,
                    ),
                    enum_name,
                )
            return label, enum_name

        self._raise(
            "expected integer case label, enum variant, or 'else'",
            code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
        )
        raise AssertionError("unreachable")

    # ------------------------------------------------------------------
    # Lookahead and structural helpers
    # ------------------------------------------------------------------

    def _is_record_field_argument_start(self) -> bool:
        return (
            self._check(TokenKind.IDENTIFIER)
            and self.current + 1 < len(self.tokens)
            and self.tokens[self.current + 1].kind is TokenKind.EQUAL
        )

    def _is_generic_call_start(self) -> bool:
        return self._generic_tail_followed_by(TokenKind.LEFT_PAREN)

    def _is_generic_type_qualifier_start(self) -> bool:
        return self._generic_tail_followed_by(TokenKind.DOT)

    def _generic_tail_followed_by(self, follower: TokenKind) -> bool:
        if self.current >= len(self.tokens) or self.tokens[self.current].kind is not TokenKind.LESS:
            return False
        cursor = self.current + 1
        depth = 1
        while cursor < len(self.tokens):
            kind = self.tokens[cursor].kind
            if kind is TokenKind.LESS:
                depth += 1
            elif kind is TokenKind.GREATER:
                depth -= 1
                if depth == 0:
                    return (
                        cursor + 1 < len(self.tokens)
                        and self.tokens[cursor + 1].kind is follower
                    )
            cursor += 1
        return False

    def _qualified_name(self, node_id: int) -> str | None:
        node = self.arena.node(node_id)
        payload = self.arena.payload(node)
        if node.kind is NodeKind.IDENTIFIER and isinstance(payload, SymbolPayload):
            return self.interner.name(payload.symbol_id)
        if node.kind is NodeKind.GENERIC_TYPE:
            children = self.arena.child_ids(node_id)
            return self._qualified_name(children[0]) if children else None
        if node.kind is NodeKind.FIELD_ACCESS and isinstance(payload, SymbolPayload):
            children = self.arena.child_ids(node_id)
            if not children:
                return None
            prefix = self._qualified_name(children[0])
            if prefix is None:
                return None
            return f"{prefix}.{self.interner.name(payload.symbol_id)}"
        return None

    def _embedded_type_arguments(self, node_id: int) -> tuple[int, ...]:
        node = self.arena.node(node_id)
        children = self.arena.child_ids(node_id)
        if node.kind is NodeKind.GENERIC_TYPE:
            return children[1:]
        if node.kind is NodeKind.FIELD_ACCESS and children:
            return self._embedded_type_arguments(children[0])
        return ()

    def _type_name_node(self, name: str, token: TokenRecord) -> int:
        return self._append(
            NodeKind.TYPE_NAME,
            token,
            payload=SymbolPayload(self._symbol(name)),
        )

    def _integer_literal(self, value: int, token: TokenRecord) -> int:
        return self._append(
            NodeKind.INTEGER_LITERAL,
            token,
            payload=IntegerPayload(value),
        )

    def _identifier(self, name: str, token: TokenRecord) -> int:
        return self._append(
            NodeKind.IDENTIFIER,
            token,
            payload=SymbolPayload(self._symbol(name)),
        )

    def _symbol(self, value: str) -> int:
        return self.interner.intern(value)

    def _append(
        self,
        kind: NodeKind,
        start: TokenRecord,
        *,
        payload=None,
        children: tuple[int, ...] = (),
        end: TokenRecord | None = None,
    ) -> int:
        span_end = end.span.end if end is not None else start.span.end
        for child_id in children:
            span_end = max(span_end, self.arena.node(child_id).span.end)
        return self.arena.append_node(
            kind,
            SyntaxSpan(
                self.token_arena.file_id,
                start.span.start,
                max(start.span.start, span_end),
            ),
            payload=payload,
            children=children,
        )

    def _append_from_node(
        self,
        kind: NodeKind,
        start_node_id: int,
        *,
        payload=None,
        children: tuple[int, ...] = (),
        end: TokenRecord | None = None,
    ) -> int:
        start_node = self.arena.node(start_node_id)
        span_end = end.span.end if end is not None else start_node.span.end
        for child_id in children:
            span_end = max(span_end, self.arena.node(child_id).span.end)
        return self.arena.append_node(
            kind,
            SyntaxSpan(
                self.token_arena.file_id,
                start_node.span.start,
                max(start_node.span.start, span_end),
            ),
            payload=payload,
            children=children,
        )

    def _location(self, token: TokenRecord) -> SourceLocation:
        return SourceLocation(
            token.source_position,
            token.line,
            token.column,
        )

    def _raise(
        self,
        message: str,
        token: TokenRecord | None = None,
        *,
        code: DiagnosticCode | None = None,
    ) -> None:
        found = self._peek() if token is None else token
        if code is None:
            raise ParseError(message, self._location(found))
        raise ParseError(
            message,
            self._location(found),
            diagnostic_category=None,
            diagnostic_code=code,
        )

    def _consume(
        self,
        kind: TokenKind,
        message: str,
    ) -> TokenRecord:
        if self._check(kind):
            return self._advance()
        found = self._peek()
        suffix = "end of file" if found.kind is TokenKind.EOF else repr(found.text)
        self._raise(f"{message}; found {suffix}", found)
        raise AssertionError("unreachable")

    def _consume_identifier(self, message: str) -> TokenRecord:
        if self._check(TokenKind.IDENTIFIER) or self._check(TokenKind.SELECT) or self._check(TokenKind.CASE):
            return self._advance()
        found = self._peek()
        suffix = "end of file" if found.kind is TokenKind.EOF else repr(found.text)
        self._raise(f"{message}; found {suffix}", found)
        raise AssertionError("unreachable")

    def _consume_statement_newline(self, message: str) -> None:
        if (
            self._previous().kind is TokenKind.DEDENT
            or self._check(TokenKind.DEDENT)
            or self._check(TokenKind.EOF)
        ):
            self._match(TokenKind.NEWLINE)
        else:
            self._consume(TokenKind.NEWLINE, message)

    def _match(self, *kinds: TokenKind) -> bool:
        if self._peek().kind not in kinds:
            return False
        self._advance()
        return True

    def _check(self, kind: TokenKind) -> bool:
        return self._peek().kind is kind

    def _advance(self) -> TokenRecord:
        token = self._peek()
        if token.kind is not TokenKind.EOF:
            self.current += 1
        return token

    def _peek(self) -> TokenRecord:
        return self.tokens[self.current]

    def _previous(self) -> TokenRecord:
        return self.tokens[self.current - 1]

    def _next_kind(self) -> TokenKind:
        if self.current + 1 >= len(self.tokens):
            return TokenKind.EOF
        return self.tokens[self.current + 1].kind

    def _skip_newlines(self) -> None:
        while self._match(TokenKind.NEWLINE):
            pass


def parse_token_arena(
    token_arena: TokenArena,
    *,
    interner: SymbolInterner | None = None,
) -> IndependentParseResult:
    """Parse TokenArena directly without bootstrap.s3.ast or parser.py."""

    return GenericParser(token_arena, interner=interner).parse_program()


__all__ = [
    "GenericParser",
    "GenericParserError",
    "IndependentParseResult",
    "parse_token_arena",
]
