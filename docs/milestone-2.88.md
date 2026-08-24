# Milestone 2.88: Composed Lowering Closure

M2.88 composes the qualified lowering checkpoint behind a deterministic S3
closure. The checkpoint remains the source of expression, call and verifier
evidence; the closure adds no hidden producer decisions.

## Contract

- the M2.87 checkpoint is evaluated before composition;
- checkpoint evidence remains available in the result;
- the S3 closure applies a bounded deterministic identity step;
- the closure is hosted and experimental.

## Non-claims

M2.88 does not replace production lowering, enable default candidate routing,
claim native self-hosting, claim performance improvement or run global T4.
Explicit canary routing is M2.89 work.
