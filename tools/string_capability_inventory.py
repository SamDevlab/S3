from __future__ import annotations


def main() -> int:
    print("S3 string capability inventory")
    print()
    print("current:")
    print("  lexer: STRING_LITERAL reserved")
    print("  parser: static string literal expression")
    print("  semantic: runtime-unsupported diagnostic")
    print("  runtime: not supported")
    print("  ir: not supported")
    print("  backend: not supported")
    print()
    print("diagnostics:")
    print("  S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED")
    print("  S3E_LEX_UNTERMINATED_STRING_LITERAL")
    print()
    print("self-hosting status:")
    print("  required for Assembly renderer subset")
    print("  blocked by runtime representation and deterministic formatting helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
