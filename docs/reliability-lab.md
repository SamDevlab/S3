# S3 Reliability Lab

This is an experimental, isolated harness for trying to break the compiler;
it is not a compiler change and is not a correctness proof. Generation is
bounded and deterministic by seed. Valid and malformed source generators,
deterministic mutators, O0/O1 differential execution, failure classification,
bounded minimization, JSON campaign reports, and replay are exposed by
`tools/reliability_lab.py`.

The first supported oracle compares O0 and O1 `run_source` results. A malformed
case passes when the compiler rejects it without an uncaught harness failure.
Timeouts are bounded at the harness boundary; future subprocess runners may
add stronger process isolation. Reports use stable source SHA and failure
signatures, never PID, timestamps, or absolute paths. Generated programs do
not invoke shell, network, filesystem mutation, or child processes.

Example: `python tools/reliability_lab.py campaign --valid 100 --malformed 100
--report reports/reliability/first-campaign.json`. Replay uses a saved case
directory containing `input.s3` and `metadata.json`. No Quantum or OCI inputs
are included in this initial campaign.
