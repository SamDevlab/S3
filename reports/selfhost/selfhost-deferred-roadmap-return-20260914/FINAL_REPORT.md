# Self-host deferred / roadmap return report

Date: 2026-09-14

## Result

The repository policy is updated to treat full compiler self-hosting as a
**deferred research frontier** rather than an active critical-path deliverable.

No production compiler code is changed by this transition.

## Project state

```text
SELFHOST_STATUS=DEFERRED_RESEARCH_FRONTIER
REFERENCE_COMPILER=PYTHON
SELFHOST_BLOCKS_NORMAL_DEVELOPMENT=NO
FULL_SELFHOST_CANONICAL_CANDIDATE=NONE
STAGE1_V4=NOT_AUTHORIZED
```

Existing bounded S3-written self-host components remain preserved as research,
differential references, and historical milestone evidence. Their existing
milestone statuses are not rewritten by this policy change.

## Architectural decision

A future full self-host attempt must not restart as another incremental
prototype generation. Re-entry is design-first and requires repository evidence
for:

- one generic `compile_program` composition root;
- a self-host-representable generic AST/HIR model;
- stable scope/declaration/type/storage identity;
- direct deterministic ID allocation;
- transactional speculative lowering;
- an IR mapped to the complete required Stage1 subset;
- an independent verifier;
- a complete emitter/output plan;
- explicit bootstrap Stage0/Stage1/Stage2 boundaries;
- complexity budgets that exclude repeated prefix rescans, source recount, and
  pathological state copying.

Vertical slices remain useful acceptance tests but are explicitly prohibited as
production dispatch architecture.

## Timing correction

Earlier planning considered language/runtime milestones such as slices or
dynamic data as possible future reevaluation points. The current repository has
already progressed through those capability families and beyond them. Therefore
self-host re-entry is no longer tied to a milestone number.

A future re-entry review depends on closing the architecture/representability
gates in `docs/selfhost/REENTRY_CRITERIA.md`, regardless of current roadmap
version.

## Files added

- `docs/selfhost/STATUS.md`
- `docs/selfhost/LESSONS.md`
- `docs/selfhost/REENTRY_CRITERIA.md`
- `docs/selfhost/FUTURE_ARCHITECTURE.md`

## Files updated

- `selfhost/README.md`

## Validation scope

This transition is documentation-only. No compiler test suite, canonical
qualification, Stage2, Stage3, or destructive Git operation is required or
claimed by this report.

The branch is intended for review before merge.

## Next action

Merge the policy/documentation change after review, then continue the normal S3
roadmap from the repository's current roadmap state. Full self-hosting remains
deferred until a separately authorized design-only re-entry review closes all
required gates.
