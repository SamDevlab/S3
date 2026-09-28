# S3 1.11 Optimization Pareto Findings

The comparison is multi-objective and workload-specific. Static code size,
instruction counts, memory traffic, pressure, and timing are not collapsed into
one score. Timing is characterization only; no result changes O1, PER, or a
production default.

| Candidate | Static native effect | Memory / pressure effect | Timing evidence | Pareto conclusion |
| --- | --- | --- | --- | --- |
| Dominating SSA value substitution (`VALUE-COST-001`) | `.text` -350/-350/-942 bytes; instructions -26/-26/-78; memory refs -10/-10/-3 | Raster peak-live +1 and stack-resident values +16; guard rejects raster | No material change established | Structurally attractive for energy/point-cloud; raster is pressure-dominated and must be rejected by the current guard |
| STORE→LOAD forwarding (`VALUE-COST-002`) | `.text` -758/-3007/-437 bytes | Memory refs +48/+3/+228; peak-live +3/+5/+3; stack residency +35/+30/+133 | Point-cloud material characterization signal reproduced on exact binaries; earlier S3 run below threshold | Trade-off, not a general Pareto improvement; conservative guard rejects all three |
| Same-color TMOV body omission (`MOVE-COALESCE-002`) | `.text` -42/-102/-36 bytes; instructions -14/-34/-12 | Allocator proves source/destination color equality; PER checks retained; no measured pressure delta | No material timing change | Strongest consistent structural-only candidate; no runtime promotion |
| Point-cloud address recurrence (`ADDR-RECURRENCE-001`) | `.text` +408; instructions +32; memory refs +8; branches +12; stack refs +9; frame +16 bytes | Peak-live unchanged at 7; stack-resident remains 0 | 95% interval [0.9801, 1.1053], inconclusive | Rejected for this workload because every reported structural dimension worsened |
| Profile-selected hot fallthrough (`HOT-FALLTHROUGH-001`) | Branches -1; instructions -1; `.text` -2 bytes | Memory refs, stack refs, frame, and ELF bytes unchanged | 21 paired samples; baseline/candidate median ratio 1.0261; 95% interval [0.9727, 1.0428], no material change within ±5% | Small structurally supported control-layout result; no general runtime benefit established |

The STORE→LOAD stack-residency deltas are the exact per-workload values from
`EXP-S3-111-VALUE-COST-002.json`; static stack residency is not a dynamic spill
counter.

## Decision

No tested candidate dominates all measured axes with a replicated material
runtime benefit. Same-color copy omission is the cleanest structural
improvement, while pressure-aware value locality remains the most important
optimization question because it exposes both safe structural wins and a
workload-specific timing/pressure trade-off. Neither is wired into production.
