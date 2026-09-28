# S3 1.11 Evidence Retention Policy

The campaign keeps source, tests, compact result JSON, protocol metadata,
hashes, and summaries needed to audit each conclusion. Large derived dumps are
not committed automatically when the pinned source, tool, command, and a
content hash are enough to reproduce them. Local working copies are preserved;
this policy does not delete or rewrite them.

## Retained locally, excluded from publication

The three full native-observatory JSON dumps are regenerable from the frozen
S3 control and workload inputs. Their compact observatory summaries and
experiment-specific derived reports are retained separately.

| Local artifact | Bytes | SHA-256 | Publication decision |
| --- | ---: | --- | --- |
| `evidence/control-832b/observatory/energy-native-observatory-v1.json` | 4,774,158 | `dfb19b4d779700ac181ad89bc786e9e26da31e072029c9af94adc0db0ca2943e` | Keep local; regenerate from pinned control if needed |
| `evidence/control-832b/observatory/point-cloud-native-observatory-v1.json` | 7,309,747 | `17f4224028cbebaf541ab2dbc40a4558b3dd046d01a8ce464b6a5cdd0ce29fa2` | Keep local; regenerate from pinned control if needed |
| `evidence/control-832b/observatory/raster-native-observatory-v1.json` | 8,736,986 | `2f959824c289f72e873ab5853e87eb45b185427ec67ce73c839f0f7061d01a8a` | Keep local; regenerate from pinned control if needed |
| `evidence/EXP-S3-111-LIVE-001.json` | 831,065 | `73570e15bcccef6f6944a2bec23ee1bfa08a5897e7e3d82539e385841c86f398` | Keep local; publish the compact findings and reproducible tool/test instead |

The observatory dumps total 20,820,891 bytes. The four excluded artifacts total
21,651,956 bytes. They remain in the local campaign worktree and must not be
removed as part of publication preparation. Their compact summaries, exact
experiment JSON, source/tool provenance, and decisions remain the reviewable
evidence surface.

## Publication rule

Publish concise experiment results and evidence that carries independent
scientific value, including negative outcomes and exact hashes. Before making
the Draft PR, compute the selected commit's file count, total bytes, and largest
files; confirm the four artifacts above are not staged. Raw evidence may be
added later only when a reviewer cannot reproduce or audit the conclusion
without it.
