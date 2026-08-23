"""Bounded S3-authored canonical AST candidate with differential evidence."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import ast
from .differential import DifferentialHarness, DifferentialResult
from .lexer import SyntaxMode, TokenKind, tokenize
from .parser import parse
from .pipeline import run_source


M263_MAX_TOKENS = 64
M263_TOKEN_HASH_BASE = 32
M263_MODULUS = 301
_CANDIDATE_SOURCE = (
    Path(__file__).resolve().parents[2] / "selfhost" / "frontend" / "ast_candidate.s3"
).read_text(encoding="utf-8")


class ASTCandidateError(ValueError):
    """Raised when the bounded canonical AST candidate cannot certify input."""


@dataclass(frozen=True, slots=True)
class ASTCandidateEvidence:
    source: str
    reference_fingerprint: int
    candidate_fingerprint: int
    differential: DifferentialResult

    @property
    def match(self) -> bool:
        return self.differential.match


def _tokens(source: str):
    tokens = tokenize(source, mode=SyntaxMode.V0_6)
    if len(tokens) > M263_MAX_TOKENS:
        raise ASTCandidateError("source exceeds the M2.63 token bound")
    return tokens


def _symbol_hash(text: str) -> int:
    return sum(ord(char) for char in text) % M263_MODULUS


def _token_symbol_hash(token) -> int:
    text = token.text
    if token.kind is TokenKind.STRING_LITERAL:
        text = text[1:-1]
    return _symbol_hash(text)


def _canonical_values(source: str) -> tuple[int, int, int, int]:
    program = parse(source, mode=SyntaxMode.V0_6)
    if len(program.functions) != 1:
        raise ASTCandidateError("M2.63 candidate requires one function")
    function = program.functions[0]
    if function.parameters:
        raise ASTCandidateError("M2.63 candidate requires no parameters")
    if len(function.body.statements) != 1:
        raise ASTCandidateError("M2.63 candidate requires one statement")
    statement = function.body.statements[0]
    if not isinstance(statement, ast.ReturnStatement):
        raise ASTCandidateError("M2.63 candidate requires a return statement")
    if isinstance(statement.expression, ast.IntegerLiteral):
        literal_kind = TokenKind.INTEGER.value
        literal_text = str(statement.expression.value)
    elif isinstance(statement.expression, ast.FloatLiteral):
        literal_kind = TokenKind.FLOAT.value
        literal_text = str(statement.expression.value)
    elif isinstance(statement.expression, ast.StringLiteral):
        literal_kind = TokenKind.STRING_LITERAL.value
        literal_text = statement.expression.value
    else:
        raise ASTCandidateError("M2.63 candidate requires a primitive literal")
    type_kinds = {
        ast.TypeName.TRIT: TokenKind.TRIT.value,
        ast.TypeName.TRYTE: TokenKind.TRYTE.value,
        ast.TypeName.I64: TokenKind.I64.value,
        ast.TypeName.F64: TokenKind.F64.value,
    }
    try:
        return (
            _symbol_hash(function.name),
            type_kinds[function.return_type],
            _symbol_hash(literal_text),
            literal_kind,
        )
    except KeyError as error:
        raise ASTCandidateError("M2.63 candidate requires a primitive return type") from error


def _reference_fingerprint(source: str) -> int:
    name_hash, type_kind, literal_hash, literal_kind = _canonical_values(source)
    checksum = 0
    for kind, value in (
        (100, 1),
        (TokenKind.IDENTIFIER.value, name_hash),
        (type_kind, type_kind),
        (literal_kind, literal_hash),
    ):
        checksum = checksum * M263_TOKEN_HASH_BASE % M263_MODULUS
        checksum = (checksum + kind + value) % M263_MODULUS
    return checksum


def reference_ast_fingerprint(source: str) -> int:
    """Canonicalize the Python AST for the bounded grammar."""

    _tokens(source)
    return _reference_fingerprint(source)


def candidate_ast_fingerprint(source: str) -> int:
    """Run the S3 canonical AST candidate through the hosted emulator."""

    tokens = _tokens(source)
    kinds = [str(token.kind.value) for token in tokens]
    widths = [str(len(token.text)) for token in tokens]
    symbols = [str(_token_symbol_hash(token)) for token in tokens]
    kinds.extend(["0"] * (M263_MAX_TOKENS - len(kinds)))
    widths.extend(["0"] * (M263_MAX_TOKENS - len(widths)))
    symbols.extend(["0"] * (M263_MAX_TOKENS - len(symbols)))
    main_source = (
        _CANDIDATE_SOURCE
        + "\nfn main() -> tryte:\n"
        + f"    kinds: tryte[{M263_MAX_TOKENS}] = [{', '.join(kinds)}]\n"
        + f"    widths: tryte[{M263_MAX_TOKENS}] = [{', '.join(widths)}]\n"
        + f"    symbols: tryte[{M263_MAX_TOKENS}] = [{', '.join(symbols)}]\n"
        + f"    return canonical_ast_fingerprint(kinds, widths, symbols, {len(tokens)})\n"
    )
    try:
        result = run_source(main_source, optimization="O0", mode=SyntaxMode.V0_6)
    except Exception as error:
        raise ASTCandidateError("S3 canonical AST candidate execution failed") from error
    if result < 0:
        raise ASTCandidateError("S3 canonical AST candidate rejected the bounded grammar")
    return result


def run_ast_differential(
    source: str,
    *,
    provenance: dict[str, object] | None = None,
) -> ASTCandidateEvidence:
    """Compare canonical Python AST evidence with the S3 candidate."""

    if not isinstance(source, str):
        raise TypeError("source must be a string")
    if not source:
        raise ASTCandidateError("source must be non-empty")
    candidate = candidate_ast_fingerprint(source)
    reference = reference_ast_fingerprint(source)
    result = DifferentialHarness(max_bytes=4096).run(
        "m2.63-canonical-ast-candidate",
        {"source": source, "mode": "V0_6"},
        lambda value: {"fingerprint": reference_ast_fingerprint(value["source"])},
        lambda value: {"fingerprint": candidate_ast_fingerprint(value["source"])},
        provenance=provenance
        or {
            "component_id": "m2.63-canonical-ast-candidate",
            "source": "selfhost/frontend/ast_candidate.s3",
        },
    )
    return ASTCandidateEvidence(source, reference, candidate, result)
