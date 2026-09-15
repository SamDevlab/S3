# Self-host deferred / roadmap return report

Date: 2026-09-14

## Result

Full compiler self-hosting is classified as a **deferred research frontier** rather than an active critical-path deliverable.

```text
SELFHOST_STATUS=DEFERRED_RESEARCH_FRONTIER
REFERENCE_COMPILER=PYTHON
SELFHOST_BLOCKS_NORMAL_DEVELOPMENT=NO
FULL_SELFHOST_CANONICAL_CANDIDATE=NONE
STAGE1_V4=NOT_AUTHORIZED
```

Existing S3-written self-host components remain preserved as bounded research, differential references, and historical milestone evidence. Their historical results are not rewritten by this policy change.

## Architectural decision

A future full self-host attempt must be design-first and demonstrate, before implementation:

- one generic `compile_program` composition root;
- a self-host-representable AST/HIR model;
- stable scope/declaration/type/storage identity;
- deterministic direct ID allocation;
- transactional speculative lowering;
- an IR covering the complete required Stage1 subset;
- an independent verifier;
- a complete emitter/output plan;
- explicit Stage0/Stage1/Stage2 bootstrap boundaries;
- complexity budgets excluding repeated prefix rescans, source recount, and pathological state copying.

Vertical slices remain useful acceptance tests but are not allowed to become production dispatch architecture.

## Re-entry

Re-entry is not tied to a version number or milestone. It requires closing the design and representability gates in `docs/selfhost/REENTRY_CRITERIA.md` and a new explicit authorization.

## Preserved policy documents

- `docs/selfhost/STATUS.md`
- `docs/selfhost/LESSONS.md`
- `docs/selfhost/REENTRY_CRITERIA.md`
- `docs/selfhost/FUTURE_ARCHITECTURE.md`
- `selfhost/README.md`

No compiler behavior is changed by this policy transition.
