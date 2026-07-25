# S3 Source Syntax Specification (Milestone 0.6)

## Status

V0.6 é a source syntax atual e padrão do S3. A sintaxe 0.5 permanece disponível estritamente como compatibilidade legada/deprecated, sem autodetecção ou fallback. As versões de sintaxe fonte, IR JSON e S3 Assembly são independentes.

## 1. Objective
This document outlines the indentation-based source syntax for S3, standard in Milestone 0.6 and later. The primary goal is to adhere to the "Less is more" principle by providing a low-ceremony, Python-like ergonomic syntax while retaining the explicit, predictable, and low-level characteristics of a systems programming language.

## 2. Syntactic Audit & Comparison

| Concept | Current Syntax (0.5) | Proposed Syntax (0.6) | Semantic Change | Implementation Impact |
| --- | --- | --- | --- | --- |
| **Function** | `fn f() { ... }` | `fn f():\n    ...` | None | Lexer/Parser blocks |
| **Parameters** | `(a: trit, b: tryte)` | `(a: trit, b: tryte)` | None | None |
| **Return** | `-> tryte { ... }` | `-> tryte:\n    ...` | None | Parser blocks |
| **Immutable Binding** | `tryte v = 5;` | `v: tryte = 5` | None | Parser semicolon |
| **Mutable Binding** | `mut tryte v = 5;` | `mut v: tryte = 5` | None | Parser semicolon |
| **Assignment** | `v = 6;` | `v = 6` | None | Parser semicolon |
| **Array** | `tryte[3] arr = [1, 2, 3];` | `arr: tryte[3] = [1, 2, 3]` | None | Parser semicolon |
| **Indexing** | `arr[0]` | `arr[0]` | None | None |
| **Call** | `f(a);` | `f(a)` | None | Parser semicolon |
| **Recursion** | `f(a);` | `f(a)` | None | Parser semicolon |
| **Ternary Compare** | `<=>` | `<=>` | None | None |
| **Control Flow** | `switch (a <=> b) { ... }` | `match a <=> b:\n    ...` | None | Lexer (match keyword), Parser |
| **Loops** | N/A | `while c:\n    ...` | None | Parser |
| **Comments** | `// comment` | `# comment` | None | None |
| **Blocks** | `{ ... }` | `:\n    ...` | None | Lexer (INDENT/DEDENT) |
| **Statement End** | `;` | `NEWLINE` | None | Lexer (NEWLINE), Parser |
| **Multiline Expr** | Allowed anywhere | Inside `()`, `[]` only | None | Lexer/Parser |

## 3. Preserved Semantic Contracts
This syntax simplification strictly alters the surface of the language. The following contracts remain **unchanged**:
- Balanced ternary logic (`trit`, `tryte`, bounds, overflows).
- The `<=>` operator returns a `trit`.
- `~` as inversion, `&` as tritwise minimum, `|` as tritwise maximum.
- Subtraction is lowered to `ADD + INVERT`.
- `SUBTRACT`, `TSUB`, `PHI` remain absent.
- Explicit mutability is strictly enforced.
- Static arrays and per-frame local memory limits.
- IR, S3 Assembly (0.5.0), ABI, and runtime ELF generation.
- Backend Linux x86-64 logic and diagnostic schemas.

## 4. Grammar Rules

### 4.1. Local Declarations
To maintain static typing without ambiguity and enforce "menos é mais":
- **Rule:** `name: type = expression` declares an immutable binding.
- **Rule:** `mut name: type = expression` declares a mutable binding.
- **Rule:** `name = expression` is exclusively an assignment.
- **Rule:** Assignment can only target a previously declared mutable binding.
- **Rule:** Parameters and return types must always have explicit types.
- **Rule:** Arrays always declare type and length.
- **Rule:** No local inference exists in this first version. No global or interprocedural inference.
- **Rule:** No `let`, no `var`, no `:=`.
- **Rule:** `mut name = expression` without type is not allowed.

