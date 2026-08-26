# PR #268 — Parallel Stage1 / Stage2→Stage3 certification handoff

This document belongs to the isolated branch:

`audit/pr268-parallel-stage1-certification-20260825`

It was intentionally prepared in parallel while an autonomous agent worked on the actual PR #268 branch. **Do not merge/cherry-pick this branch into the PR while that agent is still mutating the PR head.** Reconcile after the agent's checkpoint.

## Branch provenance

- Parallel base: `0ea67c4780f4b7577099690d2ef5cfc8dfe34529`
- Canonical compiler source was not modified by this parallel work.
- PR branch was still at the same base HEAD on the last read-only check made while preparing this handoff.
- All new tools/contracts below are prepared evidence/tooling only until their focused/Linux tests execute.

## 1. Native token-source coverage hardening

Prepared:

- `selfhost/compiler/stage1_host_io_coverage.c`
- `tools/qualify_stage1_token_lane_full_coverage.py`
- `tests/test_stage1_token_lane_native_full_coverage.py`

Reason: the existing wide-token-lane native qualifier compares complete AST/call counters but does not directly prove every source byte was observed by the native compiler process. The coverage host shim records byte indices touched by `s3_stage1_read_byte()` without changing the S3 compiler source.

Strict target:

```text
base token-lane native candidate = PASS
touched_source_bytes == source_length
first_unread == -1
max_read == source_length - 1
=> PASS_NATIVE_FULL_SOURCE_COVERAGE
```

This is stronger evidence than aggregate counters alone.

## 2. Semantic value / def-use storage model

Prepared:

- `reports/selfhost/stage1/semantic-def-use-verifier-contract.json`
- `tools/audit_stage1_semantic_def_use_requirements.py`
- `tests/test_stage1_semantic_def_use_requirements.py`

Key architecture decision:

- parameters are immutable semantic values available at function entry;
- mutable scalar locals are **storage identities**, not an implicit changing SSA value;
- fixed arrays are storage identities carrying element type and fixed extent;
- every local read produces an explicit load result;
- every local write consumes an explicit source value;
- every fixed-array element access carries an explicit semantic index value;
- compound assignment lowers as load → compute → store;
- mutable storage itself does not require phi nodes; instruction-result values remain single-definition and dominance checked.

The logical roles `LOAD_LOCAL`, `STORE_LOCAL`, `LOAD_INDEX`, `STORE_INDEX` do **not** require four physical opcodes. The reference S3 IR already has generic `IROpcode.LOAD/STORE`, `IRMemoryObject`, `IRInstruction.memory`, result and operand fields. IR-v2 may use generic physical LOAD/STORE when storage identity, optional index operand, source/result value, shape and mutability remain explicit and verifier checked.

The external typed-AST audit is an oracle/test tool only. It must never become the Stage1 compiler backend.

## 3. Stage1 codegen-complete native fixtures

Prepared:

- `tests/stage1_codegen_complete_fixtures.json`
- `tools/qualify_stage1_codegen_complete_fixtures.py`

Positive execution coverage includes:

- literal return;
- scalar local load/store;
- internal call with four ordered arguments and result;
- while/conditional CFG;
- match CFG;
- fixed-array initialization, index loads and index store;
- foreign side-effecting call through the existing host shim;
- nested calls / computed return.

Negative coverage includes deterministic malformed-source failure.

The qualifier receives a **real Stage1 executable**. Python only orchestrates. Stage1 emits assembly, host tools assemble/link, and the resulting program executes. Compiler invocations are bound to strict process/filesystem traces.

A fixture PASS is necessary evidence but explicitly leaves:

`STAGE1_CERTIFIED_FOR_STAGE2=False`

until canonical self-emit + verifier-v2 + the remaining gates pass.

## 4. Stage1 certification gate contract

Prepared:

- `reports/selfhost/stage1/stage1-certification-gate-contract.json`

The only document allowed to authorize the Stage2 campaign is intended to be:

`reports/selfhost/stage1/stage1-certification-gate.json`

with schema:

`s3.selfhost.stage1-certification-gate.v1`

It must bind the exact final canonical source SHA/bytes/commit and require:

```text
stage1_certified_for_stage2=true
self_emit=PASS
semantic_ir=PASS_CODEGEN_COMPLETE_BOOTSTRAP_SUBSET
verifier_v2=PASS
general_emitter=PASS_BOOTSTRAP_REQUIRED_OPCODES
```

It also requires native source coverage, capacities without truncation, semantic values/def-use, explicit storage/index access, codegen-complete native fixture PASS and canonical self-emit evidence.

