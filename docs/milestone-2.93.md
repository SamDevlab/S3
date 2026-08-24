# Milestone 2.93: Native Emission Boundary

M2.93 introduces an explicit plan boundary between verified S3 Assembly and a
host assembler/linker. The plan is deterministic, target-labelled and
fail-closed, but does not invoke a host tool.

## Contract

- supported targets are explicit: `x86_64`, `aarch64`, `macos_arm64`;
- Assembly is verified before a native plan is created;
- `host_tool_required` is always true for this milestone;
- no native artifact is produced by the candidate;
- unsupported targets fail without fallback.

## Non-claims

M2.93 does not invoke an assembler or linker, produce native objects, replace
existing native backends, claim native self-hosting or run global T4. Host
tool invocation remains an explicit later boundary.
