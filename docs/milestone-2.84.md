# Milestone 2.84: Canonical IR Verifier Candidate

M2.84 adds a bounded verifier candidate for the linear canonical IR shape.
It checks the invariants needed before later composition: register bounds,
single definition, use after definition and a final terminator.

## Contract

- one function and one block are covered;
- every operand must refer to a previously defined register;
- result registers are bounded and may be defined once;
- terminators cannot precede another instruction and the final instruction
  must terminate;
- rejection stages are explicit and compared against the Python reference.

## Non-claims

This milestone does not replace the production verifier, verify multi-block
dominance, add public diagnostics, change IR 0.6.0, promote the candidate,
claim native self-hosting or run global T4. Multi-block and composed closure
remain later milestones.
