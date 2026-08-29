# Stage1 oracle v2 audit and v3 correction

Date: 2026-08-29

## Status

```text
REV39_PROGRESS=PRESERVED
S1_2=PAUSED_FOR_ORACLE_AUDIT
S3IR2_V2=LEGACY_FROZEN_REFERENCE_NOT_ABSOLUTE_GROUND_TRUTH
S3IR2_V3=AUDITED_REFERENCE_CANDIDATE
10E12_TO_10E9_CHANGE=NOT_AUTHORIZED
```

This audit does not invalidate the hosted compiler and does not discard Rev39 native progress. It corrects the semantic reference boundary used to judge that progress.

## Frozen provenance

The original v2 handoff was created on top of:

```text
HOSTED_COMPILER_BASE=0789ad2df5f200c6b35b67d591d10e016c1a557a
V2_HANDOFF_HEAD=c12e45d646af27f85b39c391d3a7645a812b28c5
```

The c12 handoff commit is 28 commits ahead of the frozen hosted base and adds the semantic-reference layer. A valid frozen oracle must execute from one integral c12 worktree. Copying only selected `tools/` files while importing `bootstrap.s3` from another checkout is mixed provenance and is not accepted as frozen-oracle evidence.

## Confirmed v2 issues

### 1. Source bindings were synthesized as values without a proven IR link

The v2 source-binding extractor correctly marked local binding links as unresolved until lowering. The v2 stream builder then created a new `V kind=local_binding` for each local with `storage_id=-1`, rather than proving whether the binding denotes an actual IR value or storage object.

This conflated source-name identity with runtime/IR value identity and forced the native Rev39 observer to reconstruct synthetic V events that were not equivalent to the hosted lowering ontology.

### 2. The hosted lowering already distinguishes value bindings from storage bindings

For the Stage1 scalar subset:

```text
immutable scalar local -> register/logical value
mutable scalar local   -> memory/storage object
parameter              -> parameter register/logical value
```

v3 preserves that distinction instead of inventing an extra local-binding V.

### 3. Storage was under-verified

The v2 hosted-vs-native verifier did not establish a complete storage correspondence and did not strongly validate every instruction memory target through a mapped storage identity.

v3 gives every M record source provenance and includes storage in semantic conformance.

### 4. Binding identity contract was stronger than the v2 gate

The v2 contract described source binding identity as function + lexical scope + source anchor + exact identifier, while local matching in the conformance verifier was effectively function + name + type + mutability.

v3 uses the exact raw-source declaration/name anchor as the wire disambiguator. Distinct shadowed declarations therefore cannot collapse merely because their names/types match.

### 5. Raw CRLF provenance was not guaranteed

The v2 CLI used text-mode `Path.read_text()`. Python universal-newline handling can normalize CRLF to LF before source SHA/byte count/anchor accounting, while the native Stage1 reads raw bytes.

v3 uses `Path.read_bytes()`, computes SHA256 and byte count over those exact bytes, then decodes the current ASCII self-hosting subset without newline normalization.

### 6. S1.2 semantic equivalence and S1.6 canonical identity were conflated

The v2 conformance gate explicitly allowed candidate ValueIds to differ from hosted ValueIds. Later Rev39 direction also required byte-identical V streams/hashes. Those are different contracts.

v3 defines:

```text
S1.2 = semantic conformance, numeric producer IDs may differ
S1.6 = canonical ID assignment + canonical record order + byte identity + SHA
```

S1.6 is intentionally not claimed by the v3 semantic oracle.

### 7. Serialization order was influencing compiler architecture

The v2 encoder grouped all F, then all B, all V, all M, all I/O/R, all C/A and all T records. At the same time, the handoff instructed Stage1 to lower and emit semantics incrementally.

v3 conformance does not treat producer record order as semantic identity. Canonical record ordering belongs to S1.6, after semantic correctness is proven.

### 8. v2 type breadth exceeded its lossless wire payload

The v2 type table included f64/string/dynamic types, but its I record only preserved integer immediates in `aux_b`, and CONST_STR did not carry a lossless string payload identity.

