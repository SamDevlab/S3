# Milestone 1.36 - Linux Host Services

M1.36 adds a concrete Linux provider behind an explicit dependency boundary.
`LinuxHostServices` exposes injected `argv` and environment values, UTF-8 file
read/write, captured stdin/stdout/stderr, shell-free structured process spawn,
wait and exit status, and a deterministic two-process pipe.

Commands are passed as an argument vector with `shell=False`; no `system()` or
implicit shell expansion is used. A caller can inject `cwd`, argv and the
environment for deterministic tests. The provider reports a closed capability
set and raises `HostServiceError` for invalid or unavailable operations.

The E2E helper accepts arguments, reads stdin, emits stdout/stderr and can
return a configured non-zero status. Tests cover ARGV, ENV, STDIO, FILES,
SPAWN, WAIT, EXIT_STATUS and PIPE on Linux and Windows-compatible Python
hosts. Windows-specific process policy is not part of this Linux-first
milestone.
