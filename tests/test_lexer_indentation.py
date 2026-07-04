import pytest
import json
from bootstrap.s3.lexer import tokenize, SyntaxMode, TokenKind
from bootstrap.s3.diagnostics import DiagnosticCode, IndentationError

def get_kinds(source: str, mode: SyntaxMode = SyntaxMode.V0_6) -> list[TokenKind]:
    tokens = tokenize(source, mode=mode)
    return [t.kind for t in tokens]

def test_empty_file():
    assert get_kinds("") == [TokenKind.EOF]
    assert get_kinds("   \n  \n") == [TokenKind.EOF]

def test_only_comments():
    source = "# hello\n   # world"
    assert get_kinds(source) == [TokenKind.EOF]

def test_simple_function():
    source = "fn main():\n    return 0\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.FN, TokenKind.IDENTIFIER, TokenKind.LEFT_PAREN, TokenKind.RIGHT_PAREN,
        TokenKind.COLON, TokenKind.NEWLINE,
        TokenKind.INDENT, TokenKind.RETURN, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.DEDENT, TokenKind.EOF
    ]

def test_two_statements_same_block():
    source = "fn main():\n    mut x = 1\n    x = 2\n"
    assert get_kinds(source) == [
        TokenKind.FN, TokenKind.IDENTIFIER, TokenKind.LEFT_PAREN, TokenKind.RIGHT_PAREN, TokenKind.COLON, TokenKind.NEWLINE,
        TokenKind.INDENT, TokenKind.MUT, TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.DEDENT, TokenKind.EOF
    ]

def test_nested_block_and_multiple_dedent():
    source = "fn main():\n    if x:\n        return 1\n"
    kinds = get_kinds(source)
    assert kinds.count(TokenKind.INDENT) == 2
    assert kinds.count(TokenKind.DEDENT) == 2

    # verify dedent positions
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    dedents = [t for t in tokens if t.kind == TokenKind.DEDENT]
    assert len(dedents) == 2
    # both DEDENTs generated at EOF (pos = len(source))
    assert dedents[0].position == len(source)
    assert dedents[1].position == len(source)

def test_dedent_on_newline():
    source = "fn main():\n    if x:\n        return 1\n    return 0\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    dedent_idx = kinds.index(TokenKind.DEDENT)
    dedent_token = tokens[dedent_idx]
    
    # dedent should be before the second return
    assert tokens[dedent_idx + 1].kind == TokenKind.RETURN
    # It should have the position of the first non-whitespace character 'r'
    assert dedent_token.position == source.rfind("return 0")
    
def test_no_newline_at_eof():
    source = "fn main():\n    return 0"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    # NEWLINE should be emitted even without physical newline
    assert kinds[-3:] == [TokenKind.NEWLINE, TokenKind.DEDENT, TokenKind.EOF]

def test_inline_comment():
    source = "x = 1 # comment\ny = 2"
    kinds = get_kinds(source)
    assert kinds == [
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.EOF
    ]

def test_indented_comment_between_instructions():
    source = "fn main():\n    x = 1\n    # wait\n    y = 2\n"
    kinds = get_kinds(source)
    assert kinds == [
        TokenKind.FN, TokenKind.IDENTIFIER, TokenKind.LEFT_PAREN, TokenKind.RIGHT_PAREN, TokenKind.COLON, TokenKind.NEWLINE,
        TokenKind.INDENT, TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.DEDENT, TokenKind.EOF
    ]

def test_comment_does_not_alter_stack():
    source = "fn main():\n    x = 1\n  # weird indent\n    y = 2\n"
    kinds = get_kinds(source)
    # The weirdly indented comment should be ignored and not cause dedent/indent
    assert kinds.count(TokenKind.DEDENT) == 1 # only at EOF
    assert kinds[-2] == TokenKind.DEDENT

def test_v05_comments():
    # // works in 0.5
    assert [t.kind for t in tokenize("x = 1 // comment\n", mode=SyntaxMode.V0_5)] == [
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.EOF
    ]
    # // does NOT work in 0.6
    # in 0.6, / is not a valid token in the operator set currently except if we add it. 
    # Actually our lexer throws LexError for / if it's not a valid single token and not skipped.
    with pytest.raises(Exception) as excinfo:
        tokenize("x = 1 // comment\n", mode=SyntaxMode.V0_6)
    assert "invalid character" in str(excinfo.value)
    