## 5. Stage2 → Stage3 intermediate fixed point

Prepared:

- `reports/selfhost/stage2/stage2-stage3-fixed-point-contract.json`
- `tools/qualify_stage2_stage3_fixed_point.py`
- `tests/test_stage2_stage3_fixed_point_contract.py`

The harness is deliberately **intermediate-only**. It can never write `FULL_SELF_HOSTING=YES`.

It requires a valid Stage1 certification, then:

1. compile `stage1_host_io.c` once;
2. Stage1 exact canonical source → Stage2 assembly → Stage2 ELF;
3. representative Stage2 conformance;
4. Stage2 same exact canonical source → Stage3 assembly → Stage3 ELF;
5. reuse the identical host object and identical linker recipe;
6. require Stage2 ELF and Stage3 ELF exact SHA/byte equality.

Link recipe retains the existing deterministic properties:

```text
-nostdlib
-no-pie
-s
-Wl,--build-id=none
```

Assembly equality is a strong diagnostic signal, not a stricter replacement for the required exact ELF fixed point.

The intermediate harness reports:

`full_self_hosting=false`

and routes a successful fixed point to the strict sandbox wrapper.

## 6. Strict Python/bootstrap-inaccessible fixed-point wrapper

Prepared:

- `tools/qualify_stage2_stage3_strict_sandbox.py`
- `tests/test_stage2_stage3_strict_sandbox.py`

The wrapper executes the intermediate fixed-point harness, then replays the exact Stage1→Stage2 and Stage2→Stage3 compiler invocations under:

```text
strace -f -e trace=execve,open,openat
```

Required compiler-process proof:

- exactly one compiler `execve`;
- no descendant process execution;
- no Python executable;
- no repository-checkout access;
- no `bootstrap/` access;
- no `.py` / `.pyc` access;
- normalized PATH/PYTHONPATH/PYTHONHOME/LANG/LC_ALL/TZ/SOURCE_DATE_EPOCH;
- canonical source supplied through stdin;
- traced assembly SHA must equal the assembly SHA actually used to build the measured Stage2/Stage3 artifact.

System dynamic-loader reads are allowed and are not treated as compiler delegation.

Only this strict wrapper may reach:

```text
stage2_pythonless_compiler=PASS_STRICT_PROCESS_AND_FILE_TRACE
stage2_conformance=PASS
stage2_stage3_exact_elf_fixed_point=true
full_self_hosting=true
```

## 7. Tests still required

No PASS is claimed for the parallel branch yet.

After the autonomous PR agent finishes and the useful pieces are reconciled, run at minimum on the Linux guest:

```bash
python -m pytest -q \
  tests/test_stage1_token_lane_native_full_coverage.py \
  tests/test_stage1_semantic_def_use_requirements.py \
  tests/test_stage2_stage3_fixed_point_contract.py \
  tests/test_stage2_stage3_strict_sandbox.py
```

Also run compileall/JSON validation/diff-check for any selected integration.

The native qualifiers are dormant until their real prerequisite artifacts exist.

## 8. Integration policy after the main agent stops

Do not blindly merge the whole side branch.

First:

1. fetch the final PR #268 HEAD;
2. compare it with this branch;
3. discard any side-branch tooling superseded by better main-agent implementation;
4. preserve the stronger gates that are still missing;
5. rebase/adapt to the final schemas rather than forcing stale assumptions;
6. run focused tests before pushing anything to PR #268.

Priority pieces to preserve if still absent:

1. direct native byte-read source coverage;
2. storage-identity + explicit generic LOAD/STORE def-use contract including arrays;
3. Stage1 codegen-complete execution fixtures;
4. machine-readable Stage1 certification gate;
5. intermediate fixed point kept non-authoritative;
6. strict process + filesystem anti-delegation proof before `FULL_SELF_HOSTING=YES`.

## Status

```text
PARALLEL_BRANCH_ONLY=YES
MAIN_PR_MUTATED_BY_THIS_PARALLEL_WORK=NO
CANONICAL_SOURCE_MUTATED=NO
PARALLEL_TOOLING_TESTED_HERE=NO
NATIVE_EVIDENCE_FROM_PARALLEL_BRANCH=NO
STAGE1_CERTIFIED_FOR_STAGE2=NO
STAGE2_STARTED_BY_PARALLEL_BRANCH=NO
STAGE3_STARTED_BY_PARALLEL_BRANCH=NO
FULL_SELF_HOSTING=NO
```
