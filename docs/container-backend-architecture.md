# Container Backend Architecture

S3 keeps the M1.38 Docker integration as a supported compatibility backend.
The container boundary is now explicit:

```text
ContainerBackend
├── DockerCliBackend   (qualified compatibility backend)
└── S3OciBackend       (experimental contract-only backend)
```

`DockerProvider` remains available for existing callers and is the underlying
implementation of `DockerCliBackend`. Docker build, run, inspect, planning,
and interoperability are not removed or replaced.

## Backend Selection

Container operations accept `--backend docker`, `--backend s3`, or
`--backend auto`. The compatibility default remains `docker` so existing
commands keep their behavior. `auto` selects Docker while the S3 OCI backend
is not qualified and records:

```text
CONTAINER_BACKEND=docker
FALLBACK_REASON=S3_OCI_BACKEND_NOT_QUALIFIED
```

The S3 backend is never silently substituted. Explicit `--backend s3` can
produce the deterministic structural plan, but image build and runtime fail
closed until its own gates pass. No S3 OCI backend is currently declared
functional or the default.

## OCI Contract Boundary

The experimental backend defines deterministic contracts for:

- source filesystem layer plans with sorted logical paths;
- SHA-256 OCI descriptors with validated size and digest fields;
- timestamp-free canonical image configuration;
- canonical OCI image manifests and layout/index documents;
- deterministic archive member ordering for a future OCI layout/tar export.

These contracts do not implement a container runtime, namespaces, cgroups,
overlay filesystems, networking, or a Docker daemon. Actual OCI blob/tar
generation and runtime qualification are a future S3 Container V2 line after
the M3.00 self-hosting gates.

## Test Classes

Container tests should remain separated into:

- `S3_CONTAINER_CORE`: deterministic plans and backend selection;
- `S3_OCI_BUILD`: canonical OCI contracts and future artifact generation;
- `DOCKER_INTEROPERABILITY`: real Docker CLI build/load/run/inspect evidence.

An unavailable Docker daemon defers only the interoperability class. It does
not turn the daemonless core or structural OCI contract tests into failures.