def test_multiline_in_parens():
    source = "x = (\n    1 +\n    2\n)\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    # No INDENT/DEDENT inside parens, no NEWLINEs for physical newlines
    assert TokenKind.INDENT not in kinds
    assert TokenKind.DEDENT not in kinds
    # Only 1 NEWLINE at the very end after the closing paren
    assert kinds.count(TokenKind.NEWLINE) == 1
    assert kinds[-2] == TokenKind.NEWLINE

def test_multiline_in_brackets():
    source = "x = [\n    1,\n    2\n]\n"
    kinds = get_kinds(source)
    assert TokenKind.INDENT not in kinds
    assert TokenKind.DEDENT not in kinds
    assert kinds.count(TokenKind.NEWLINE) == 1

def test_crlf():
    source = "x = 1\r\ny = 2\r\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    assert kinds == [
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE,
        TokenKind.EOF
    ]
    assert tokens[3].position == 5 # position of \r

def test_tab_in_indentation():
    source = "fn main():\n\tx = 1\n"
    with pytest.raises(IndentationError) as exc:
        tokenize(source, mode=SyntaxMode.V0_6)
    assert exc.value.diagnostic_code == DiagnosticCode.LEX_TAB_INDENTATION
    
def test_mixed_indentation():
    source = "fn main():\n  \tx = 1\n"
    with pytest.raises(IndentationError) as exc:
        tokenize(source, mode=SyntaxMode.V0_6)
    assert exc.value.diagnostic_code == DiagnosticCode.LEX_MIXED_INDENTATION

def test_invalid_dedent():
    source = "fn main():\n    x = 1\n  y = 2\n"
    with pytest.raises(IndentationError) as exc:
        tokenize(source, mode=SyntaxMode.V0_6)
    assert exc.value.diagnostic_code == DiagnosticCode.LEX_INVALID_DEDENT
    assert exc.value.location.line == 3
    
def test_location_newline_indent_dedent():
    source = "fn main():\n    x = 1\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    
    newline_1 = tokens[5]
    assert newline_1.kind == TokenKind.NEWLINE
    assert newline_1.line == 1 # logical line 1
    assert newline_1.column == 11
    
    indent = tokens[6]
    assert indent.kind == TokenKind.INDENT
    assert indent.line == 2
    assert indent.column == 5
    
def test_non_ascii_in_comment():
    source = "# olá mundo\nx = 1\n"
    assert get_kinds(source) == [
        TokenKind.IDENTIFIER, TokenKind.EQUAL, TokenKind.INTEGER, TokenKind.NEWLINE, TokenKind.EOF
    ]

def test_eof_inside_delimiter():
    source = "x = (\n    1 +\n    2"
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    kinds = [t.kind for t in tokens]
    # NEWLINE and INDENT/DEDENT should NOT be emitted because the delimiter is still open.
    # It just reaches EOF. The parser will catch the missing ')'.
    assert TokenKind.NEWLINE not in kinds
    assert TokenKind.INDENT not in kinds
    assert TokenKind.DEDENT not in kinds
    assert kinds[-1] == TokenKind.EOF

def test_no_regression_v05():
    source = "fn main() { return 0; }\n"
    tokens = tokenize(source, mode=SyntaxMode.V0_5)
    kinds = [t.kind for t in tokens]
    assert TokenKind.NEWLINE not in kinds
    assert TokenKind.INDENT not in kinds
    assert TokenKind.DEDENT not in kinds

def test_structured_diagnostics():
    from bootstrap.s3.diagnostics import diagnostic_from_exception
    source = "fn main():\n\tx = 1\n"
    try:
        tokenize(source, mode=SyntaxMode.V0_6)
    except IndentationError as e:
        diag = diagnostic_from_exception(e, file="test.s3")
        assert diag.code == DiagnosticCode.LEX_TAB_INDENTATION
        assert diag.category == "syntax"
        
        json_str = diag.to_json()
        data = json.loads(json_str)
        assert data["code"] == "S3E_LEX_TAB_INDENTATION"
        assert data["source"]["line"] == 2
        assert data["source"]["column"] == 1
        assert data["source"]["offset"] == 11
