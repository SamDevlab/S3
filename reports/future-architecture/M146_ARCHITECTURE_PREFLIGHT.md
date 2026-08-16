# M1.46 Architecture Preflight

Status: `CLOSED_FOR_IMPLEMENTATION`.

The runner uses the existing project model and a convention-based test
entrypoint. Test units are discovered from the locked project graph in stable
node/path order; no new scripting language or test syntax is introduced.

The entrypoint returns the existing structured result/error form. A test is
`pass`, `fail`, or `skip`; skip is explicit and never inferred from a crash.
Timeouts are integer milliseconds, with a deterministic default of 10,000 ms.
The seed is fixed by the project lockfile and may be overridden only by an
explicit CLI argument recorded in the report.

Hosted execution is the reference for portability. Native execution is a
required differential gate on Linux x86-64, not a separate source of
semantics. Capability and resource limits are declared by the project and
denials are reported as failures unless the test explicitly expects denial.

The versioned report contains project identity, test identity, mode, status,
duration, diagnostics, seed, timeout, and capability outcome. Exit status is
zero only when all selected tests pass or are explicitly skipped; discovery,
timeout, resource, and infrastructure failures are nonzero.
