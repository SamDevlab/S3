# Milestone 2.85: Composed IR Closure

M2.85 composes the qualified expression and call producers behind one
bounded closure identity. The composition is explicit and remains an
experimental hosted path.

## Contract

- expression and call producers run before composition;
- their identities remain visible in the result;
- the closure applies a deterministic bounded fold;
- the S3 candidate receives the two producer identities and does not recreate
  their reference logic.

## Non-claims

M2.85 does not promote a compiler path, alter public IR 0.6.0, add verifier
coverage, claim native self-hosting, claim performance improvement or run
global T4. Canary routing is later work.
