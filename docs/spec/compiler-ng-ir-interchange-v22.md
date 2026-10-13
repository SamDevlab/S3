# S3C-NG IR Interchange V22

V22 preserves canonical basic-block names and the canonical absence of the
scalar `result` field on discarded and value-projected calls across hosted and native S3C-NG
transport. It retains earlier record contracts, adds one kind-28 descriptor
for every kind-9 block record, and uses a sparse kind-29 descriptor for each
result-producing call whose canonical scalar `result` field is absent.

The eight signed 64-bit cells are:

| Cell | Meaning |
| --- | --- |
| 0 | Record kind, `28` |
| 1 | Function index |
| 2 | Block index |
| 3 | Stable block-name template ID |
| 4 | Per-function block-name counter suffix |
| 5-7 | Reserved; must be zero |

Template ID `0` denotes `entry` and is valid only for block index `0` with
suffix `-1`. IDs `1` through `13` denote, respectively, `rel_neg_`,
`rel_zero_`, `rel_pos_`, `rel_cont_`, `switch_negative_`, `switch_neutral_`,
`switch_positive_`, `switch_continue_`, `while_condition_`, `while_body_`,
`while_exit_0_`, `while_exit_1_`, and `while_exit_`. For non-entry blocks, the
explicit suffix must equal the block index minus one, matching the reference
lowerer's per-function block counter.

Every V22 block must have exactly one descriptor. Function and block identities
must refer to declared objects, names must be unique within a function, and
unknown templates, malformed descriptors, or missing descriptors are rejected.
Branch and jump records continue to carry numeric block identities; the decoder
resolves them through the explicit V22 name descriptors.

Kind 29 carries the absent-field distinction for a `CALL` whose result cells
are still present. This includes a call materialized through a typed value
projection, even when the value has only one cell. The eight signed 64-bit cells are:

| Cell | Meaning |
| --- | --- |
| 0 | Record kind, `29` |
| 1 | Function index |
| 2 | Instruction index within that function |
| 3-7 | Reserved; must be zero |

The descriptor must identify an existing `CALL` with at least one result cell;
duplicate descriptors, unknown identities, and descriptors on other opcodes
are rejected. Without this descriptor, the scalar `result` transported for
register identity remains the canonical `result` field. With it, the decoder
retains the result cells but reconstructs canonical `result=None`. This is
structural metadata only and does not change call execution. Older versions do
not accept kind 29 and retain their existing inference rules.

V1-V21 streams remain decodable under their existing contracts. Since those
versions do not carry block names, their non-entry blocks retain the historical
synthetic `bN` labels. V22 never falls back to synthesized labels.
