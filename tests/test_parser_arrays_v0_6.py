import pytest

from bootstrap.s3 import ast
from bootstrap.s3.diagnostics import ParseError
from bootstrap.s3.lexer import SyntaxMode
from bootstrap.s3.parser import parse
from bootstrap.s3.semantic import analyze
from bootstrap.s3.lowering import lower
from bootstrap.s3.verifier import verify_ir
from bootstrap.s3.codegen import generate_assembly
from bootstrap.s3.emulator import Emulator

def remove_locations(d):
    if isinstance(d, dict):
        return {k: remove_locations(v) for k, v in d.items() if k != "location"}
    if isinstance(d, tuple):
        return tuple(remove_locations(v) for v in d)
    if isinstance(d, list):
        return list(remove_locations(v) for v in d)
    return d

def test_ast_equivalence_immutable_declaration():
    source_v0_5 = "fn main() -> tryte {\n    tryte[3] values = [1, 2, 3];\n    return values[1];\n}"
    source_v0_6 = "fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    return values[1]\n"
    
    ast_v0_5 = ast.to_dict(parse(source_v0_5, mode=SyntaxMode.V0_5))
    ast_v0_6 = ast.to_dict(parse(source_v0_6, mode=SyntaxMode.V0_6))
    
    assert remove_locations(ast_v0_5) == remove_locations(ast_v0_6)

def test_ast_equivalence_mutable_declaration_and_assignment():
    source_v0_5 = "fn main() -> tryte {\n    mut tryte[3] values = [1, 2, 3];\n    values[1] = 6;\n    return values[1];\n}"
    source_v0_6 = "fn main() -> tryte:\n    mut values: tryte[3] = [1, 2, 3]\n    values[1] = 6\n    return values[1]\n"
    
    ast_v0_5 = ast.to_dict(parse(source_v0_5, mode=SyntaxMode.V0_5))
    ast_v0_6 = ast.to_dict(parse(source_v0_6, mode=SyntaxMode.V0_6))
    
    assert remove_locations(ast_v0_5) == remove_locations(ast_v0_6)

def test_ast_equivalence_trit_array():
    source_v0_5 = "fn main() -> tryte {\n    trit[2] bits = [0, 1];\n    return 0;\n}"
    source_v0_6 = "fn main() -> tryte:\n    bits: trit[2] = [0, 1]\n    return 0\n"
    
    ast_v0_5 = ast.to_dict(parse(source_v0_5, mode=SyntaxMode.V0_5))
    ast_v0_6 = ast.to_dict(parse(source_v0_6, mode=SyntaxMode.V0_6))
    
    assert remove_locations(ast_v0_5) == remove_locations(ast_v0_6)

def test_multiline_literal():
    source = """\
fn main() -> tryte:
    values: tryte[3] = [
        1,
        2,
        3
    ]
    return values[
        1
    ]
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    assert len(program.functions) == 1
    func = program.functions[0]
    assert len(func.body.statements) == 2

def test_literal_with_expressions():
    source = """\
fn get_one() -> tryte:
    return 1

fn main() -> tryte:
    values: tryte[3] = [0 + 1, get_one(), -1]
    return values[1]
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    assert len(program.functions) == 2

def test_array_in_match():
    source = """\
fn main() -> tryte:
    mut values: tryte[3] = [1, 2, 3]

    match values[0] <=> 0:
        -1:
            values[1] = -1
        0:
            values[1] = 0
        1:
            values[1] = 1

    return values[1]
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    analyzed = analyze(program)
    ir = lower(program, analyzed)
    verify_ir(ir)
    asm = generate_assembly(ir)
    assert Emulator().execute(asm) == 1

def test_recursive_frames_arrays_adversarial():
    source = """\
fn recursive(count: tryte) -> tryte:
    mut local_array: tryte[1] = [count]
    match count <=> 0:
        -1:
            return -1
        0:
            return local_array[0]
        1:
            mut temp: tryte[1] = [recursive(count - 1)]
            return temp[0] + local_array[0]

fn main() -> tryte:
    return recursive(3)
