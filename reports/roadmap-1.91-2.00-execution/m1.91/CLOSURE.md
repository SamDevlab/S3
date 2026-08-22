# M1.91 Closure Checkpoint

Status: `PASS`

Implemented in the campaign branch:

- first-class V0.6 `select`/`case` syntax;
- semantic ownership joins for select arms;
- bounded executable async select actions and nested suspension;
- deterministic source-order candidate resolution;
- cancellation/drop handling for unselected Future owners;
- shared arity enforcement in compiler and channel select paths;
- focused cross-layer regression tests.

The checkpoint is not a publication or merge assertion. M1.92 must not begin
until the M1.91 campaign gates are completed and this state is reviewed by the
campaign driver.
