# Security Policy

S3 is an **experimental programming language and compiler**. It should not currently be treated as a production-hardened security boundary.

## Supported status

The public package line and internal compiler line are still evolving. Security-sensitive behavior may change as memory, FFI, runtime and host-service capabilities mature.

## Reporting a vulnerability

Please do not publish a security-sensitive report with exploit details in a public issue before the maintainer has had a chance to review it.

Send the report to:

**samusilvadev@gmail.com**

Include, when possible:

- affected commit/version;
- platform and Python/toolchain versions;
- minimal reproduction;
- expected behavior;
- observed behavior;
- whether the issue affects the compiler, verifier, emulator or native output;
- potential security impact.

## Areas of special interest

Reports are especially useful when they demonstrate a violation of an intended invariant, such as:

- verifier bypass;
- out-of-bounds access that should have been rejected/trapped;
- reference/provenance violation;
- unsafe native lowering inconsistent with validated IR;
- optimizer miscompilation;
- disagreement between emulator and native backend;
- malformed serialized IR/Assembly accepted when it should be rejected.

## Experimental limitations

S3 currently does not claim production-grade guarantees for arbitrary hostile code or untrusted FFI/host integrations.

The absence of raw pointers and other unsafe surface features reduces some classes of risk, but it is not a substitute for a mature security audit.
