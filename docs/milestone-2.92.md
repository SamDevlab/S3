# Milestone 2.92: Assembly Verification Closure

M2.92 composes the bounded Assembly emission candidate with the existing
Assembly parser and verifier. Emitted text must parse and pass the verifier
before its candidate identity is accepted.

## Contract

- emission remains limited to the M2.91 linear subset;
- emitted text is reparsed from bytes/text before verification;
- `AssemblyVerifier` validates the parsed program and entry point;
- invalid canonical IR fails before the verification candidate runs.

## Non-claims

M2.92 does not replace the production Assembly verifier, claim complete
Assembly coverage, provide native object emission, claim full self-hosting or
run global T4.
