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
    "ast": "StringLiteral, IndexExpression, SliceExpression",
    "assembly": "string type, .data table, TCONST_STR",
    "backend": "native .rodata labels for static strings",
    "emulator": "static string handles",
    "ir": "IRType.STRING with static_strings and CONST_STR",
    "lexer": "STRING_LITERAL",
    "parser": "string type, string literal expressions, indexing, and slicing",
    "runtime": "static handles only",
    "semantic": "typed static string values plus immutable scalar constants, constant arithmetic, constant comparisons, static text indexing, slicing, and queries",
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
    if behavior.get("constant_propagation") != "immutable_static_text_bindings_only":
        raise ValueError(
            "contract constant_propagation must be immutable_static_text_bindings_only"
        )
    if behavior.get("numeric_constant_propagation") != "immutable_tryte_bindings":
        raise ValueError(
            "contract numeric_constant_propagation must be immutable_tryte_bindings"
        )
    if behavior.get("trit_constant_propagation") != "immutable_trit_bindings":
        raise ValueError(
            "contract trit_constant_propagation must be immutable_trit_bindings"
        )
    if behavior.get("constant_arithmetic") != "supported_existing_operators":
        raise ValueError(
            "contract constant_arithmetic must be supported_existing_operators"
        )
    if behavior.get("constant_comparisons") != "supported_existing_operators":
        raise ValueError(
            "contract constant_comparisons must be supported_existing_operators"
        )
    if behavior.get("len_result_propagation") is not True:
        raise ValueError("contract len_result_propagation must be true")
    if behavior.get("find_result_propagation") is not True:
        raise ValueError("contract find_result_propagation must be true")
    if behavior.get("static_text_index_bounds") != "compile_time_tryte_expression":
        raise ValueError(
            "contract static_text_index_bounds must be compile_time_tryte_expression"
        )
    if behavior.get("static_text_slice_bounds") != "compile_time_tryte_expression":
        raise ValueError(
            "contract static_text_slice_bounds must be compile_time_tryte_expression"
        )
    if behavior.get("length") != "compile_time_static_text":
        raise ValueError("contract length must be compile_time_static_text")
    if behavior.get("equality") != "compile_time_static_text":
        raise ValueError("contract equality must be compile_time_static_text")
    if behavior.get("indexing") != "compile_time_static_text_with_literal_index":
        raise ValueError(
            "contract indexing must be compile_time_static_text_with_literal_index"
        )
    if behavior.get("slicing") != "compile_time_static_text_literal_bounds":
        raise ValueError(
            "contract slicing must be compile_time_static_text_literal_bounds"
        )
    for key in ("contains", "starts_with", "ends_with", "find"):
        if behavior.get(key) != "compile_time_static_text":
            raise ValueError(f"contract {key} must be compile_time_static_text")
    if behavior.get("string_byte_mutation") is not False:
        raise ValueError("contract string_byte_mutation must be false")


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
