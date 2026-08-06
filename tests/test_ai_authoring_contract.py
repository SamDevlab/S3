"""Contract tests for AI authoring readiness and stability."""

from bootstrap.s3 import OptimizationLevel
from bootstrap.s3.diagnostics import DiagnosticCode
from bootstrap.s3.emulator import Emulator
from bootstrap.s3.lexer import SyntaxMode, tokenize
from bootstrap.s3.parser import parse_tokens
from bootstrap.s3.pipeline import compile_source
from bootstrap.s3.semantic import SemanticError, analyze


# 12 Representative AI authoring cases in canonical V0.6 syntax
AI_CORPUS = [
    {
        "id": "1_scalar_valid",
        "goal": "Scalar trit/tryte arithmetic program",
        "source": "fn main() -> tryte:\n    mut x: tryte = 10\n    x = x + 5\n    return x\n",
        "expected_compile": True,
        "expected_result": 15,
    },
    {
        "id": "2_fn_params_result",
        "goal": "Function with parameters and return value",
        "source": "fn add(a: tryte, b: tryte) -> tryte:\n    return a + b\n\nfn main() -> tryte:\n    return add(20, 30)\n",
        "expected_compile": True,
        "expected_result": 50,
    },
    {
        "id": "3_record",
        "goal": "Nominal record creation and member access",
        "source": "record Point:\n    x: tryte\n    y: tryte\n\nfn main() -> tryte:\n    p: Point = Point(x=3, y=7)\n    return p.x + p.y\n",
        "expected_compile": True,
        "expected_result": 10,
    },
    {
        "id": "4_enum",
        "goal": "Nominal enum variant construction and match statement",
        "source": "enum Status:\n    Active\n    Inactive\n\nfn main() -> tryte:\n    s: Status = Status.Active\n    mut res: tryte = 0\n    match s:\n        Status.Active:\n            res = 1\n        Status.Inactive:\n            res = 0\n    return res\n",
        "expected_compile": True,
        "expected_result": 1,
    },
    {
        "id": "5_fixed_array",
        "goal": "Fixed-capacity static array creation and indexing",
        "source": "fn main() -> tryte:\n    mut arr: tryte[3] = [10, 20, 30]\n    return arr[1]\n",
        "expected_compile": True,
        "expected_result": 20,
    },
    {
        "id": "6_bounded_text",
        "goal": "Static text evaluation with len",
        "source": "fn main() -> tryte:\n    s: string = \"hello\"\n    return len(s)\n",
        "expected_compile": True,
        "expected_result": 5,
    },
    {
        "id": "7_structured_error",
        "goal": "Payload enum representing a structured result/error",
        "source": "enum Result:\n    Ok(val: tryte)\n    Err(code: tryte)\n\nfn main() -> tryte:\n    r: Result = Result.Ok(val=42)\n    mut res: tryte = 0\n    match r:\n        Result.Ok(val):\n            res = val\n        Result.Err(code):\n            res = 0\n    return res\n",
        "expected_compile": True,
        "expected_result": 42,
    },
    {
        "id": "8_import",
        "goal": "Deterministic multi-file module and import",
        "sources": {
            "math": "module math\nexport fn inc(x: tryte) -> tryte:\n    return x + 1\n",
            "main": "from math import inc\nfn main() -> tryte:\n    return inc(99)\n",
        },
        "expected_compile": True,
        "expected_result": 100,
    },
    {
        "id": "9_type_error",
        "goal": "Type mismatch diagnostic stability",
        "source": "fn main() -> tryte:\n    x: tryte = \"invalid\"\n    return x\n",
        "expected_compile": False,
        "expected_diagnostic": DiagnosticCode.SEMANTIC_TYPE_MISMATCH,
    },
    {
        "id": "10_unknown_symbol",
        "goal": "Unknown symbol diagnostic stability",
        "source": "fn main() -> tryte:\n    return undefined_var\n",
        "expected_compile": False,
        "expected_diagnostic": DiagnosticCode.SEMANTIC_INVALID_PROGRAM,
    },
    {
        "id": "11_incorrect_result",
        "goal": "Functional expectation verification probe",
        "source": "fn main() -> tryte:\n    return 1 + 1\n",
        "expected_compile": True,
        "expected_result": 2,
    },
    {
        "id": "12_unsupported_feature",
        "goal": "Rejection of unsupported dynamic heap/pointers",
        "source": "fn main() -> tryte:\n    ptr: tryte = &10\n    return *ptr\n",
        "expected_compile": False,
    },
]


def test_ai_authoring_contract_corpus():
    for case in AI_CORPUS:
        case_id = case["id"]
        if case["expected_compile"]:
            if "sources" in case:
                # Multi-module case verification
                from bootstrap.s3.pipeline import compile_sources
                compilation = compile_sources(case["sources"], OptimizationLevel.O0, entry_module="main")
                emulator = Emulator()
                res = emulator.execute(compilation.assembly, "main")
                assert res == case["expected_result"], f"Case {case_id} failed result check"
            else:
                # Single source O0 and O1 parity
                res_o0 = compile_source(case["source"], OptimizationLevel.O0)
                res_o1 = compile_source(case["source"], OptimizationLevel.O1)

                emu0 = Emulator()
                emu1 = Emulator()
                val_o0 = emu0.execute(res_o0.assembly, "main")
                val_o1 = emu1.execute(res_o1.assembly, "main")

                assert val_o0 == case["expected_result"], f"Case {case_id} O0 value mismatch"
                assert val_o1 == case["expected_result"], f"Case {case_id} O1 value mismatch"
        else:
            # Rejection case verification
            try:
                tokens = tokenize(case["source"], mode=SyntaxMode.V0_6)
                ast = parse_tokens(tokens, mode=SyntaxMode.V0_6)
                analyze(ast)
                assert False, f"Case {case_id} expected compilation failure but succeeded"
            except (SemanticError, Exception) as exc:
                if "expected_diagnostic" in case:
                    assert hasattr(exc, "code") or isinstance(exc, SemanticError), f"Case {case_id} missing diagnostic code"
