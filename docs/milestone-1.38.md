# Milestone 1.38 - S3 Docker Contract

This milestone defines an immutable, deterministic Docker invocation
specification. It validates a lowercase image reference, a non-empty command,
sorted unique environment names, and an execution timeout from 1 through 3600
seconds. The resulting argv is stable and contains only the explicit Docker
runtime request.

Process execution, host filesystem mounting, image acquisition, networking,
resource limits, and platform adapters are outside this structural contract.
No implicit host paths or environment values are introduced by the model.
