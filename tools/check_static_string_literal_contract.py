from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "tests" / "golden" / "static_string_literal_contract.json"

REQUIRED_KEYS = {
    "blocked_by",
    "contract_version",
    "current_state",
    "diagnostics",
    "feature",
    "first_supported_behavior",
    "static_literal_table",
}

EXPECTED_DIAGNOSTICS = {
    "invalid_argument_type": "S3E_SEMANTIC_INVALID_ARGUMENT_TYPE",
    "invalid_return_type": "S3E_SEMANTIC_INVALID_RETURN_TYPE",
    "type_mismatch": "S3E_SEMANTIC_TYPE_MISMATCH",
    "unterminated": "S3E_LEX_UNTERMINATED_STRING_LITERAL",
    "unsupported_operation": "S3E_SEMANTIC_UNSUPPORTED_STRING_OPERATION",
}

EXPECTED_CURRENT_STATE = {
    "ast": "StringLiteral",
    "assembly": "string type, .data table, TCONST_STR",
    "backend": "native .rodata labels for static strings",
    "emulator": "static string handles",
    "ir": "IRType.STRING with static_strings and CONST_STR",
    "lexer": "STRING_LITERAL",
    "parser": "string type and string literal expressions",
    "runtime": "static handles only",
    "semantic": "typed static string values with literal-only compile-time concat, length, and equality",
}

EXPECTED_STATIC_LITERAL_TABLE = {
    "deduplication": True,
    "id_scheme": "deterministic_sN",
    "scope": "front-end, IR, Assembly, emulator, native",
}


def _canonical(data: object) -> str:
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def _load_contract() -> tuple[dict[str, object], str]:
    text = CONTRACT_PATH.read_text(encoding="utf-8")
    data = json.loads(text)
    if not isinstance(data, dict):
        raise ValueError("contract root must be an object")
    return data, text


def _validate_contract(data: dict[str, object], text: str) -> None:
    missing = REQUIRED_KEYS - data.keys()
    if missing:
        rendered = ", ".join(sorted(missing))
        raise ValueError(f"contract missing required key(s): {rendered}")

    if text != _canonical(data):
        raise ValueError("contract JSON is not canonical")

    diagnostics = data["diagnostics"]
    if diagnostics != EXPECTED_DIAGNOSTICS:
        raise ValueError("contract diagnostics do not match reserved string diagnostics")

    current_state = data["current_state"]
    if current_state != EXPECTED_CURRENT_STATE:
        raise ValueError("contract current_state does not match front-end string state")

    static_literal_table = data["static_literal_table"]
    if static_literal_table != EXPECTED_STATIC_LITERAL_TABLE:
        raise ValueError("contract static_literal_table does not match front-end table")

    behavior = data["first_supported_behavior"]
    if not isinstance(behavior, dict):
        raise ValueError("contract first_supported_behavior must be an object")
    if behavior.get("storage") != "static_string_table":
        raise ValueError("contract storage must be static_string_table")
    if behavior.get("encoding") != "utf8_static_text":
        raise ValueError("contract encoding must be utf8_static_text")
    if behavior.get("binding_assignment") is not True:
        raise ValueError("contract binding_assignment must be true")
    if behavior.get("mutable_binding") is not True:
        raise ValueError("contract mutable_binding must be true")
    if behavior.get("concat") != "compile_time_literal_only":
        raise ValueError("contract concat must be compile_time_literal_only")
    if behavior.get("length") != "compile_time_static_text":
        raise ValueError("contract length must be compile_time_static_text")
    if behavior.get("equality") != "compile_time_static_text":
        raise ValueError("contract equality must be compile_time_static_text")
    for key in ("indexing", "string_byte_mutation"):
        if behavior.get(key) is not False:
            raise ValueError(f"contract {key} must be false")


def main() -> int:
    try:
        data, text = _load_contract()
        _validate_contract(data, text)
    except (OSError, json.JSONDecodeError, ValueError) as error:
        print(f"static string literal contract invalid: {error}")
        return 1

    print("static string literal contract: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