### 4.2. Blocks and Indentation
- **Rule:** Blocks begin with `:` followed by a logical `NEWLINE` and an `INDENT`.
- **Rule:** Blocks end with a logical `DEDENT`.
- **Rule:** Recommended indentation is 4 spaces. Mixing tabs and spaces will trigger a diagnostic error.
- **Rule:** Empty lines and lines containing only comments are ignored by the indentation logic.
- **Rule:** End-of-file implicitly yields pending `DEDENT` tokens.

### 4.3. Ternary Control Flow
- **Rule:** The `switch` keyword is replaced by `match`.
- **Why:** "Switch" implies C-like fallthrough behavior, which S3 does not have. "Match" clearly conveys mapping an expression strictly to exactly one of `-1`, `0`, or `1`. There is no permanent support for both.

### 4.4. Compound Operators
- **Rule:** Compound operators (e.g., `+=`, `-=`) do not exist.
- **Why:** Keeps the implementation simple and enforces explicit operations (`a = a + 1`), which makes overflow boundaries and ternary limits mathematically visible.

### 4.5. Multiline Expressions
- **Rule:** Line breaks are freely allowed inside matching `( )` and `[ ]`. Outside of these delimiters, a newline produces a logical `NEWLINE` token which terminates the statement.

### 4.6. Ternary Literals
- **Rule:** The explicit type annotation in the declaration and the expression context determine if a literal represents a trit or tryte.
- **Example:** `sign: trit = 1` and `value: tryte = 1`.
- **Rule:** There is no autonomous inference rule for unannotated local literals. Values outside -1, 0, and 1 remain invalid for trit.

### 4.7. Loops
- **Rule:** The `while` keyword introduces a loop.
- **Rule:** The loop condition must be a `trit` expression.
- **Rule:** A condition of `-1` executes the loop body.
- **Rule:** A condition of `0` terminates the loop.
- **Rule:** A condition of `1` terminates the loop.
- **Rule:** The `break` statement immediately terminates the loop and transfers control to the continuation after the innermost `while` loop.
- **Rule:** The `continue` statement immediately terminates the current iteration and transfers control to the re-evaluation of the condition of the innermost `while` loop.
- **Rule:** `break` and `continue` do not take labels or expressions.

### 4.8. Relational Operators
- **Rule:** Binary relational operators `==`, `!=`, `<`, `<=`, `>`, `>=` compare two operands of the same scalar type (`tryte` with `tryte`, or `trit` with `trit`).
- **Rule:** Relational expressions evaluate to a `trit` (`-1` for true, `0` for false).
- **Rule:** When evaluated as a `while` condition, `-1` (true) executes the loop body, while `0` (false) exits the loop.

### 4.9. Match Expression
- **Rule:** `match selector:` can be used as an expression.
- **Rule:** The selector must evaluate to a `trit`.
- **Rule:** Exactly three arms (`-1`, `0`, `1`) must be provided inside an indented block.
- **Rule:** Each arm contains a single result expression. All arm expressions must evaluate to the same scalar type (`trit` or `tryte`).
- **Rule:** Only the selected arm expression is evaluated at runtime (lazy evaluation of unselected arms).

### 4.10. For Loop Statement
- **Rule:** `for var: tryte in range(start, end):` iterates over the half-open range `[start, end)`.
- **Rule:** `start` and `end` bounds must evaluate to `tryte`.
- **Rule:** The loop variable `var` is bound for the scope of the loop body and is immutable (`is_mutable=False`).
- **Rule:** `break` and `continue` statements inside the loop body transfer control to the loop exit or loop step, respectively.

### 4.11. Static Array Len Expression
- **Rule:** `len(array_expression)` returns the compile-time element count of a static array.
- **Rule:** The argument must evaluate to a static array type (`tryte[N]` or `trit[N]`). Scalar values, indexed elements, and non-array expressions are rejected with a semantic error.
- **Rule:** `len` returns a scalar of type `tryte`.
- **Rule:** Evaluation is purely static during compilation; zero runtime memory instructions or call instructions are emitted.

## 5. Normative Examples

