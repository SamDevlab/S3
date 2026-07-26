from __future__ import annotations


def main() -> int:
    print("S3 string capability inventory")
    print()
    print("current:")
    print("  lexer: STRING_LITERAL reserved")
    print("  parser: string type and static string literal expression")
    print("  semantic: typed static string values with literal-only compile-time concat")
    print("  ir: IRType.STRING, static_strings, CONST_STR")
    print("  assembly: string type, .data, TCONST_STR")
    print("  hosted runtime: static string handles")
    print("  native backend: private .rodata labels")
    print()
    print("diagnostics:")
    print("  S3E_SEMANTIC_TYPE_MISMATCH")
    print("  S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION")
    print("  S3E_SEMANTIC_INVALID_RETURN_TYPE")
    print("  S3E_SEMANTIC_INVALID_ARGUMENT_TYPE")
    print("  S3E_LEX_UNTERMINATED_STRING_LITERAL")
    print()
    print("self-hosting status:")
    print("  required for Assembly renderer subset")
    print("  literal-only static text concat no longer blocks fixed token composition")
    print("  strings no longer block 0.54 static renderer data paths")
    print("  still blocked by records/enums and deterministic formatting helpers")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
