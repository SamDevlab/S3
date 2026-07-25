"""Recursive-descent parser for the first S3 grammar."""

from __future__ import annotations

from collections.abc import Callable

from . import ast
from .diagnostics import DiagnosticCode, ParseError
from .lexer import SyntaxMode, Token, TokenKind, tokenize


class Parser:
    def __init__(self, tokens: tuple[Token, ...], mode: SyntaxMode = SyntaxMode.V0_6):
        self.tokens = tokens
        self.current = 0
        self.mode = mode

    def parse_program(self) -> ast.Program:
        functions: list[ast.FunctionDeclaration] = []
        location = self._peek().location
        while not self._check(TokenKind.EOF):
            functions.append(self._parse_function())
        if not functions:
            raise ParseError("expected at least one function", self._peek().location)
        return ast.Program(tuple(functions), location)

    def _parse_function(self) -> ast.FunctionDeclaration:
        start = self._consume(TokenKind.FN, "expected 'fn'")
        name = self._consume(TokenKind.IDENTIFIER, "expected function name")
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

        signature = ast.FunctionSignature(
            name.text,
            tuple(parameters),
            return_type,
            name.location,
        )
        return ast.FunctionDeclaration(signature, body, start.location)

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
        if self._match(TokenKind.TRIT):
            result: ast.DeclaredType = ast.TypeName.TRIT
        elif self._match(TokenKind.TRYTE):
            result = ast.TypeName.TRYTE
        else:
            raise ParseError("expected type 'trit' or 'tryte'", self._peek().location)
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
            if self._check(TokenKind.MUT):
                return self._parse_variable_declaration_v0_6()
            if self._check(TokenKind.IDENTIFIER):
                next_token = self.tokens[self.current + 1] if self.current + 1 < len(self.tokens) else None
                if next_token and next_token.kind is TokenKind.COLON:
                    return self._parse_variable_declaration_v0_6()
                return self._parse_assignment_v0_6()
            raise ParseError("expected variable declaration, 'return', 'while', 'for', 'break', 'continue', or assignment", self._peek().location)

        if (
            self._check(TokenKind.MUT)
            or self._check(TokenKind.TRIT)
            or self._check(TokenKind.TRYTE)
        ):
            return self._parse_variable_declaration()
        if self._match(TokenKind.RETURN):
            return self._parse_return(self._previous())
        if self._match(TokenKind.SWITCH):
            return self._parse_switch(self._previous())
        if self._check(TokenKind.IDENTIFIER):
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
        name = self._consume(TokenKind.IDENTIFIER, "expected assignment target")
        target: ast.AssignmentTarget
        if self._match(TokenKind.LEFT_BRACKET):
            index = self._parse_expression()
            self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
            target = ast.IndexTarget(name.text, index, name.location)
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
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            cases.append(self._parse_ternary_case_v0_6())

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
        first_expr = self._parse_expression()
        if self._match(TokenKind.COMMA):
            start_expression = first_expr
            end_expression = self._parse_expression()
        else:
            start_expression = ast.IntegerLiteral(0, first_expr.location)
            end_expression = first_expr
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
            body,
            start.location,
        )

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
        negative = self._match(TokenKind.MINUS)
        start = self._previous() if negative else self._peek()

        if not self._check(TokenKind.INTEGER):
            raise ParseError("expected integer case label", self._peek().location, diagnostic_category=None, diagnostic_code=DiagnosticCode.PARSE_INVALID_MATCH_ARM)

        integer = self._advance()
        value = int(integer.text)
        if negative:
            value = -value
        self._consume(TokenKind.COLON, "expected ':' after case label")
        self._consume(TokenKind.NEWLINE, "expected newline after ':'")
        self._consume(TokenKind.INDENT, "expected indented block")
        body = self._parse_block_v0_6()
        return ast.TernaryCase(value, body, start.location)

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
            target = ast.IndexTarget(name.text, index, name.location)
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
            self._parse_unary,
            {
                TokenKind.PLUS: ast.BinaryOperator.ADD,
                TokenKind.MINUS: ast.BinaryOperator.SUBTRACT,
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
        return self._parse_primary()

    def _parse_primary(self) -> ast.Expression:
        if self.mode == SyntaxMode.V0_6 and self._match(TokenKind.MATCH):
            return self._parse_match_expression_v0_6(self._previous())
        if self.mode == SyntaxMode.V0_6 and self._match(TokenKind.LEN):
            return self._parse_len_v0_6(self._previous())
        if self._match(TokenKind.INTEGER):
            token = self._previous()
            return ast.IntegerLiteral(int(token.text), token.location)
        if self._match(TokenKind.STRING_LITERAL):
            token = self._previous()
            return ast.StringLiteral(token.text[1:-1], token.location)
        if self._match(TokenKind.IDENTIFIER):
            token = self._previous()
            if self._match(TokenKind.LEFT_PAREN):
                return self._finish_call(token)
            if self._match(TokenKind.LEFT_BRACKET):
                index = self._parse_expression()
                self._consume(TokenKind.RIGHT_BRACKET, "expected ']' after index")
                return ast.IndexExpression(token.text, index, token.location)
            return ast.Identifier(token.text, token.location)
        if self._match(TokenKind.LEFT_PAREN):
            expression = self._parse_expression()
            self._consume(TokenKind.RIGHT_PAREN, "expected ')' after expression")
            return expression
        raise ParseError("expected expression", self._peek().location)

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
        while not self._check(TokenKind.DEDENT) and not self._check(TokenKind.EOF):
            cases.append(self._parse_match_expression_case_v0_6())
        if not cases:
            raise ParseError(
                "expected at least one match arm",
                self._peek().location,
            )
        self._consume(TokenKind.DEDENT, "expected dedent after match arms")
        return ast.MatchExpression(selector, tuple(cases), start.location)

    def _parse_match_expression_case_v0_6(self) -> ast.MatchExpressionCase:
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
        expr = self._parse_expression()
        self._consume_statement_newline("expected newline after match arm expression")
        return ast.MatchExpressionCase(value, expr, start.location)

    def _finish_call(self, function: Token) -> ast.CallExpression:
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
            function.text,
            tuple(arguments),
            function.location,
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


def parse_tokens(tokens: tuple[Token, ...], *, mode: SyntaxMode = SyntaxMode.V0_6) -> ast.Program:
    return Parser(tokens, mode).parse_program()


def parse(source: str, *, mode: SyntaxMode = SyntaxMode.V0_6) -> ast.Program:
    return parse_tokens(tokenize(source, mode=mode), mode=mode)