### Example 1: Simple Return
```s3
fn main() -> tryte:
    return 6
```

### Example 2: Addition
```s3
fn add(a: tryte, b: tryte) -> tryte:
    return a + b
```

### Example 3: Mutable Value and Assignment
```s3
fn main() -> tryte:
    mut counter: tryte = 0
    counter = counter + 1
    return counter
```

### Example 4: Ternary Match
```s3
fn sign(value: tryte) -> trit:
    match value <=> 0:
        -1:
            return -1
        0:
            return 0
        1:
            return 1
```

### Example 5: Function Call
```s3
fn main() -> trit:
    return sign(-20)
```

### Example 6: Nested Calls
```s3
fn main() -> trit:
    return sign(add(10, -30))
```

### Example 7: Recursion
```s3
fn sum_to(n: tryte) -> tryte:
    match n <=> 0:
        -1:
            return 0
        0:
            return 0
        1:
            return n + sum_to(n - 1)
```

### Example 8: Static Array
```s3
fn main() -> tryte:
    values: tryte[3] = [1, 2, 3]
    mut total: tryte = 0
    total = total + values[0]
    total = total + values[1]
    total = total + values[2]
    return total
```

### Example 9: Mutable Array
```s3
fn main() -> tryte:
    mut buffer: tryte[3] = [0, 0, 0]
    buffer[0] = 10
    buffer[1] = 20
    return buffer[1]
```

### Example 10: Recursive Memory Isolation
```s3
fn recurse(depth: tryte) -> tryte:
    local_val: tryte = depth
    match depth <=> 0:
        -1:
            return local_val
        0:
            return local_val
        1:
            return recurse(depth - 1)
```

### Example 11: Multiline Expression
```s3
fn main() -> tryte:
    values: tryte[3] = [
        1,
        2,
        3
    ]
    return values[0]
```

### Example 12: Comment
```s3
fn main() -> tryte:
    # This is a valid comment
    return 0
```

### Example 13: Indentation Error
```s3
fn main() -> tryte:
  return 0
    return 1 # S3E_LEX_INVALID_INDENT
```

### Example 14: Mutability Error
```s3
fn main() -> tryte:
    value: tryte = 0
    value = 1 # Semantic error: assignment to immutable
    return value
```

### Example 15: Type Error
```s3
fn expect_trit(val: trit) -> trit:
    return val

fn main() -> tryte:
    value: tryte = 5
    expect_trit(value) # Semantic error: type mismatch (expected trit, got tryte)
    return 0
```

### Example 16: While Loop
```s3
fn main() -> tryte:
    mut index: tryte = 0

    while index <=> 5:
        index = index + 1

    return index
```

## 6. Migration Strategy
S3 is currently experimental. The older 0.5 syntax is deprecated.
- **Action:** Direct syntax replacement in the compiler.
- **Errors:** If the compiler encounters `{`, `}`, or `;`, it will emit a clear diagnostic explaining that the syntax has evolved to 0.6 and these characters are obsolete.

## 7. Versioning
- The file extension remains `.s3`.
- The new syntax is considered the standard for Milestone 0.6.
- The IR JSON schema and S3 Assembly schema will remain `0.5.0` as they are semantically unaffected by this surface change.

## 8. Diagnostics
New diagnostics integrate with the existing structured schema:
- `S3E_LEX_UNEXPECTED_INDENT`: Emitted when an indentation increases without a preceding `:`.
- `S3E_LEX_INVALID_DEDENT`: Emitted when dedent does not match any previous indentation level.
- `S3E_LEX_TAB_IN_INDENT`: Emitted when a tab character is used for indentation.
- `S3E_PARSE_EXPECTED_BLOCK`: Emitted when a `:` is missing before a block.
- `S3E_PARSE_EXPECTED_STATEMENT`: Emitted on an empty block.
- `S3E_PARSE_OBSOLETE_BRACE`: Emitted on `{` or `}`.
- `S3E_PARSE_OBSOLETE_SEMICOLON`: Emitted on `;`.
