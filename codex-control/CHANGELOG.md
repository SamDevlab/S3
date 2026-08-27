# Codex control changelog

## Revision 1 — 2026-08-27

Initial live control plane created for Stage1 semantic lowering v2.

- active stage: `01_PRECHECK_AND_IMPORT`;
- S3IR2 v2 frozen;
- stages 01–11 defined;
- automatic advancement allowed between ungated stages;
- canonical Stage1 mutation not authorized;
- SELF_EMIT not authorized;
- Stage2 not authorized;
- Stage3 not authorized;
- T4 not authorized;
- PR #268 remains the implementation target;
- PR #270 remains semantic handoff/reference and must not be merged by Codex;
- control branch must be consumed via `git fetch` + `git show` only.
