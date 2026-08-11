# Milestone 1.37 - Project Container Model

M1.37 provides a deterministic project-container boundary for hosted S3
applications. A project is described by `s3.toml` and can be checked,
inspected, compiled, emulated, and converted into a stable container plan.

The manifest records the project name, version, module entrypoint, source
roots, profile, dependencies, foreign libraries, external executables,
environment, services, capabilities, and container metadata. Source discovery
is deterministic: roots and files are normalized and ordered before
compilation.

Capabilities are explicit in the manifest. A `true` value is represented as
`enforced`; a `false` value remains `declared` until a host adapter provides
the corresponding enforcement. The plan is descriptive and deterministic; it
does not silently execute host services or invoke a shell.

Example:

```toml
[project]
name = "scientific_app"
version = "1.0.0"
entrypoint = "main"
source_roots = ["src"]
profile = "hosted"

[capabilities]
"filesystem.read" = true
"process.spawn" = false
```

The project tooling is intentionally daemonless. Runtime host access remains
owned by the explicit M1.36 host-services provider, while packaging and image
generation are future work.
