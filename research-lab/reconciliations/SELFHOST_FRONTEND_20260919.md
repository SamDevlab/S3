# Self-hosting native frontend reconciliation — 2026-09-19

## Purpose

Retroactive knowledge closure for the native source-frontend/self-hosting work that advanced after the Research Lab stopped receiving regular updates.

This reconciliation records both technical successes and process failures. It does not merge or promote the stacked production PRs.

## Provenance

```text
DATE=2026-09-19
RESEARCH_BRANCH=research/zettelkasten-lab-20260812

PR301=OPEN_DRAFT
PR301_HEAD=b82a94d91e065b892e3c801ccafde0f364908a9e
PR301_FUNCTIONAL_HEAD=5230f92281e482a30fee8d116fb29d6932483fe1

PR302=OPEN_DRAFT
PR302_HEAD=469578b8257806d9ef4a7ed7ac35854279ac417c
PR302_FUNCTIONAL_HEAD=0cceff303f0337fe45db9b80a2e7b6e814ff979e

REFERENCE_FALLBACK=NONE
REMOTE_CI=FAIL_PRE_EXECUTION_INFRA_DISPATCH
```

The PRs are stacked and remain unmerged. Evidence here is implementation/validation evidence, not release certification.

## What worked

### Independent oracle boundary

The campaign established an independent hosted source frontend used as a differential oracle rather than as a hidden fallback.

The native path consumes native token vectors and makes the supported parsing decisions in ordinary S3 code.

### Native lexer/parser progression

The bounded native frontend progressed through:

```text
source
→ native lexer
→ native token stream
→ native parser
→ integer expressions
→ binary + and *
→ precedence
→ left associativity
→ parenthesized grouping
→ identifier primary expressions
→ identifier/binary/precedence/grouping integration
```

PR #301 closed the bounded expression-core slice.

Observed evidence recorded by the PR:

```text
NATIVE_INTEGER_EXPRESSION=PASS
NATIVE_BINARY_ADDITION=PASS
NATIVE_MULTIPLICATION=PASS
NATIVE_EXPRESSION_PRECEDENCE=PASS
NATIVE_SAME_LEVEL_ASSOCIATIVITY=PASS
NATIVE_PARENTHESIZED_EXPRESSION=PASS
NATIVE_GROUPING_OVERRIDES_PRECEDENCE=PASS
NATIVE_EXPRESSION_NEGATIVE_CASES=PASS
FOCUSED_LINUX_NATIVE=34 passed
FULL_SUITE_EXIT=0
```

PR #302 extended primary expressions with identifiers derived from real source bytes/spans.

Observed evidence:

```text
NATIVE_IDENTIFIER_PRIMARY=PASS
NATIVE_IDENTIFIER_BINARY_EXPRESSION=PASS
NATIVE_IDENTIFIER_PRECEDENCE_INTEGRATION=PASS
NATIVE_IDENTIFIER_GROUPING_INTEGRATION=PASS
NATIVE_IDENTIFIER_NEGATIVE_CASES=PASS
FOCUSED_LINUX_NATIVE=36 passed
FULL_SUITE_EXIT=0
```

## What did not work / limitations

### Remote CI provisioning

The remote checks repeatedly failed before test execution:

```text
RUNNER_ASSIGNED=NO
STEPS_STARTED=NO
REMOTE_TEST_EXECUTED=NO
```

This is classified as an infrastructure/dispatch failure, not evidence of a code/test failure.

Local Windows focused tests, Linux x86-64 native qualification and the full local suite supplied the available implementation evidence, but the Draft PRs are not remotely CI-certified.

### Self-hosting remains partial

The successful subset does not establish a full native parser or complete self-hosting.

Not yet established by these PRs:

```text
statement sequence
local bindings
assignment
symbol resolution
type checking
calls
broader control flow
full native frontend
full compiler self-hosting
```

The next documented grammar blocker after PR #302 is `NATIVE_STATEMENT_SEQUENCE`.

### Knowledge-capture failure

