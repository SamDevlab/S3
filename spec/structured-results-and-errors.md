# M1.42 Structured Results and Errors

This specification defines the recoverable error contract built on S3's
existing nominal payload enums and aggregate result cells. It does not define
generic `Result<T,E>` syntax.

## 1. Result shape

A result is a named enum with explicit success and error variants:

    record ErrorContext:
        code: tryte
        detail: tryte
    enum ParseResult:
        Ok(value: tryte)
        Err(error: ErrorContext)

Variant names are nominal and type-specific. The compiler does not infer that
an arbitrary enum is a result; the program's declaration and API contract give
the variants their meaning. Payload fields are named and type checked.

## 2. Construction and return

Qualified constructors use the declared payload names:

    ParseResult.Ok(value=42)
    ParseResult.Err(error=ErrorContext(code=7, detail=11))

Functions may return a result enum, including a fixed-width multi-cell result.
The tag occupies cell zero; payload leaves follow in declaration order. The
entry function must still return a single scalar result for the standalone
native launcher unless a separate entry adapter is provided.

## 3. Inspection and propagation

Inspection is explicit and exhaustive:

    fn inspect(result: ParseResult) -> tryte:
        match result:
            ParseResult.Ok(value):
                return value
            ParseResult.Err(error):
                return 0 - error.code - error.detail

The success payload is not implicitly converted to a scalar. Returning or
using the whole result where a scalar is required is a semantic type mismatch.
Missing variants in a `match` are a deterministic semantic diagnostic.
Propagation is ordinary control flow: each caller matches the result and
returns an explicit success or error constructor. There is no `?`, implicit
propagation, exception, unwinding, or hidden branch.

## 4. Error code and context policy

An error code must be an explicitly declared field or enum discriminant. Error
context must use declared payload fields. Payload order, width, inactive slots,
and nested record leaves are deterministic. Error values do not contain host
addresses, allocator identity, timestamps, randomized hashes, or unspecified
text formatting.

## 5. Recoverable versus terminal failure

Use a result value for expected domain outcomes such as invalid user input,
capacity refusal requested by an API, I/O failure, or a foreign operation
status. The following remain semantic diagnostics or deterministic traps:

- use-after-move, borrow conflict, invalid reference escape, and type errors;
- out-of-bounds, overflow, uninitialized access, and immutable writes;
- allocation-limit violations and malformed compiler artifacts;
- native toolchain, target, and process failures at the compiler boundary.

These failures must not be encoded as a magic result value merely to avoid the
specified safety boundary.

## 6. IR and Assembly

The semantic enum layout is authoritative for lowering. IR represents a
multi-cell result as one grouped call/return contract with ordered scalar
cells. Assembly preserves the function result type group and result width.
Existing IR and Assembly format versions remain valid; result serialization is
canonical and round-trippable.

## 7. Native and differential behavior

Hosted execution, IR emulation, and Linux x86-64 native execution must agree
on success values, error tags, payload bindings, explicit propagation, and
deterministic inactive cells. O0 and O1 must preserve the same observable
result. Native aggregate returns use the established aggregate ABI; M1.42
does not add exception metadata or unwinding.

## 8. Non-goals

Generic parameters, generic result syntax, exceptions, stack unwinding,
implicit propagation, reflection, dynamic error objects, hidden allocation,
and arbitrary error serialization are outside M1.42. M1.43 owns resource
handles and capability enforcement and consumes this result contract.
