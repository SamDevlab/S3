"""Recursive-descent parser for the first S3 grammar."""

from __future__ import annotations

from collections.abc import Callable

from . import ast
from .diagnostics import DiagnosticCode, ParseError, SourceLocation
from .lexer import SyntaxMode, Token, TokenKind, tokenize


class Parser:
    def __init__(self, tokens: tuple[Token, ...], mode: SyntaxMode = SyntaxMode.V0_6):
        self.tokens = tokens
        self.current = 0
        self.mode = mode
        self._active_type_parameters: set[str] = set()

    def parse_program(self) -> ast.Program:
        functions: list[ast.FunctionDeclaration] = []
        records: list[ast.RecordDeclaration] = []
        enums: list[ast.EnumDeclaration] = []
        foreign_functions: list[ast.ForeignFunctionDeclaration] = []
        location = self._peek().location
        self._skip_newlines()
        module = self._parse_module_declaration()
        self._skip_newlines()
        imports: list[ast.ImportDeclaration] = []
        while self.mode is SyntaxMode.V0_6 and self._check(TokenKind.FROM):
            imports.append(self._parse_import_declaration())
            self._skip_newlines()
        while not self._check(TokenKind.EOF):
            self._skip_newlines()
            if self._check(TokenKind.EOF):
                break
            exported = False
            if self.mode is SyntaxMode.V0_6 and self._match(TokenKind.EXPORT):
                exported = True
            if self.mode is SyntaxMode.V0_6 and self._match(TokenKind.FOREIGN):
                foreign_functions.append(self._parse_foreign_function())
            elif self.mode is SyntaxMode.V0_6 and self._check(TokenKind.RECORD):
                records.append(self._parse_record_declaration(exported=exported))
            elif self.mode is SyntaxMode.V0_6 and self._check(TokenKind.ENUM):
                enums.append(self._parse_enum_declaration(exported=exported))
            else:
                functions.append(self._parse_function(exported=exported))
        if not functions:
            raise ParseError("expected at least one function", self._peek().location)
        return ast.Program(
            tuple(functions),
            location,
            module=module,
            imports=tuple(imports),
            records=tuple(records),
            enums=tuple(enums),
            foreign_functions=tuple(foreign_functions),
        )

    def _parse_foreign_function(self) -> ast.ForeignFunctionDeclaration:
        start = self._consume(TokenKind.FN, "expected 'fn' after 'foreign'")
        name = self._consume(TokenKind.IDENTIFIER, "expected foreign function name")
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after foreign function name")
        parameters = self._parse_parameters()
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after parameters")
        self._consume(TokenKind.ARROW, "expected '->' before foreign return type")
        return_type = self._parse_type()
        self._consume_statement_newline("expected newline after foreign declaration")
        return ast.ForeignFunctionDeclaration(
            ast.FunctionSignature(name.text, tuple(parameters), return_type, name.location),
            start.location,
        )

    def _parse_module_declaration(self) -> ast.ModuleDeclaration | None:
        if self.mode is not SyntaxMode.V0_6 or not self._match(TokenKind.MODULE):
            return None
        start = self._previous()
        module_name = self._parse_module_name()
        self._consume_statement_newline("expected newline after module declaration")
        return ast.ModuleDeclaration(module_name, start.location)

    def _parse_import_declaration(self) -> ast.ImportDeclaration:
        start = self._consume(TokenKind.FROM, "expected 'from'")
        module_name = self._parse_module_name()
        self._consume(TokenKind.IMPORT, "expected 'import' after module name")
        symbol = self._consume(TokenKind.IDENTIFIER, "expected imported symbol")
        alias = None
        if self._match(TokenKind.AS):
            alias_token = self._consume(TokenKind.IDENTIFIER, "expected import alias")
            alias = alias_token.text
        self._consume_statement_newline("expected newline after import declaration")
        return ast.ImportDeclaration(
            module_name,
            symbol.text,
            alias,
            start.location,
        )

    def _parse_module_name(self) -> str:
        parts = [
            self._consume(TokenKind.IDENTIFIER, "expected module name").text
        ]
        while self._match(TokenKind.DOT):
            parts.append(
                self._consume(
                    TokenKind.IDENTIFIER,
                    "expected module name after '.'",
                ).text
            )
        return ".".join(parts)

    def _parse_function(self, *, exported: bool = False) -> ast.FunctionDeclaration:
        start = self._consume(TokenKind.FN, "expected 'fn'")
        name = self._consume(TokenKind.IDENTIFIER, "expected function name")
        type_parameters = self._parse_type_parameters()
        prior_type_parameters = self._active_type_parameters
        self._active_type_parameters = {item.name for item in type_parameters}
        try:
            self._consume(TokenKind.LEFT_PAREN, "expected '(' after function name")
            parameters = self._parse_parameters()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after parameters")
            self._consume(TokenKind.ARROW, "expected '->' before return type")
            return_type = self._parse_type()
            if self.mode is SyntaxMode.V0_6:
                if self._check(TokenKind.LEFT_BRACE):
                    raise ParseError("obsolete brace syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_BRACE)
                self._consume(TokenKind.COLON, "expected ':' after return type")
                self._consume(TokenKind.NEWLINE, "expected newline after ':'")
                self._consume(TokenKind.INDENT, "expected indented block")
                body = self._parse_block_v0_6()
            else:
                body = self._parse_block()
        finally:
            self._active_type_parameters = prior_type_parameters

        signature = ast.FunctionSignature(
            name.text,
            tuple(parameters),
            return_type,
            name.location,
            tuple(type_parameters),
        )
        return ast.FunctionDeclaration(signature, body, start.location, exported)

    def _parse_type_parameters(self) -> list[ast.TypeParameter]:
        if not self._match(TokenKind.LESS):
            return []
        parameters: list[ast.TypeParameter] = []
        while True:
            token = self._consume(TokenKind.IDENTIFIER, "expected type parameter name")
            constraint = "value"
            if self._match(TokenKind.COLON):
                constraint = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected type parameter constraint",
                ).text
            parameters.append(ast.TypeParameter(token.text, constraint, token.location))
            if not self._match(TokenKind.COMMA):
                break
            if self._check(TokenKind.GREATER):
                raise ParseError("expected type parameter after ','", self._peek().location)
        self._consume(TokenKind.GREATER, "expected '>' after type parameters")
        names = [item.name for item in parameters]
        if len(set(names)) != len(names):
            raise ParseError("duplicate type parameter", parameters[-1].location)
        return parameters

    def _parse_record_declaration(
        self,
        *,
        exported: bool = False,
    ) -> ast.RecordDeclaration:
        start = self._consume(TokenKind.RECORD, "expected 'record'")
        name = self._consume(TokenKind.IDENTIFIER, "expected record name")
        self._consume(TokenKind.COLON, "expected ':' after record name")
        self._consume(TokenKind.NEWLINE, "expected newline after record ':'")
        self._consume(TokenKind.INDENT, "expected indented record fields")
        fields: list[ast.RecordField] = []
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            field_name = self._consume(
                TokenKind.IDENTIFIER,
                "expected record field name",
            )
            self._consume(TokenKind.COLON, "expected ':' after record field name")
            type_name = self._parse_type()
            self._consume_statement_newline("expected newline after record field")
            fields.append(ast.RecordField(field_name.text, type_name, field_name.location))
        if not fields:
            raise ParseError("expected at least one record field", name.location)
        self._consume(TokenKind.DEDENT, "expected dedent after record declaration")
        return ast.RecordDeclaration(name.text, tuple(fields), start.location, exported)

    def _parse_enum_declaration(
        self,
        *,
        exported: bool = False,
    ) -> ast.EnumDeclaration:
        start = self._consume(TokenKind.ENUM, "expected 'enum'")
        name = self._consume(TokenKind.IDENTIFIER, "expected enum name")
        self._consume(TokenKind.COLON, "expected ':' after enum name")
        self._consume(TokenKind.NEWLINE, "expected newline after enum ':'")
        self._consume(TokenKind.INDENT, "expected indented enum variants")
        variants: list[ast.EnumVariant] = []
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            variant = self._consume(
                TokenKind.IDENTIFIER,
                "expected enum variant name",
            )
            payload_fields: list[ast.RecordField] = []
            if self._match(TokenKind.LEFT_PAREN):
                if self._check(TokenKind.RIGHT_PAREN):
                    raise ParseError("expected enum payload field", self._peek().location)
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
                    payload_fields.append(
                        ast.RecordField(field_name.text, field_type, field_name.location)
                    )
                    if not self._match(TokenKind.COMMA):
                        break
                    if self._check(TokenKind.RIGHT_PAREN):
                        raise ParseError(
                            "expected enum payload field after ','",
                            self._peek().location,
                        )
                self._consume(TokenKind.RIGHT_PAREN, "expected ')' after enum payload fields")
            self._consume_statement_newline("expected newline after enum variant")
            variants.append(ast.EnumVariant(variant.text, variant.location, tuple(payload_fields)))
        if not variants:
            raise ParseError("expected at least one enum variant", name.location)
        self._consume(TokenKind.DEDENT, "expected dedent after enum declaration")
        return ast.EnumDeclaration(name.text, tuple(variants), start.location, exported)

    def _parse_parameters(self) -> list[ast.Parameter]:
        parameters: list[ast.Parameter] = []
        if self._check(TokenKind.RIGHT_PAREN):
            return parameters
        while True:
            name = self._consume(TokenKind.IDENTIFIER, "expected parameter name")
            self._consume(TokenKind.COLON, "expected ':' after parameter name")
            type_name = self._parse_type()
            parameters.append(ast.Parameter(name.text, type_name, name.location))
            if not self._match(TokenKind.COMMA):
                return parameters
            if self._check(TokenKind.RIGHT_PAREN):
                raise ParseError(
                    "expected parameter after ','",
                    self._peek().location,
                )

    def _parse_type(self) -> ast.DeclaredType:
        start = self._peek()
        if self._match(TokenKind.AMPERSAND):
            mutable = self._match(TokenKind.MUT)
            if self._match(TokenKind.LEFT_BRACKET):
                element = self._parse_type()
                if not isinstance(element, ast.TypeName):
                    raise ParseError(
                        "slice element type must be a scalar type",
                        element.location,
                    )
                self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after slice element type")
                return ast.SliceType(element, mutable, start.location)
            target = self._parse_type()
            return ast.ReferenceType(target, mutable, start.location)
        if self._match(TokenKind.TRIT):
            result: ast.DeclaredType = ast.TypeName.TRIT
        elif self._match(TokenKind.TRYTE):
            result = ast.TypeName.TRYTE
        elif self._match(TokenKind.I64):
            result = ast.TypeName.I64
        elif self._match(TokenKind.F64):
            result = ast.TypeName.F64
        elif self._check(TokenKind.IDENTIFIER) and self._peek().text in {
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
        }:
            name = self._advance().text
            result = {
                "string": ast.TypeName.STRING,
                "bytes": ast.TypeName.BYTES,
                "text": ast.TypeName.TEXT,
                "tryte_vector": ast.TypeName.TRYTE_VECTOR,
                "i64_vector": ast.TypeName.I64_VECTOR,
                "f64_vector": ast.TypeName.F64_VECTOR,
                "i64_map": ast.TypeName.I64_MAP,
                "i64_set": ast.TypeName.I64_SET,
                "host_capability": ast.TypeName.HOST_CAPABILITY,
                "resource_handle": ast.TypeName.RESOURCE_HANDLE,
            }[name]
        elif self._check(TokenKind.IDENTIFIER):
            nominal = self._advance()
            if nominal.text in self._active_type_parameters:
                result = ast.TypeParameterType(nominal.text, nominal.location)
                while self._match(TokenKind.LEFT_BRACKET):
                    raise ParseError(
                        "type parameter arrays require a concrete specialization",
                        nominal.location,
                    )
                return result
            parts = [nominal.text]
            while self.mode is SyntaxMode.V0_6 and self._match(TokenKind.DOT):
                parts.append(
                    self._consume(
                        TokenKind.IDENTIFIER,
                        "expected nominal type name after '.'",
                    ).text
                )
            result = ast.NominalType(".".join(parts), nominal.location)
        else:
            raise ParseError(
                "expected type 'trit', 'tryte', 'i64', 'f64', 'string', or nominal type",
                self._peek().location,
            )
        while self._match(TokenKind.LEFT_BRACKET):
            negative = self._match(TokenKind.MINUS)
            length = self._consume(
                TokenKind.INTEGER,
                "expected static array length",
            )
            value = int(length.text)
            if negative:
                value = -value
            self._consume(
                TokenKind.RIGHT_BRACKET,
                "expected ']' after array length",
            )
            result = ast.ArrayType(result, value, start.location)
        return result

    def _parse_block(self) -> ast.Block:
        start = self._consume(TokenKind.LEFT_BRACE, "expected '{'")
        statements: list[ast.Statement] = []
        while not self._check(TokenKind.RIGHT_BRACE) and not self._check(TokenKind.EOF):
            statements.append(self._parse_statement())
        self._consume(TokenKind.RIGHT_BRACE, "expected '}' after block")
        return ast.Block(tuple(statements), start.location)

    def _parse_block_v0_6(self) -> ast.Block:
        start = self._previous()
        statements: list[ast.Statement] = []
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            statements.append(self._parse_statement())
        if not statements:
            raise ParseError("expected at least one statement in block", self._peek().location)
        self._consume(TokenKind.DEDENT, "expected dedent after block")
        return ast.Block(tuple(statements), start.location)

    def _parse_statement(self) -> ast.Statement:
        if self.mode is SyntaxMode.V0_6:
            if self._check(TokenKind.LEFT_BRACE) or self._check(TokenKind.RIGHT_BRACE):
                raise ParseError("obsolete brace syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_BRACE)
            if self._check(TokenKind.SEMICOLON):
                raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
            if self._check(TokenKind.SWITCH):
                raise ParseError("obsolete 'switch' syntax, use 'match'", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SWITCH)

            if self._match(TokenKind.BREAK):
                return self._parse_break_v0_6(self._previous())
            if self._match(TokenKind.CONTINUE):
                return self._parse_continue_v0_6(self._previous())
            if self._match(TokenKind.RETURN):
                return self._parse_return_v0_6(self._previous())
            if self._match(TokenKind.MATCH):
                return self._parse_match_v0_6(self._previous())
            if self._match(TokenKind.WHILE):
                return self._parse_while_v0_6(self._previous())
            if self._match(TokenKind.FOR):
                return self._parse_for_v0_6(self._previous())
            if self._match(TokenKind.DISCARD):
                return self._parse_discard_v0_6(self._previous())
            if self._check(TokenKind.MUT):
                return self._parse_variable_declaration_v0_6()
            if self._check(TokenKind.IDENTIFIER):
                next_token = self.tokens[self.current + 1] if self.current + 1 < len(self.tokens) else None
                if next_token and next_token.kind is TokenKind.COLON:
                    return self._parse_variable_declaration_v0_6()
                return self._parse_assignment_v0_6()
            if self._check(TokenKind.STAR):
                return self._parse_assignment_v0_6()
            raise ParseError("expected variable declaration, 'return', 'while', 'for', 'break', 'continue', or assignment", self._peek().location)

        if (
            self._check(TokenKind.MUT)
            or self._check(TokenKind.TRIT)
            or self._check(TokenKind.TRYTE)
            or self._check(TokenKind.I64)
            or self._check(TokenKind.F64)
        ):
            return self._parse_variable_declaration()
        if self._match(TokenKind.RETURN):
            return self._parse_return(self._previous())
        if self._match(TokenKind.SWITCH):
            return self._parse_switch(self._previous())
        if self._check(TokenKind.IDENTIFIER) or self._check(TokenKind.STAR):
            return self._parse_assignment()
        raise ParseError(
            "expected variable declaration, 'return', or 'switch'",
            self._peek().location,
        )

    def _parse_variable_declaration_v0_6(self) -> ast.VariableDeclaration:
        start = self._peek()
        mutable = self._match(TokenKind.MUT)
        name = self._consume(TokenKind.IDENTIFIER, "expected variable name")
        self._consume(TokenKind.COLON, "expected ':' after variable name")
        type_name = self._parse_type()
        self._consume(TokenKind.EQUAL, "expected '=' after variable type")
        initializer = self._parse_initializer()
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume_statement_newline("expected newline after declaration")
        return ast.VariableDeclaration(
            type_name,
            name.text,
            initializer,
            start.location,
            mutable,
        )

    def _parse_assignment_v0_6(self) -> ast.Statement:
        if self._match(TokenKind.STAR):
            start = self._previous()
            reference = self._parse_unary()
            target = ast.DereferenceTarget(reference, start.location)
            self._consume(TokenKind.EQUAL, "expected '=' after dereference target")
            value = self._parse_initializer()
            self._consume_statement_newline("expected newline after assignment")
            return ast.AssignmentStatement(target, value, start.location)
        name = self._consume(TokenKind.IDENTIFIER, "expected assignment target")
        target: ast.AssignmentTarget
        if self._match(TokenKind.LEFT_BRACKET):
            index = self._parse_expression()
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
            base: ast.Expression = ast.IndexExpression(
                ast.Identifier(name.text, name.location),
                index,
                name.location,
            )
            if self._match(TokenKind.DOT):
                field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
                while self._match(TokenKind.DOT):
                    base = ast.FieldAccessExpression(base, field.text, field.location)
                    field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
                target = ast.FieldTarget(base, field.text, field.location)
            else:
                target = ast.IndexTarget(name.text, index, name.location)
        elif self._match(TokenKind.DOT):
            base: ast.Expression = ast.Identifier(name.text, name.location)
            field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
            while self._match(TokenKind.DOT):
                base = ast.FieldAccessExpression(base, field.text, field.location)
                field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
            target = ast.FieldTarget(base, field.text, field.location)
        else:
            target = ast.VariableTarget(name.text, name.location)
        if self._match(TokenKind.PLUS_EQUAL):
            op = ast.BinaryOperator.ADD
        else:
            self._consume(TokenKind.EQUAL, "expected '=' or '+=' after assignment target")
            op = None
        value = self._parse_initializer()
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume_statement_newline("expected newline after assignment")
        if op is not None:
            return ast.CompoundAssignmentStatement(target, op, value, name.location)
        return ast.AssignmentStatement(target, value, name.location)

    def _parse_return_v0_6(self, start: Token) -> ast.ReturnStatement:
        expression = self._parse_expression()
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume_statement_newline("expected newline after return value")
        return ast.ReturnStatement(expression, start.location)

    def _parse_match_v0_6(self, start: Token) -> ast.SwitchStatement:
        expression = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after match expression")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")

        cases: list[ast.TernaryCase] = []
        had_fallback = False
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            if had_fallback:
                raise ParseError("explicit case arm after fallback arm in match statement", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)
            case = self._parse_ternary_case_v0_6()
            if case.label is None:
                had_fallback = True
            cases.append(case)

        if not cases:
            raise ParseError("expected at least one match arm", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_EXPECTED_MATCH_ARM)

        self._consume(TokenKind.DEDENT, "expected dedent after match block")
        return ast.SwitchStatement(expression, tuple(cases), start.location)

    def _parse_while_v0_6(self, start: Token) -> ast.WhileStatement:
        condition = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after while condition")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")

        body = self._parse_block_v0_6()

        return ast.WhileStatement(condition, body, start.location)

    def _parse_for_v0_6(self, start: Token) -> ast.ForStatement:
        variable_name = self._consume(TokenKind.IDENTIFIER, "expected loop variable name")
        self._consume(TokenKind.COLON, "expected ':' after loop variable name")
        variable_type = self._parse_type()
        self._consume(TokenKind.IN, "expected 'in' after loop variable type")
        self._consume(TokenKind.RANGE, "expected 'range' after 'in'")
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'range'")
        arg1 = self._parse_expression()
        if self._match(TokenKind.COMMA):
            arg2 = self._parse_expression()
            if self._match(TokenKind.COMMA):
                arg3 = self._parse_expression()
                start_expression = arg1
                end_expression = arg2
                step_expression = arg3
            else:
                start_expression = arg1
                end_expression = arg2
                step_expression = ast.IntegerLiteral(1, start_expression.location)
        else:
            start_expression = ast.IntegerLiteral(0, arg1.location)
            end_expression = arg1
            step_expression = ast.IntegerLiteral(1, arg1.location)
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after range bounds")
        self._consume(TokenKind.COLON, "expected ':' after range clause")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")

        body = self._parse_block_v0_6()

        return ast.ForStatement(
            variable_name.text,
            variable_type,
            start_expression,
            end_expression,
            step_expression,
            body,
            start.location,
        )

    def _parse_discard_v0_6(self, start: Token) -> ast.DiscardStatement:
        expression = self._parse_expression()
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume_statement_newline("expected newline after discard expression")
        return ast.DiscardStatement(expression, start.location)

    def _parse_break_v0_6(self, start: Token) -> ast.BreakStatement:
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume(TokenKind.NEWLINE, "expected newline after break")
        return ast.BreakStatement(start.location)

    def _parse_continue_v0_6(self, start: Token) -> ast.ContinueStatement:
        if self._check(TokenKind.SEMICOLON):
            raise ParseError("obsolete ';' syntax", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_OBSOLETE_SEMICOLON)
        self._consume(TokenKind.NEWLINE, "expected newline after continue")
        return ast.ContinueStatement(start.location)

    def _parse_ternary_case_v0_6(self) -> ast.TernaryCase:
        if self._match(TokenKind.ELSE):
            start = self._previous()
            self._consume(TokenKind.COLON, "expected ':' after 'else'")
            self._consume(TokenKind.NEWLINE, "expected newline after ':'")
            self._consume(TokenKind.INDENT, "expected indented block")
            body = self._parse_block_v0_6()
            return ast.TernaryCase(None, body, start.location)

        label, location = self._parse_match_case_label_v0_6()
        self._consume(TokenKind.COLON, "expected ':' after case label")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")
        body = self._parse_block_v0_6()
        return ast.TernaryCase(label, body, location)

    def _parse_match_case_label_v0_6(self) -> tuple[ast.MatchCaseLabel, SourceLocation]:
        negative = self._match(TokenKind.MINUS)
        start = self._previous() if negative else self._peek()
        if self._check(TokenKind.INTEGER):
            integer = self._advance()
            value = int(integer.text)
            if negative:
                value = -value
            return value, start.location
        if negative:
            raise ParseError("expected integer case label or 'else'", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)
        if self._check(TokenKind.IDENTIFIER):
            enum_name = self._advance()
            if not self._match(TokenKind.DOT):
                raise ParseError("expected integer case label or 'else'", enum_name.location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)
            member = self._consume(
                TokenKind.IDENTIFIER,
                "expected enum variant in case label",
            )
            label: ast.FieldAccessExpression = ast.FieldAccessExpression(
                ast.Identifier(enum_name.text, enum_name.location),
                member.text,
                enum_name.location,
            )
            while self._match(TokenKind.DOT):
                member = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected enum variant in case label",
                )
                label = ast.FieldAccessExpression(
                    label,
                    member.text,
                    enum_name.location,
                )
            if self._match(TokenKind.LEFT_PAREN):
                bindings: list[str] = []
                if self._check(TokenKind.RIGHT_PAREN):
                    raise ParseError(
                        "expected payload binding name",
                        self._peek().location,
                        diagnostic_category=None,
                        diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                    )
                while True:
                    binding = self._consume(
                        TokenKind.IDENTIFIER,
                        "expected payload binding name",
                    )
                    bindings.append(binding.text)
                    if not self._match(TokenKind.COMMA):
                        break
                    if self._check(TokenKind.RIGHT_PAREN):
                        raise ParseError(
                            "expected payload binding name after ','",
                            self._peek().location,
                            diagnostic_category=None,
                            diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM,
                        )
                self._consume(TokenKind.RIGHT_PAREN, "expected ')' after payload bindings")
                return (
                    ast.MatchPayloadLabel(label, tuple(bindings), enum_name.location),
                    enum_name.location,
                )
            return (
                label,
                enum_name.location,
            )
        raise ParseError("expected integer case label, enum variant, or 'else'", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)

    def _parse_variable_declaration(self) -> ast.VariableDeclaration:
        start = self._peek()
        mutable = self._match(TokenKind.MUT)
        type_name = self._parse_type()
        name = self._consume(TokenKind.IDENTIFIER, "expected variable name")
        self._consume(TokenKind.EQUAL, "expected '=' after variable name")
        initializer = self._parse_initializer()
        self._consume(
            TokenKind.SEMICOLON,
            "expected ';' after variable declaration",
        )
        return ast.VariableDeclaration(
            type_name,
            name.text,
            initializer,
            start.location,
            mutable,
        )

    def _parse_assignment(self) -> ast.AssignmentStatement:
        name = self._consume(TokenKind.IDENTIFIER, "expected assignment target")
        target: ast.AssignmentTarget
        if self._match(TokenKind.LEFT_BRACKET):
            index = self._parse_expression()
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
            base: ast.Expression = ast.IndexExpression(
                ast.Identifier(name.text, name.location),
                index,
                name.location,
            )
            if self._match(TokenKind.DOT):
                field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
                while self._match(TokenKind.DOT):
                    base = ast.FieldAccessExpression(base, field.text, field.location)
                    field = self._consume(TokenKind.IDENT, "expected field name after '.'")
                target = ast.FieldTarget(base, field.text, field.location)
            else:
                target = ast.IndexTarget(name.text, index, name.location)
        elif self._match(TokenKind.DOT):
            base = ast.Identifier(name.text, name.location)
            field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
            while self._match(TokenKind.DOT):
                base = ast.FieldAccessExpression(base, field.text, field.location)
                field = self._consume(TokenKind.IDENTIFIER, "expected field name after '.'")
            target = ast.FieldTarget(base, field.text, field.location)
        else:
            target = ast.VariableTarget(name.text, name.location)
        self._consume(TokenKind.EQUAL, "expected '=' after assignment target")
        value = self._parse_initializer()
        self._consume(TokenKind.SEMICOLON, "expected ';' after assignment")
        return ast.AssignmentStatement(target, value, name.location)

    def _parse_initializer(self) -> ast.Initializer:
        if self._match(TokenKind.LEFT_BRACKET):
            return self._finish_array_literal(self._previous())
        return self._parse_expression()

    def _finish_array_literal(self, start: Token) -> ast.ArrayLiteral:
        elements: list[ast.Expression] = []
        if not self._check(TokenKind.RIGHT_BRACKET):
            while True:
                elements.append(self._parse_expression())
                if not self._match(TokenKind.COMMA):
                    break
                if self._check(TokenKind.RIGHT_BRACKET):
                    raise ParseError(
                        "expected array element after ','",
                        self._peek().location,
                    )
        self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after array literal")
        return ast.ArrayLiteral(tuple(elements), start.location)

    def _parse_return(self, start: Token) -> ast.ReturnStatement:
        expression = self._parse_expression()
        self._consume(TokenKind.SEMICOLON, "expected ';' after return value")
        return ast.ReturnStatement(expression, start.location)

    def _parse_switch(self, start: Token) -> ast.SwitchStatement:
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'switch'")
        expression = self._parse_expression()
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after switch expression")
        self._consume(TokenKind.LEFT_BRACE, "expected '{' before switch cases")
        cases: list[ast.TernaryCase] = []
        while not self._check(TokenKind.RIGHT_BRACE) and not self._check(TokenKind.EOF):
            cases.append(self._parse_ternary_case())
        self._consume(TokenKind.RIGHT_BRACE, "expected '}' after switch cases")
        return ast.SwitchStatement(expression, tuple(cases), start.location)

    def _parse_ternary_case(self) -> ast.TernaryCase:
        negative = self._match(TokenKind.MINUS)
        start = self._previous() if negative else self._peek()
        integer = self._consume(
            TokenKind.INTEGER,
            "expected integer case label",
        )
        value = int(integer.text)
        if negative:
            value = -value
        self._consume(TokenKind.COLON, "expected ':' after case label")
        body = self._parse_block()
        return ast.TernaryCase(value, body, start.location)

    def _parse_expression(self) -> ast.Expression:
        return self._parse_relational()

    def _parse_relational(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_compare,
            {
                TokenKind.EQUAL_EQUAL: ast.BinaryOperator.EQUAL,
                TokenKind.NOT_EQUAL: ast.BinaryOperator.NOT_EQUAL,
                TokenKind.LESS: ast.BinaryOperator.LESS,
                TokenKind.LESS_EQUAL: ast.BinaryOperator.LESS_EQUAL,
                TokenKind.GREATER: ast.BinaryOperator.GREATER,
                TokenKind.GREATER_EQUAL: ast.BinaryOperator.GREATER_EQUAL,
            },
        )

    def _parse_compare(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_maximum,
            {TokenKind.COMPARE: ast.BinaryOperator.COMPARE},
        )

    def _parse_maximum(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_minimum,
            {TokenKind.PIPE: ast.BinaryOperator.MAXIMUM},
        )

    def _parse_minimum(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_additive,
            {TokenKind.AMPERSAND: ast.BinaryOperator.MINIMUM},
        )

    def _parse_additive(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_multiplicative,
            {
                TokenKind.PLUS: ast.BinaryOperator.ADD,
                TokenKind.MINUS: ast.BinaryOperator.SUBTRACT,
            },
        )

    def _parse_multiplicative(self) -> ast.Expression:
        return self._parse_left_associative(
            self._parse_unary,
            {
                TokenKind.STAR: ast.BinaryOperator.MULTIPLY,
                TokenKind.SLASH: ast.BinaryOperator.DIVIDE,
            },
        )

    def _parse_left_associative(
        self,
        operand_parser: Callable[[], ast.Expression],
        operators: dict[TokenKind, ast.BinaryOperator],
    ) -> ast.Expression:
        expression = operand_parser()
        while self._peek().kind in operators:
            operator_token = self._advance()
            right = operand_parser()
            expression = ast.BinaryExpression(
                operators[operator_token.kind],
                expression,
                right,
                operator_token.location,
            )
        return expression

    def _parse_unary(self) -> ast.Expression:
        if self._match(TokenKind.AMPERSAND):
            token = self._previous()
            mutable = self._match(TokenKind.MUT)
            return ast.AddressOfExpression(
                self._parse_unary(), mutable, token.location
            )
        if self._match(TokenKind.STAR):
            token = self._previous()
            return ast.DereferenceExpression(self._parse_unary(), token.location)
        if self._match(TokenKind.TILDE):
            token = self._previous()
            return ast.UnaryExpression(
                ast.UnaryOperator.INVERT,
                self._parse_unary(),
                token.location,
            )
        if self._match(TokenKind.MINUS):
            token = self._previous()
            return ast.UnaryExpression(
                ast.UnaryOperator.NEGATE,
                self._parse_unary(),
                token.location,
            )
        return self._parse_postfix()

    def _parse_postfix(self) -> ast.Expression:
        expression = self._parse_primary_atom()
        while True:
            if self._match(TokenKind.LEFT_PAREN):
                if (
                    self._expression_to_qualified_name(expression) is not None
                    and self._is_record_field_argument_start()
                ):
                    expression = self._finish_record_expression(expression)
                else:
                    expression = self._finish_call(expression)
                continue
            if (
                isinstance(expression, ast.Identifier)
                and self._is_generic_call_start()
            ):
                self._consume(TokenKind.LESS, "expected '<' before type arguments")
                type_arguments: list[ast.DeclaredType] = []
                while True:
                    type_arguments.append(self._parse_type())
                    if not self._match(TokenKind.COMMA):
                        break
                self._consume(TokenKind.GREATER, "expected '>' after type arguments")
                self._consume(TokenKind.LEFT_PAREN, "expected '(' after type arguments")
                expression = ast.CallExpression(
                    expression,
                    self._finish_call(expression).arguments,
                    expression.location,
                    tuple(type_arguments),
                )
                continue
            if self._match(TokenKind.LEFT_BRACKET):
                start = self._parse_expression()
                if self._match(TokenKind.COLON):
                    end = self._parse_expression()
                    self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after slice")
                    expression = ast.SliceExpression(
                        expression,
                        start,
                        end,
                        expression.location,
                    )
                    continue
                index = start
                self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
                expression = ast.IndexExpression(
                    expression,
                    index,
                    expression.location,
                )
                continue
            if self._match(TokenKind.DOT):
                field = self._consume(
                    TokenKind.IDENTIFIER,
                    "expected member name after '.'",
                )
                expression = ast.FieldAccessExpression(
                    expression,
                    field.text,
                    expression.location,
                )
                continue
            break
        return expression

    def _is_generic_call_start(self) -> bool:
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
                        and self.tokens[cursor + 1].kind is TokenKind.LEFT_PAREN
                    )
            cursor += 1
        return False

    def _parse_primary_atom(self) -> ast.Expression:
        if self.mode == SyntaxMode.V0_6 and self._match(TokenKind.MATCH):
            return self._parse_match_expression_v0_6(self._previous())
        if self.mode == SyntaxMode.V0_6 and self._match(TokenKind.LEN):
            return self._parse_len_v0_6(self._previous())
        if self._match(TokenKind.INTEGER):
            token = self._previous()
            return ast.IntegerLiteral(int(token.text), token.location)
        if self._match(TokenKind.FLOAT):
            token = self._previous()
            return ast.FloatLiteral(float(token.text), token.location)
        if self._match(TokenKind.STRING_LITERAL):
            token = self._previous()
            return ast.StringLiteral(token.text[1:-1], token.location)
        if self._match(TokenKind.IDENTIFIER):
            token = self._previous()
            return ast.Identifier(token.text, token.location)
        if self._match(TokenKind.LEFT_PAREN):
            expression = self._parse_expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after expression")
            return expression
        raise ParseError("expected expression", self._peek().location)

    def _is_record_field_argument_start(self) -> bool:
        return (
            self._check(TokenKind.IDENTIFIER)
            and self.current + 1 < len(self.tokens)
            and self.tokens[self.current + 1].kind is TokenKind.EQUAL
        )

    def _expression_to_qualified_name(self, expression: ast.Expression) -> str | None:
        if isinstance(expression, ast.Identifier):
            return expression.name
        if isinstance(expression, ast.FieldAccessExpression):
            prefix = self._expression_to_qualified_name(expression.target)
            if prefix is None:
                return None
            return f"{prefix}.{expression.field_name}"
        return None

    def _finish_record_expression(self, type_name: ast.Expression) -> ast.RecordExpression:
        record_name = self._expression_to_qualified_name(type_name)
        if record_name is None:
            raise ParseError(
                "record constructor must be a nominal type name",
                type_name.location,
            )
        fields: list[ast.RecordFieldValue] = []
        while True:
            field = self._consume(TokenKind.IDENTIFIER, "expected record field name")
            self._consume(TokenKind.EQUAL, "expected '=' after record field name")
            expression = self._parse_expression()
            fields.append(ast.RecordFieldValue(field.text, expression, field.location))
            if not self._match(TokenKind.COMMA):
                break
            if self._check(TokenKind.RIGHT_PAREN):
                raise ParseError(
                    "expected record field after ','",
                    self._peek().location,
                )
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after record fields")
        return ast.RecordExpression(record_name, tuple(fields), type_name.location)

    def _parse_len_v0_6(self, start: Token) -> ast.LenExpression:
        self._consume(TokenKind.LEFT_PAREN, "expected '(' after 'len'")
        argument = self._parse_expression()
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after 'len' argument")
        return ast.LenExpression(argument, start.location)

    def _parse_match_expression_v0_6(self, start: Token) -> ast.MatchExpression:
        selector = self._parse_expression()
        self._consume(TokenKind.COLON, "expected ':' after match expression selector")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected block indentation")
        cases: list[ast.MatchExpressionCase] = []
        had_fallback = False
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            if had_fallback:
                raise ParseError("explicit case arm after fallback arm in match expression", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)
            case = self._parse_match_expression_case_v0_6()
            if case.label is None:
                had_fallback = True
            cases.append(case)
        if not cases:
            raise ParseError(
                "expected at least one match arm",
                self._peek().location,
            )
        self._consume(TokenKind.DEDENT, "expected dedent after match arms")
        return ast.MatchExpression(selector, tuple(cases), start.location)

    def _parse_match_expression_case_v0_6(self) -> ast.MatchExpressionCase:
        if self._match(TokenKind.ELSE):
            start = self._previous()
            self._consume(TokenKind.COLON, "expected ':' after 'else'")
            expr = self._parse_expression()
            self._consume_statement_newline("expected newline after match arm expression")
            return ast.MatchExpressionCase(None, expr, start.location)

        label, location = self._parse_match_case_label_v0_6()
        self._consume(TokenKind.COLON, "expected ':' after case label")
        expr = self._parse_expression()
        self._consume_statement_newline("expected newline after match arm expression")
        return ast.MatchExpressionCase(label, expr, location)

    def _finish_call(self, callee: ast.Expression) -> ast.CallExpression:
        arguments: list[ast.CallArgument] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                expression = self._parse_expression()
                arguments.append(ast.CallArgument(expression, expression.location))
                if not self._match(TokenKind.COMMA):
                    break
                if self._check(TokenKind.RIGHT_PAREN):
                    raise ParseError(
                        "expected argument after ','",
                        self._peek().location,
                    )
        self._consume(TokenKind.RIGHT_PAREN, "expected ')' after arguments")
        return ast.CallExpression(
            callee,
            tuple(arguments),
            callee.location,
        )

    def _match(self, kind: TokenKind) -> bool:
        if not self._check(kind):
            return False
        self._advance()
        return True

    def _consume(self, kind: TokenKind, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        found = self._peek()
        suffix = "end of file" if found.kind is TokenKind.EOF else repr(found.text)
        raise ParseError(f"{message}; found {suffix}", found.location)

    def _consume_statement_newline(self, message: str) -> None:
        if self._previous().kind == TokenKind.DEDENT or self._check(TokenKind.DEDENT) or self._check(TokenKind.EOF):
            self._match(TokenKind.NEWLINE)
        else:
            self._consume(TokenKind.NEWLINE, message)

    def _check(self, kind: TokenKind) -> bool:
        return self._peek().kind is kind

    def _advance(self) -> Token:
        token = self._peek()
        if token.kind is not TokenKind.EOF:
            self.current += 1
        return token

    def _peek(self) -> Token:
        return self.tokens[self.current]

    def _previous(self) -> Token:
        return self.tokens[self.current - 1]

    def _skip_newlines(self) -> None:
        while self._match(TokenKind.NEWLINE):
            pass


def parse_tokens(tokens: tuple[Token, ...], *, mode: SyntaxMode = SyntaxMode.V0_6) -> ast.Program:
    return Parser(tokens, mode).parse_program()


def parse(source: str, *, mode: SyntaxMode = SyntaxMode.V0_6) -> ast.Program:
    return parse_tokens(tokenize(source, mode=mode), mode=mode)