The Research Lab/Zettelkasten was not updated while the September self-hosting work progressed.

Result:

```text
IMPLEMENTATION_STATE > RESEARCH_NOTE_STATE
```

This is a process failure: useful successes, negative cases, infrastructure distinctions and architectural lessons remained only in chats/PR descriptions instead of feeding the durable knowledge graph.

The gap motivated Decision D-009 and the campaign knowledge-closure protocol.

### Excessive fragmentation

The sequence of very small stacked frontend PRs improved isolation but introduced repeated branch/PR/report/gate overhead.

Current process adjustment:

- preserve narrow semantic milestones internally;
- group related milestones into larger coherent campaigns when the dependency chain is clear;
- use focused validation while developing;
- run broad/full validation at meaningful campaign checkpoints;
- perform consolidated knowledge closure instead of producing a separate research ceremony for each micro-increment.

This is a workflow conclusion, not evidence that large PRs are always preferable.

## Existing notes strengthened by the campaign

### IC-012 — Self-hosting should progress by semantic-layer replacement

The September campaign provides direct bounded evidence for the pattern:

```text
REFERENCE SEMANTICS
→ REPLACE ONE IMPLEMENTATION LAYER
→ DIFFERENTIAL VALIDATION
→ EXTEND THE NATIVE SEMANTIC SUBSET
```

The result strengthens IC-012 but does not yet justify a universal claim about all self-hosting stages.

### IC-013 — Evaluator/compiler agreement can be a bounded differential oracle

The independent hosted frontend vs native S3 frontend comparison provides concrete evidence that a separately implemented reference path can serve as a bounded oracle for source/token/syntax behavior.

The oracle remains valuable only to the extent that implementation independence and supported semantic scope are explicit.

### S3-ZK-0026 — Demonstration success is not technology maturity

Strengthened as a process reminder: successful native lexer/parser slices are meaningful self-hosting progress, but they do not establish full self-hosting.

### S3-ZK-0068 — Structural evidence is not a runtime oracle

No runtime-performance claim is derived from parser/lexer structural success.

### S3-ZK-0070 — Safety and profitability are separate gates

Relevant by analogy: correctness of the native semantic replacement and broader value/performance of the architecture remain separate questions.

## New idea captured separately

The September discussion also explored implicit function signatures:

```s3
fn soma(a, b):
    return a + b
```

and automatic numeric representation selection.

This remains speculative/deferred. It should enter the canonical temporary insight system rather than becoming an active self-hosting requirement.

The aggressive form (dynamic numeric-width promotion) is currently considered unlikely to be viable; static semantic-type inference and later representation selection remain separate possible research questions.

## Current self-hosting direction

The immediate campaign direction remains native frontend growth.

The next bounded parser capability is:

```text
NATIVE_STATEMENT_SEQUENCE
```

The subsequent broader plan is to reduce operational fragmentation by grouping related native-program-frontend milestones into a larger campaign rather than opening one production PR for every tiny grammar feature.

## Knowledge result

```text
TECHNICAL_SELFHOST_PROGRESS=REAL_BUT_PARTIAL
DIFFERENTIAL_ORACLE_BOUNDARY=USEFUL
NATIVE_LINUX_EVIDENCE=PASS_FOR_RECORDED_SUBSETS
REMOTE_CI_CERTIFICATION=BLOCKED_BY_INFRASTRUCTURE
KNOWLEDGE_CAPTURE_LAG=CONFIRMED_PROCESS_FAILURE
MICRO_PR_FRAGMENTATION=CONFIRMED_PROCESS_COST
NEXT_PROCESS=CONTINUOUS_CAMPAIGN_KNOWLEDGE_CLOSURE
```

## Reopen / update conditions

Update this reconciliation when:

- the stacked PRs are merged/rebased or abandoned;
- statement-sequence/native-program parsing materially expands the semantic subset;
- remote CI begins actually executing steps;
- a self-hosting stage falsifies the semantic-layer replacement approach;
- new evidence supports promotion/rejection of IC-012 or IC-013.
