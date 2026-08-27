# Stage 06 — Control flow: close S4

## Goal

Produce explicit semantic blocks and complete terminators for the canonical Stage1 language subset.

## Required terminators

### RETURN

- terminator kind 1;
- return value ID when applicable;
- no branch targets.

### JUMP

- terminator kind 2;
- exactly one numeric destination in `target_negative`;
- other targets `-1`.

### BRANCH3

- terminator kind 3;
- exactly one condition value ID;
- exactly three numeric targets in negative/zero/positive order.

## Required control constructs

- while loop entry/body/back-edge/exit;
- match negative/zero/positive;
- nested control flow required by canonical Stage1;
- break/loop exit semantics where used;
- every non-external block ends in exactly one complete terminator.

## Required fixtures

- direct return;
- while with semantic condition;
- while with local mutation;
- match returning three distinct values;
- match inside loop or loop inside match if canonical source requires it.

## Exit gate

```text
S1=PASS
S2=PASS
S3=PASS
S4_COMPLETE_TERMINATORS=PASS
BLOCK_TERMINATOR_COVERAGE=100_PERCENT_FOR_QUALIFIED_FIXTURES
BRANCH3_TARGET_ORDER=PASS
```

Do not advance to serialization if any block target/callee/value remains unresolved.
