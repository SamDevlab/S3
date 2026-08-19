# M1.84 Architecture

M1.84 exposes filesystem and process operations as explicit async Future
factories. Filesystem paths are relative to an injected root and are resolved
with traversal checks. Reads, writes, argument counts, stdin, stdout, and
stderr are bounded by a single immutable I/O budget.

Process execution accepts an executable plus an argv tuple and always invokes
the host with `shell=False`. A shell request is rejected rather than silently
interpreted. Timeouts and output overflow become explicit failed Future
results. The service never returns an unbounded host buffer or a borrowed
handle; the Future owns the returned bytes and deterministic frame cleanup
remains authoritative.

The implementation is a hosted adapter over the existing OS boundary. It does
not claim kernel-native async completion, and no native ARM certificate is
manufactured when that environment is unavailable.
