# Milestone 1.38 - S3 Docker V1 Capability Closure

M1.38 provides a real Docker provider around the S3 project model. The
provider has two explicit modes: daemonless `plan` and `inspect`, plus real
Docker CLI `version`, `build`, and `run` operations. Every operation exposes
the exact argv and return status; no host paths or ambient environment values
are added implicitly.

Project contexts are deterministic. Source files are copied in sorted logical
path order, the generated recipe is stable, and the manifest entrypoint is
mapped to the container path. The public CLI surface is:

```text
s3 container inspect PROJECT --image IMAGE
s3 container plan PROJECT --image IMAGE
s3 container build PROJECT --image IMAGE
s3 container run PROJECT --image IMAGE
```

The real closure requires evidence for daemonless planning, Docker version,
deterministic build context, `docker build`, `docker run`, an S3 application
running in the container, foreign-helper integration, and native non-Docker
regression. GPU capability is declaration/passthrough only; this milestone does
not implement a GPU backend.

M1.38 remains the supported Docker CLI compatibility integration. The future
container boundary is documented in `docs/container-backend-architecture.md`:
`DockerCliBackend` preserves this provider, while `S3OciBackend` is an
experimental contract-only path and is not yet functional or the default.
