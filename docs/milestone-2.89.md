# Milestone 2.89: Lowering Canary

M2.89 adds explicit opt-in routing for the composed lowering closure. The
reference lowering path remains the default and is retained as a visible
fallback.

## Selection Rules

The canary requires explicit opt-in, exact source-lock agreement and a
canonical differential match. Candidate errors and output drift are reported
as fallback decisions; no fallback is silent and no candidate is selected by
default.

## Non-claims

M2.89 does not replace production lowering, enable default self-hosting,
change public IR 0.6.0, claim native execution, claim performance improvement
or run global T4. M2.90 owns the bounded IR/lowering checkpoint.
