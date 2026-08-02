# Milestone 1.09 - Aggregate Function Results

Status: Implementation complete locally in Draft PR #127; user validation pending.

Milestone 1.09 makes fixed-layout source values returnable from ordinary
functions. A source function still returns one logical value and one declared
type. The compiler lowers that value to the ordered cells described by
`SemanticModel.fixed_value_layout(...)`.

## Scope

Implemented aggregate returns include:

- records with two or more scalar leaves;
- nested records in depth-first declaration order;
- nominal enums with tag-first fixed payload layout;
- variants with different payload widths and deterministic inactive slots;
- structured result APIs modeled as nominal enums such as `Ok`/`Err`;
- local and imported nominal result types;
- direct constructor returns, local returns, parameter returns, direct call
  returns, nested calls, and call results used as arguments.

## Invariants

- A call returning an aggregate is emitted once.
- All result cells are materialized together or discarded together.
- Partial result consumption is not a source-language feature.
- Nominal identity is preserved; same-shape types remain incompatible when their
  nominal identities differ.
- Arrays are not fixed value leaves and are not returnable as aggregate values.
- Recursive layouts remain rejected.

## Native

Width-1 returns use the scalar `RAX` convention. Width greater than 1 uses the
hidden sret convention documented in `spec/native-x86_64.md`. The entry point
remains scalar-only.

Tests covering this milestone were authored across aggregate language,
optimizer, SSA, emulator, and native surfaces. Tests added after the
no-agent-testing policy change are not executed by the agent and require user
validation.
