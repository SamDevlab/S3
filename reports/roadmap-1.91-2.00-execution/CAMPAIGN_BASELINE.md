# M1.91-M2.00 Campaign Baseline

## Canonical ancestry

```text
REPOSITORY=SamDevlab/S3
CANONICAL_BRANCH=main
CANONICAL_BASE_SHA=a9e430551f2ee77aa2ef229daf9e967333e83e2c
PREDECESSOR_PR=183
PREDECESSOR_LINE=M1.81-M1.90
CAMPAIGN_BRANCH=feature/m191-m200-autonomous-20260819
```

The campaign branch was created directly from the canonical merge commit above.
No implementation code has been added as part of this baseline preparation.

## Inherited capability floor

M1.91-M2.00 must build on, and must not silently regress, the merged M1.81-M1.90
contracts:

- executable resumable async IR and async entry dispatch;
- move-only `Future<T>`, async modules, and deterministic specialization;
- bounded multithread executor with atomic admission and one-active-poll ownership;
- bounded async process/filesystem I/O;
- bounded HTTP/1.1 client with monotonic request deadline and ASCII request boundary;
- digest-before-cache registry transport with canonical origin identity;
- provider-backed Ed25519 verification with no custom crypto fallback;
- Linux AArch64/macOS ARM64 structural lowering with typed AAPCS64 value classes;
- deterministic toolchain/release-candidate bundle verification that is fail-closed;
- the core instruction/resource ceiling `100000` remains preserved.

The following predecessor evidence remains historical and must not be rewritten:

- publication T4: 359 selected / 336 pass / 1 fail / 22 timeout / exit 1;
- terminal triage: 0 reproducible failures and 0 unresolved cases;
- Ed25519 provider execution deferred where `cryptography` is unavailable;
- Linux AArch64 and macOS ARM64 native execution deferred where native
  environments are unavailable.

## Baseline-only scope

This base preparation may:

- establish ancestry and branch identity;
- reconcile stale planning documents after the predecessor merge;
- define campaign execution, testing, evidence, benchmark, and publication rules;
- provide a handoff state for an implementation agent.

This base preparation may **not**:

- add M1.91 production implementation;
- add placeholder behavior that would be mistaken for implementation;
- change runtime semantics, parser/type semantics, native lowering, protocol code,
  package/trust logic, or release behavior;
- create a pull request, merge, tag, release, or public benchmark result;
- begin M2.01 or any post-M2.00 work.

## Local entry verification required

Before implementation starts, the local campaign checkout must record:

```text
LOCAL_BRANCH=feature/m191-m200-autonomous-20260819
LOCAL_HEAD=<exact remote campaign base head>
WORKTREE_CLEAN=YES
CANONICAL_BASE_IS_ANCESTOR=YES
PYTHON_VERSION=<recorded>
PLATFORM=<recorded>
COMPILEALL=<PASS or explicit failure>
SANITY_GATE=<PASS or explicit failure>
M191_IMPLEMENTATION_STARTED=NO
```

A failure in baseline verification is fixed or classified before M1.91 source
changes begin. The verification itself does not authorize implementation until
the campaign owner explicitly starts the campaign.
