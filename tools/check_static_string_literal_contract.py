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
    "runtime_unsupported": "S3E_SEMANTIC_STRING_LITERAL_RUNTIME_UNSUPPORTED",
    "unterminated": "S3E_LEX_UNTERMINATED_STRING_LITERAL",
}

EXPECTED_CURRENT_STATE = {
    "ast": "StringLiteral",
    "backend": "not supported",
    "ir": "not supported",
    "lexer": "STRING_LITERAL",
    "parser": "front-end expression",
    "runtime": "not supported",
    "semantic": "runtime-unsupported diagnostic",
}

EXPECTED_STATIC_LITERAL_TABLE = {
    "deduplication": True,
    "id_scheme": "deterministic_sN",
    "scope": "front-end only",
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
    if behavior.get("storage") != "static_literal_table":
        raise ValueError("contract storage must be static_literal_table")
    if behavior.get("encoding") != "ascii_subset_utf8_compatible":
        raise ValueError("contract encoding must be ascii_subset_utf8_compatible")
    for key in ("concat", "indexing", "length", "mutable"):
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