v3 is explicitly a bootstrap-subset stream and fails closed on `CONST_STR` and f64 immediates until a lossless representation is specified.

### 9. `discard 0` hosted O0 semantics

The frozen hosted lowering lowers a non-call discard expression normally. Integer literals lower to CONST, and O0 does not run dead pure-instruction elimination. Therefore the frozen hosted reference expects `discard 0` to create a constant logical value/instruction.

Any Rev39 observation claiming the opposite must be treated as stale/mixed-provenance evidence until independently reproduced.

### 10. 10^12 is not proven to exceed an i64/native boundary

The language i64 domain is signed 64-bit. The x86-64 backend emits large immediates with `movabs` and uses signed 64-bit comparisons. No architectural evidence supports replacing a 10^12 packing base with 10^9 merely to make a probe pass.

The prior proposed change remains diagnostic-only and is not authorized as a fix.

## v3 ontology

```text
D = source binding identity
    -> must target V or M

V = logical IR/runtime value
    parameter | constant | instruction_result

M = logical storage object
    source provenance + type + length + mutability

I/O/R = instruction graph and def/use
C/A   = calls and ordered arguments
T     = complete terminators
```

A binding name is not automatically a value.

## v3 wire format

Header:

```text
S3IR2 3
```

Records:

```text
F function_id kind name_start name_length parameter_count result_count
B function_id block_id ordinal instruction_count terminator_instruction_id
D binding_id function_id kind type_code name_start name_length mutable target_kind target_id
V value_id function_id kind type_code anchor_start anchor_length mutable storage_id
M function_id storage_id type_code length mutable anchor_start
I instruction_id function_id block_id ordinal opcode result_count operand_count aux_a aux_b
O instruction_id ordinal value_id
R instruction_id ordinal value_id
C instruction_id callee_kind callee_function_id callee_name_start callee_name_length argument_count result_count
A instruction_id ordinal value_id
T instruction_id kind condition_value_id target_negative target_zero target_positive return_value_id
Z semantic_completeness_mask
```

`Z 15` means S1-S4 semantic completeness only.

## Resource Discipline

The oracle correction also adopts the current project policy:

```text
MEASURE
RESPECT
ADAPT
PROVE
```

Streaming remains a validated technique for the current Stage1 resource contract, not a universal compiler law. No v3 semantic rule requires globally O(1) compiler memory. Hard configured resource limits remain gates.

## Independent canaries

`tests/test_stage1_semantic_stream_v3.py` covers:

- raw CRLF SHA/byte identity;
- `discard 0` retaining CONST semantics at O0;
- immutable local -> real V link;
- mutable local -> real M link;
- exact 10^12 i64 immediate preservation;
- self-generated v3 semantic conformance;
- fail-closed unknown binding storage target;
- hosted-vs-candidate rejection when storage shape is mutated.

These tests are intentionally focused on the failure modes uncovered by the audit rather than only round-tripping the oracle against itself.

## Rev39 migration rule

Do not reset or discard Rev39. Do not blindly replay all v2 special cases either.

After v3 hosted qualification:

1. preserve the current frozen Rev39 source and evidence;
2. classify existing Rev39 V events into real V, binding D, or storage M;
3. remove only synthetic local-binding V behavior that v3 proves obsolete;
4. add v3 D/M emission primitives to the native candidate;
5. qualify focused fixtures against semantic v3 conformance;
6. re-run canonical Stage1 only after focused fixtures pass;
7. resume from the first real semantic divergence under v3;
8. keep S1.6 canonical serialization as a later independent gate.

## Promotion boundary

No claim in this branch authorizes SELF_EMIT, Stage2, Stage3, T4 or S1.6.

Required before Rev39 resumes:

```text
V3_PYTHON_COMPILE=PASS
V3_CANARY_TESTS=PASS
V3_RAW_CRLF=PASS
V3_BINDING_TO_VALUE=PASS
V3_BINDING_TO_STORAGE=PASS
V3_STORAGE_MUTATION_REJECTION=PASS
V3_1E12_IMMEDIATE=PASS
```

Then the next task is native Rev39 migration from v2 semantics to v3 semantics, preserving all already-valid parsing/lowering work.
