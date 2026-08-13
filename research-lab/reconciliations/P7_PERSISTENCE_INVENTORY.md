# P7 persistence inventory

This inventory records the P7 checkpoint before PR #177 is promoted into the
durable research branch.

## Git anchors

```text
P7_IMPLEMENTATION_HEAD=b118917ec5a5284899d27b1838712b2e04364caf
P7_MERGE=631b51e70562a33183ac14d0be5bbe2ddd140779
P7_RESEARCH_CHECKPOINT=e91e13fc307f94a40f4103d6c67e6f0951245ebd
TARGET_MAIN_SHA=631b51e70562a33183ac14d0be5bbe2ddd140779
```

## Required durable files

The following files were present on the current research checkpoint and are
preserved in the reconciled PR branch:

| Path | SHA-256 at checkpoint |
|---|---|
| `research-lab/STATE.json` | `7EE4641CA26C31B783CE15E1A13EF032FDB1007FFB12A2DEFA68C7B769D6C8ED` |
| `research-lab/HANDOFF.md` | `7019179AD178BD5F88D2810DB849F4D28839ADBEE54CF3482D551A63CC73B6A8` |
| `research-lab/NEW_CHAT_PROMPT.md` | `DB43B802DF86033F00CACD6798F51C097C98AB86F3E486AB9DC7690EBDAC9F59` |
| `research-lab/SESSION_LOG.md` | `CC3DB4A541858E0EC4278A5EF050167E017D5054BDF9E3A6A2AE8772AA5FD8AB` |
| `research-lab/zettelkasten/INDEX.md` | `1B8BF96599CB7CDF9F02B81E1F95652A0321B84AFD6AFF67B37A646516833E80` |
| `research-lab/experiments/README.md` | `5A73523709082A8FC2CDC6938912D921D45B4FFF4829FADD1D651E2069C32AC3` |
| `research-lab/reconciliations/P7_NECESSARY_VS_ACCIDENTAL_20260813.md` | `C0E360B613040052954AF4F13FBA5A9909A20C5B0A2FB9186E93E07F018BEC39` |
| `research-lab/zettelkasten/notes/S3-ZK-0049.md` | `114BE791A5B50160FA93F768D1F31521AB2496FB74A2C47A7878704E0FB10CAF` |

## P7 state

`STATE.json` still records P7 as complete, with PR 176, the implementation
head, merge commit, CI PASS, Linux full-suite-equivalent exit 0, P8 false, and
shutdown unauthorized. The newer P7 experiment `S3-EXP-0026` and Zettelkasten
note `S3-ZK-0049` are retained.

## Reconciliation scope

The eight files changed by the P7 research checkpoint have no path intersection
with the 17 original PR #177 paths. The reconciled result is therefore a union:
P7 persistence plus the restored Zettels, EXP-0016, provenance policy,
historical-roadmap labeling, and validator from #177.