"""
    program = parse(source, mode=SyntaxMode.V0_6)
    analyzed = analyze(program)
    ir = lower(program, analyzed)
    verify_ir(ir)
    asm = generate_assembly(ir)
    # The innermost calls will assign 0 to their local_array, but if frames are isolated, 
    # the outer frames will still retain their original `count` in `local_array[0]`.
    # count=3 -> recursive(2) + 3 = 6
    # recursive(2) -> recursive(1) + 2 = 3
    # recursive(1) -> recursive(0) + 1 = 1
    # recursive(0) -> 0
    assert Emulator().execute(asm) == 6

def test_invalid_syntax_v0_6_rejected():
    source_old_style_decl = "fn main() -> tryte:\n    tryte[3] values = [1, 2, 3]\n    return 0\n"
    with pytest.raises(ParseError) as exc_info:
        parse(source_old_style_decl, mode=SyntaxMode.V0_6)
    assert "expected variable declaration, 'return', 'while', 'break', 'continue', or assignment" in str(exc_info.value)
    
    source_old_style_mut = "fn main() -> tryte:\n    mut tryte[3] values = [1, 2, 3]\n    return 0\n"
    with pytest.raises(ParseError) as exc_info:
        parse(source_old_style_mut, mode=SyntaxMode.V0_6)
    assert "expected variable name; found 'tryte'" in str(exc_info.value)

def test_invalid_syntax_v0_6_rejected_parameterized():
    invalid_cases = [
        ("fn main() -> tryte:\n    values: tryte[] = []\n    return 0\n", "expected static array length; found ']'"),
        ("fn main() -> tryte:\n    values: tryte 3 = [1, 2, 3]\n    return 0\n", "expected '=' after variable type"),
        ("fn main() -> tryte:\n    values: tryte[3] = 1, 2, 3]\n    return 0\n", "expected newline after declaration; found ','"),
        ("fn main() -> tryte:\n    values: tryte[3] = [1 2 3]\n    return 0\n", "expected ']' after array literal"),
        ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3,]\n    return 0\n", "expected array element after ','"),
        ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3\n    return 0\n", "expected ']' after array literal"),
        ("fn main() -> tryte:\n    return values[0:2]\n", "expected ']' after index"),
        ("fn main() -> tryte:\n    values[0] 1\n    return 0\n", "expected '=' after assignment target"),
        ("fn main() -> tryte:\n    values: tryte[3]\n    return 0\n", "expected '=' after variable type"),
        ("fn main() -> tryte:\n    values[0][1] = 2\n    return 0\n", "expected '=' after assignment target"),
        ("fn main() -> tryte:\n    return values[0][1]\n", "expected newline after return value; found '['"),
    ]
    for src, expected_msg in invalid_cases:
        with pytest.raises(ParseError) as exc:
            parse(src, mode=SyntaxMode.V0_6)
        assert expected_msg in str(exc.value), f"Expected '{expected_msg}' in '{exc.value}' for:\n{src}"

def test_semantic_failures_preserved_parameterized():
    # Semantic verification
    from bootstrap.s3.diagnostics import SemanticError
    
    semantic_cases = [
        # Immutable write
        ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    values[0] = 6\n    return 0\n", "cannot assign to immutable variable"),
        # Length mismatch
        ("fn main() -> tryte:\n    values: tryte[2] = [1, 2, 3]\n    return 0\n", "array initializer has 3 element(s); expected 2"),
        # Constant negative bounds
        ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    return values[-1]\n", "constant index -1 is outside array 'values' bounds [0, 3)"),
        # Constant out of bounds
        ("fn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    return values[3]\n", "constant index 3 is outside array 'values' bounds [0, 3)"),
        # Writing to non-array
        ("fn main() -> tryte:\n    mut values: tryte = 1\n    values[0] = 2\n    return 0\n", "variable 'values' is not an array"),
        # Reading non-array
        ("fn main() -> tryte:\n    values: tryte = 1\n    return values[0]\n", "variable 'values' is not an array"),
        # Type mismatch in literal
        ("fn main() -> tryte:\n    values: trit[1] = [10]\n    return 0\n", "literal 10 is outside trit range [-1, 1]"),
    ]
    
    for src, error_snippet in semantic_cases:
        program = parse(src, mode=SyntaxMode.V0_6)
        with pytest.raises(SemanticError) as exc:
            analyze(program)
        assert error_snippet in str(exc.value)

def test_dynamic_bounds_in_emulator():
    from bootstrap.s3.emulator import EmulatorError
    src = "fn get_index() -> tryte:\n    return 5\nfn main() -> tryte:\n    values: tryte[3] = [1, 2, 3]\n    return values[get_index()]\n"
    program = parse(src, mode=SyntaxMode.V0_6)
    a = analyze(program)
    ir = lower(program, a)
    verify_ir(ir)
    asm = generate_assembly(ir)
    with pytest.raises(EmulatorError) as exc:
        Emulator().execute(asm)
    assert "memory m0 index 5 is outside [0, 3)" in str(exc.value)
