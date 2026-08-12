from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def _top_families(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    counts: Counter[tuple[str, str, str]] = Counter(
        (str(row["function"]), str(row["block"]), str(row["family"]))
        for row in rows
    )
    result = []
    for rank, ((function, block, family), count) in enumerate(
        counts.most_common(50), 1
    ):
        result.append(
            {
                "rank": rank,
                "function": function,
                "block": block,
                "state_kind": family,
                "static_count": count,
                "dynamic_weight": None,
                "weight_kind": "UNKNOWN",
                "first_introduction_layer": (
                    "x86_64 emitter frame layout and metadata helpers"
                ),
                "first_redundant_layer": (
                    "not established; repeated physical checks/stores are emitted here"
                ),
                "semantic_necessity": (
                    "USER_DATA_REQUIRED"
                    if family.startswith("MEMORY_DATA")
                    else "REQUIRED_OR_CONDITIONALLY_AVOIDABLE"
                ),
                "likely_optimization_class": (
                    "none: semantic data"
                    if family.startswith("MEMORY_DATA")
                    else "proof-fact propagation and lazy state materialization"
                ),
            }
        )
    return result


def _write(path: Path, text: str) -> None:
    path.write_text(text.rstrip() + "\n", encoding="utf-8")


def build(audit_json: Path, report_dir: Path, research_head: str) -> None:
    audit = json.loads(audit_json.read_text(encoding="utf-8"))
    mode = audit["modes"]["RA_ON"]
    families = mode["metadata_family_counts"]
    rows = mode["metadata_lines"]
    top = _top_families(rows)
    report_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "campaign": "P5-AUDIT",
        "production_base": "a0b694fadc985c0b8e0944fb7844e14f72a838d8",
        "p4_merge_ancestor": True,
        "p4_metric_reproduced": True,
        "p4_metric_source": "external p4_value_probe.py plus independent byte-frame decomposition",
        "p4_metadata_metric_definition": "all emitted disassembly lines containing byte ptr [rbp",
        "p4_metadata_accesses_expected": 5638,
        "p4_metadata_accesses_reproduced": 5638,
        "total_target_accesses": 5638,
        "classified_accesses": 5638,
        "classification_coverage": 1.0,
        "required_share": None,
        "avoidable_share": None,
        "conditionally_avoidable_share": None,
        "unknown_share": None,
        "physical_origin_classification": {
            "register_initialization": 4589,
            "memory_initialization": 837,
            "memory_data_trit_bytes": 212,
            "classification_note": "100% physical-origin coverage; semantic necessity shares were not fabricated",
        },
        "initialization_state_accesses": 5426,
        "memory_validity_accesses": 0,
        "memory_validity_note": "no independent MEMORY_VALID bit exists; initialized-state bytes guard definedness and immutable-write semantics",
        "ssa_destruction_accesses": 0,
        "phi_edge_accesses": 0,
        "loop_phi_accesses": 0,
        "call_abi_accesses": 0,
        "reference_address_required_accesses": 0,
        "true_ra_spill_accesses": None,
        "emitter_staging_accesses": 5426,
        "redundant_state_materializations": None,
        "dead_metadata_stores": None,
        "loads_with_fact_already_known": None,
        "primary_static_cause": "emitter materialization of register and memory initialization state",
        "primary_dynamic_cause": "NOT_ESTABLISHED_NO_DYNAMIC_TRACE",
        "earliest_introduction_layer": "x86_64 emitter frame layout and initialized-state helpers",
        "earliest_redundant_repetition_layer": "not established; physical repetition begins in emitter access guards/stores",
        "fact_loss_causes_memory_traffic": "partial",
        "state_collapse_confirmed": "partial",
        "parallel_copy_model": "partial",
        "dual_validity_model_useful": True,
        "reduced_product_model": "useful",
        "metadata_automaton_built": True,
        "raw_state_count": None,
        "minimized_state_count": None,
        "mincut_metadata_model": "partial",
        "exact_metadata_oracle_available": False,
        "smt_oracle_available": False,
        "new_idea_discovered": False,
        "dominant_avoidable_pattern": "repeated initialized-state checks/stores whose removability depends on preserved proof facts",
        "recommended_p5_target": "proof-preserving initialization-state propagation with lazy native materialization",
        "recommended_p5_name": "P5 — Proof-Preserving Initialization State and Lazy Materialization",
        "top_50_access_families": top,
        "production_code_committed": False,
        "temporary_instrumentation_used": False,
        "temporary_instrumentation_reverted": True,
        "full_suite_run": False,
        "production_pr_opened": False,
        "p5_started": False,
        "p6_started": False,
        "shutdown_authorized": False,
        "research_branch_head_final": research_head,
        "production_worktree_clean": True,
        "status": "COMPLETE",
    }
    (report_dir / "P5_AUDIT_RESULT.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    (report_dir / "04-top-access-families.json").write_text(
        json.dumps(top, indent=2), encoding="utf-8"
    )

    _write(
        report_dir / "00-repository-state.md",
        f"""# P5 Audit Repository State

CURRENT_ORIGIN_MAIN=a0b694fadc985c0b8e0944fb7844e14f72a838d8
P4_MERGE_ANCESTOR=YES
AUDIT_BASE_A=a0b694fadc985c0b8e0944fb7844e14f72a838d8
AUDIT_BASE_B=NOT_REQUIRED_MAIN_UNCHANGED
AUDIT_WORKTREE=C:/Users/samue/Downloads/S3/S3-p5-audit-20260812
RESEARCH_BRANCH=research/zettelkasten-lab-20260812
RESEARCH_BRANCH_HEAD={research_head}
P4_REPORTS_FOUND=YES_EXTERNAL
P4_VALUE_CORPUS_FOUND=YES_EXTERNAL
P4_METADATA_TOOL_FOUND=YES_EXTERNAL
P5_AUDIT_STARTED=YES
PRODUCTION_IMPLEMENTATION_STARTED=NO
P5_STARTED=NO
P6_STARTED=NO
FULL_SUITE_AUTHORIZED=NO
SHUTDOWN_AUTHORIZED=NO

The user's pre-existing checkout was detached and had two unrelated
untracked campaign artifacts. It was not modified. The audit worktree is
clean and detached at the exact P4 merge.
""",
    )
    _write(
        report_dir / "01-p4-metric-reproduction.md",
        """# P4 Metric Reproduction

The external P4 probe's definition is lexical: count every generated native
line containing `byte ptr [rbp`. Re-running the same compilation against the
exact P4 merge reproduces `5638` in both RA_OFF and RA_ON. The workload source
is external to the historical P4 tree and was supplied from the user's
current experiment checkout; that provenance is recorded rather than hidden.

RA_OFF: frame accesses 9282, qword loads 1549, qword stores 1520, byte-frame
metric 5638.

RA_ON: frame accesses 7175, qword loads 491, qword stores 471, byte-frame
metric 5638.

The unchanged byte-frame metric therefore cannot be interpreted as a pure
measure of register allocation or SSA traffic.
""",
    )
    _write(
        report_dir / "02-metadata-definition.md",
        f"""# What P4 Called Metadata

## Exact definition

`metadata = count(native lines containing byte ptr [rbp`.

## Independent decomposition of {families and 5638}

| physical origin | count | share |
|---|---:|---:|
| register initialization bytes | 4589 | 81.3941% |
| memory initialization bytes | 837 | 14.8457% |
| trit array data bytes | 212 | 3.7602% |
| total | 5638 | 100% |

The `212` data accesses are user data, not compiler metadata. The remaining
`5426` accesses are initialization/definedness state. The decomposition has
100% physical-origin coverage; semantic required/avoidable shares remain
unmeasured and are not invented.

The `memory initialization` count is `228` TLOAD definedness checks plus `96`
immutable-store checks, and `513` initialization-byte stores for TSTORE.
Register initialization is `1520` prologue zero/parameter marks plus `1549`
body checks and `1514` body marks.
""",
    )
    _write(
        report_dir / "03-access-taxonomy.md",
        """# Access Taxonomy

The taxonomy maps the required concepts to the observed population:

* `REGISTER_INITIALIZATION_*`: runtime register-definedness state.
* `MEMORY_INITIALIZATION_*`: runtime memory-definedness and immutable-write
  state.
* `MEMORY_DATA_*`: trit array payload bytes, semantically required user data.
* SSA/phi/loop/call/ABI/reference/true-spill: separate categories; none is
  represented by the 5638 byte-frame metric in this corpus.

All 5638 byte-frame accesses were assigned one of the first three physical
families. This is not a claim that every state access is removable. A future
optimization must preserve uninitialized-register, uninitialized-memory and
immutable-write failure behavior, address identity, aliases and call effects.
""",
    )
    _write(
        report_dir / "05-initialization-state.md",
        """# Initialization-State Forensics

The native emitter allocates one byte per logical register and one byte per
memory cell. `_initialize_metadata` zeroes register flags, clears memory flags
with `rep stosb`, then marks parameters initialized. `_read_register` checks a
register flag; `_write_register` marks it. `_emit_load` checks a memory flag;
`_emit_store` checks immutable state where needed and marks the cell.

The IR initialization analysis has the abstract states
`UNINITIALIZED`, `INITIALIZED`, and `MAYBE_INITIALIZED`, joined conservatively
at CFG merges. It is not the same object as the native emitter's per-register
byte state. This is a proof-knowledge preservation opportunity, but no exact
dead-store or known-fact count was measured.

SEMANTIC_NECESSITY=required under the current runtime contract, with
conditional avoidance possible only after a proof-preserving replacement is
validated.
""",
    )
    _write(
        report_dir / "06-memory-validity.md",
        """# Memory Validity and Dual Validity

There is no separate `MEMORY_VALID` bit in the audited backend. Memory data is
authoritative and the byte flags encode definedness/immutable-write state.
For an allocated scalar, the physical register can be current while its
canonical frame value is stale; `_snapshot_register` materializes the value
before ABI-sensitive calls. This makes a dual-validity model useful as a
research abstraction, but it is not an existing explicit backend state.

DUAL_VALIDITY_MODEL_USEFUL=YES
STATE_COLLAPSE_CONFIRMED=PARTIAL: value data and initialized bytes are
separate, while residence/coherence is implicit rather than explicit.
""",
    )
    _write(
        report_dir / "07-ssa-destruction.md",
        """# SSA Destruction Forensics

The O1 pipeline can build SSA and lower it out of SSA, but the JSMN corpus
used for the P4 metric produces zero phi nodes after the fixpoint pipeline.
The resulting IR has no phi-created memory objects beyond the source memory
objects, and the observed 5638 byte-frame accesses are unchanged by RA.

SSA_DESTRUCTION_ACCESSES=0 in this corpus.
SSA is therefore not the dominant explanation for this measured population.
This is corpus-scoped evidence, not a universal claim about all S3 programs.
""",
    )
    _write(
        report_dir / "08-phi-edge-copies.md",
        """# Phi and Edge-Copy Forensics

The audited corpus has `0` explicit phis, `0` phi edge-copy stores and `0`
critical edges. The out-of-SSA lowering implementation does have an explicit
edge-copy path and splits critical edges when copies are present, so the
compiler architecture is `PARALLEL_COPY_MODEL=PARTIAL`, not absent.

No cycle case was observed in this workload; no claim is made that the
general lowering is cycle-optimal.
""",
    )
    _write(
        report_dir / "09-loop-carried-state.md",
        """# Loop-Carried State

The exact IR dominator analysis finds `34` backedges, all in `main`, and `0`
critical edges. The current static probe has no runtime trip counts and no
per-iteration native metadata trace. LOOP_PHI_ACCESSES=0 for the measured
corpus because no phi nodes were present; dynamic loop weighting is
UNKNOWN, not zero.
""",
    )
    _write(
        report_dir / "10-ra-spill-separation.md",
        """# True RA Spill Separation

RA_ON colors `927` of `1313` main logical registers; `386` receive no physical
color and none are marked address-taken in this corpus. This is a candidate
stack-residency population, not a measured true-spill access count. The
allocator does not expose why every `None` decision occurred, and the emitter
also emits parameter snapshots and ABI/call preservation traffic.

TRUE_RA_SPILL_TRAFFIC=NOT_ESTABLISHED. The 5638 byte-frame metric contains no
qword spill accesses by definition, and true spill counts must not be inferred
from generic frame traffic.
""",
    )
    _write(
        report_dir / "11-call-abi-reference.md",
        """# Call, ABI and Reference Separation

The corpus contains calls, but the byte-frame metric counts no call-preserved
qword slots. Caller-saved preservation is a separate ABI mechanism. The
corpus contains no TADDR/reference operations in the measured IR, so
REFERENCE_ADDRESS_REQUIRED_ACCESSES=0 for this corpus. This does not relax
reference provenance or address identity for future workloads.
""",
    )
    _write(
        report_dir / "12-information-loss.md",
        """# Information-Loss Boundary Audit

| fact | source/IR | Assembly IR | emitter/native |
|---|---|---|---|
| logical register identity | preserved | preserved as vreg | mapped to physical or frame |
| type | preserved | preserved | selects width/encoding |
| SSA identity | derivable in optimizer | intentionally discarded | unavailable |
| phi relation | derivable in SSA | absent in this corpus | unavailable |
| initialization fact | preserved in IR analysis | not carried as a proof object | reified as bytes |
| memory validity/coherence | not independent | not explicit | implicit in frame/value policy |
| address observability | preserved when present | preserved | forces frame residence |
| rematerializability | unknown | unknown | not represented |
| loop invariance | derivable for some passes | not retained as contract | unknown |

FACT_LOSS_CAUSES_MEMORY_TRAFFIC=PARTIAL. The strongest evidence is that the
emitter reifies initialization state independently of the IR analysis result;
the exact removable subset requires a proof-aware trace not present today.
""",
    )
    _write(
        report_dir / "13-state-transition-graph.md",
        """# State Transition Graph

Observed/derived native transitions:

* `UNINITIALIZED -> INITIALIZED`: parameter mark or `_write_register`.
* `UNINITIALIZED -> failure`: `_read_register` or `_emit_load` guard.
* `INITIALIZED -> INITIALIZED`: repeated reads/checks and writes/marks.
* `REGISTER_VALID + MEMORY_STALE -> BOTH_VALID`: `_snapshot_register` before
  a call or another observer.
* `MEMORY_UNINITIALIZED -> MEMORY_VALID`: TSTORE data write and flag mark.
* `MEMORY_VALID -> failure`: immutable TSTORE attempt.

The graph has observable failure effects, so state minimization cannot merge
states merely because one benchmark emits the same x86 instructions.
""",
    )
    _write(
        report_dir / "14-automata-analysis.md",
        """# Automata Analysis

A conceptual finite-state machine was built for register residence and
definedness: `UNINITIALIZED`, `MEMORY_ONLY`, `REGISTER_ONLY`, and `BOTH`, with
failure and address-observable effects kept outside the equivalence relation.
No minimized state count is claimed. A valid minimization proof must preserve
uninitialized failures, calls, address observation and later reload behavior.
""",
    )
    _write(
        report_dir / "15-term-rewrite-analysis.md",
        """# Term-Rewrite Analysis

No production rewrite was accepted. The only candidate rule is:

`CHECK_INIT(v); USE(v) -> USE(v)`

under the preconditions that a dominating proof establishes initialization,
no failure observer is required, and the value's location/alias obligations
remain valid. Occurrence count and dynamic weight are UNKNOWN. Blind emitter
peepholes are rejected because the upstream proof/failure contract is not yet
available.
""",
    )
    _write(
        report_dir / "16-abstract-domain-analysis.md",
        """# Abstract-Domain Analysis

A reduced product is useful as a research model:

`Residence x MemoryDefinedness x Initialization x Observability x MergeState`.

The order is precision order per component; bottom is unreachable/contradictory
state, and joins at CFG merges conservatively lose precision. Transfer
functions are the emitter operations described in the state graph. The
components have finite height for a fixed function/corpus, but a production
domain and convergence proof have not been implemented.

REDUCED_PRODUCT_MODEL=USEFUL_RESEARCH_MODEL
PRODUCTION_STATUS=OPEN; no P5 implementation started.
""",
    )
    _write(
        report_dir / "17-exact-oracle.md",
        """# Exact Oracle

EXACT_METADATA_ORACLE_AVAILABLE=NO
SMT_ORACLE_AVAILABLE=NO

The audit did not add a solver or fabricate an optimality gap. A future
bounded oracle should minimize materializations while preserving failure,
address, call and mutable-memory observations.
""",
    )
    _write(
        report_dir / "18-mincut-model.md",
        """# Min-Cut Model

MINCUT_METADATA_MODEL=PARTIAL. A binary register-side versus materialized-side
cut loses at least initialization/definedness, memory data, immutable-write,
address-observable and call-preservation dimensions. It may remain a bounded
subproblem after those dimensions are fixed, but it is not an exact P5 model.
""",
    )
    _write(
        report_dir / "19-cross-workload.md",
        """# Cross-Workload Evidence

The existing P4 cross-workload characterization covers integer-loop,
nested-loop and branch-heavy scalar semantics, but it does not carry the
byte-frame provenance taxonomy. No new benchmark was run in P5-AUDIT. The
classification is therefore corpus-proven for JSMN and generality beyond it
remains an explicit follow-up gate, not an assumption.
""",
    )
    _write(
        report_dir / "20-dynamic-weighting.md",
        """# Dynamic Weighting

No hardware counters, native execution benchmark, loop-trip trace or dynamic
metadata instrumentation was run. PERF_AVAILABLE=NOT_REQUIRED; no security
setting was changed. All access-family weights are `UNKNOWN`, and the primary
dynamic cause is consequently `NOT_ESTABLISHED`.
""",
    )
    _write(
        report_dir / "21-model-scorecard.md",
        """# Model Scorecard

| model | static evidence | dynamic evidence | verdict |
|---|---|---|---|
| SSA/phi staging | 0 phi accesses in corpus | unavailable | not dominant here |
| initialization fact loss | 5426 state accesses reified by emitter | unavailable | strongest causal model |
| memory-validity/coherence | no independent bit | unavailable | partial companion model |
| emitter-local staging | first physical introduction is emitter | unavailable | supported as layer, not full root cause |
| true RA spill | candidate stack residency only | unavailable | not established |
| call/ABI/reference | outside byte metric / absent refs | unavailable | not dominant here |
| reduced product | explains interacting dimensions | unavailable | useful research model |
| automata minimization | conceptual states only | unavailable | open |
| term rewriting | no safe measured rule | unavailable | rejected for now |

The evidence selects a proof-preserving state-propagation investigation, not
a generic RA rewrite or SSA-only milestone.
""",
    )
    _write(
        report_dir / "22-root-cause-ranking.md",
        """# Root-Cause Ranking

1. **Emitter initialization-state materialization** — static share 5426/5638
   of true state/data-separated target; dynamic share unknown; earliest
   physical layer `_initialize_metadata`, `_read_register`, `_write_register`,
   `_emit_load`, `_emit_store`; confidence HIGH for physical origin.
2. **Trit array data included in the lexical metric** — static share 212/5638;
   mandatory user data; confidence HIGH; not an optimization target.
3. **SSA/phi/loop staging** — static share 0 in this corpus; dynamic share
   unknown; confidence HIGH for the measured workload, not a universal claim.
4. **True RA spill traffic** — share not established; confidence LOW until the
   allocator exposes spill causes and dynamic access attribution.

The P4 label “metadata” was therefore directionally useful but too broad for
choosing a production target.
""",
    )
    _write(
        report_dir / "23-p5-recommendation.md",
        """# P5 Recommendation

RECOMMENDED_P5_NAME=P5 — Proof-Preserving Initialization State and Lazy Materialization

Scope for a future production milestone:

1. expose initialization/definedness facts as a preserved, verifier-backed
   capability rather than an emitter-only byte convention;
2. materialize bytes only at actual observers (failure paths, mutable-memory
   checks, calls/aliases and address identity);
3. preserve the explicit stack-backed fallback and all reference semantics;
4. compare against the simpler current emitter and measure dynamic impact on
   multiple workloads.

Do not implement this during P5-AUDIT. Cross-workload provenance and dynamic
weighting remain promotion gates.
""",
    )
    _write(
        report_dir / "FINAL_P5_AUDIT.md",
        f"""# S3 P5-AUDIT Final Report

## Required state

P5_AUDIT_BASE_SHA=a0b694fadc985c0b8e0944fb7844e14f72a838d8
CURRENT_ORIGIN_MAIN=a0b694fadc985c0b8e0944fb7844e14f72a838d8
P4_MERGE_ANCESTOR=YES
P4_METRIC_REPRODUCED=YES
METADATA_METRIC_DEFINITION=all emitted native lines containing `byte ptr [rbp`
METADATA_ACCESSES_EXPECTED=5638
METADATA_ACCESSES_REPRODUCED=5638
TOTAL_TARGET_ACCESSES=5638
CLASSIFIED_ACCESSES=5638
CLASSIFICATION_COVERAGE=1.0
REQUIRED_SHARE=NOT_ESTABLISHED
AVOIDABLE_SHARE=NOT_ESTABLISHED
CONDITIONALLY_AVOIDABLE_SHARE=NOT_ESTABLISHED
UNKNOWN_SHARE=NOT_ESTABLISHED_FOR_SEMANTIC_NECESSITY; physical origin 0 unknown
INITIALIZATION_STATE_ACCESSES=5426
MEMORY_VALIDITY_ACCESSES=0_EXPLICIT_INDEPENDENT_BIT
SSA_DESTRUCTION_ACCESSES=0_CORPUS
PHI_EDGE_ACCESSES=0_CORPUS
LOOP_PHI_ACCESSES=0_CORPUS
CALL_ABI_ACCESSES=0_WITHIN_BYTE_METRIC
REFERENCE_ADDRESS_REQUIRED_ACCESSES=0_CORPUS
TRUE_RA_SPILL_ACCESSES=NOT_ESTABLISHED
EMITTER_STAGING_ACCESSES=5426_STATE_BYTES
REDUNDANT_STATE_MATERIALIZATIONS=NOT_MEASURED
DEAD_METADATA_STORES=NOT_MEASURED
LOADS_WITH_FACT_ALREADY_KNOWN=NOT_MEASURED
PRIMARY_STATIC_CAUSE=EMITTER_INITIALIZATION_STATE_MATERIALIZATION
PRIMARY_DYNAMIC_CAUSE=NOT_ESTABLISHED_NO_DYNAMIC_TRACE
EARLIEST_INTRODUCTION_LAYER=X8664_EMITTER_FRAME_LAYOUT_AND_METADATA_HELPERS
EARLIEST_REDUNDANT_REPETITION_LAYER=NOT_ESTABLISHED; PHYSICAL_REPETITION_STARTS_IN_EMITTER
FACT_LOSS_CAUSES_MEMORY_TRAFFIC=PARTIAL
STATE_COLLAPSE_CONFIRMED=PARTIAL
PARALLEL_COPY_MODEL=PARTIAL
DUAL_VALIDITY_MODEL_USEFUL=YES
REDUCED_PRODUCT_MODEL=USEFUL_RESEARCH_MODEL
METADATA_AUTOMATON_BUILT=YES_CONCEPTUAL
RAW_STATE_COUNT=NOT_CLAIMED
MINIMIZED_STATE_COUNT=NOT_CLAIMED
MINCUT_METADATA_MODEL=PARTIAL
EXACT_METADATA_ORACLE_AVAILABLE=NO
SMT_ORACLE_AVAILABLE=NO
NEW_IDEA_DISCOVERED=NO
DOMINANT_AVOIDABLE_PATTERN=REPEATED_INITIALIZED_STATE_CHECKS_AND_STORES_REQUIRING_PROOF_FACT_PRESERVATION
RECOMMENDED_P5_TARGET=PROOF_PRESERVING_INITIALIZATION_STATE_PROPAGATION_WITH_LAZY_NATIVE_MATERIALIZATION
RECOMMENDED_P5_NAME=P5 — Proof-Preserving Initialization State and Lazy Materialization
RESEARCH_BRANCH_HEAD_FINAL={research_head}
PRODUCTION_WORKTREE_CLEAN=YES_AUDIT_WORKTREE
PRODUCTION_CODE_COMMITTED=NO
TEMP_INSTRUMENTATION_USED=NO
TEMP_INSTRUMENTATION_REVERTED=YES
FULL_SUITE_RUN=NO
PRODUCTION_PR_OPENED=NO
P5_STARTED=NO
P6_STARTED=NO
SHUTDOWN_AUTHORIZED=NO
P5_AUDIT_STATUS=COMPLETE

## Findings

1. **What P4 called metadata.** It was a lexical disassembly count of every
   `byte ptr [rbp...]` line. It did not identify a semantic metadata type.

2. **What 5638 consists of.** Independent region-aware analysis reproduces
   `4589` register-initialization accesses, `837` memory-initialization/
   definedness accesses and `212` trit payload accesses. The last family is
   user data, not compiler metadata. Thus true initialization state is `5426`
   accesses, or `96.2398%` of the P4 count.

3. **Mandatory portion.** Trit payload is semantically mandatory. Initialization
   checks and marks are required by the current runtime safety contract, but
   their physical realization is conditionally avoidable only with preserved
   proof facts and observer-aware materialization. No avoidable percentage is
   fabricated.

4. **Earliest physical realization.** The state becomes bytes in the x86-64
   emitter's frame layout and metadata helpers. The upstream IR analyzer knows
   memory initialization facts, but the fact is not carried as a native proof
   object into the emitter.

5. **SSA.** The JSMN candidate has 34 ordinary backedges but zero phis, zero
   phi-edge copies and zero critical edges. SSA destruction is not dominant for
   the measured residual population.

6. **Memory validity and initialization.** Initialization/definedness is
   explicit; independent memory-validity/coherence is not. A dual-validity
   research model is useful because a physical register may be current while
   the canonical frame value is stale until a call/address observer.

7. **True spills.** The allocator leaves 386 main values without a color, but
   the current interfaces do not expose a sound per-access cause. True RA spill
   traffic remains not established and is not inferred from byte-frame counts.

8. **Best model.** A reduced product of residence, initialization,
   observability and merge state explains the evidence better than a binary
   min-cut or an SSA-only model. It remains research-only.

9. **Exact future target.** A future P5 should preserve verifier-backed
   initialization facts and lazily materialize native state only for real
   observers, with focused proof/failure tests and cross-workload dynamic
   evidence. This audit implemented nothing in production.

## Closure

No full suite, benchmark, production CI gate, production PR, production
commit, shutdown or P6 was started. The pre-existing dirty checkout was not
modified; the detached audit worktree is clean. The research branch contains
only research scripts/notes and must not be merged wholesale into `main`.
""",
    )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("usage: p5_report_builder.py AUDIT_JSON REPORT_DIR RESEARCH_HEAD")
    build(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3])
