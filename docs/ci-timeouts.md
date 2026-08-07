# Benchmark timeout scopes

Benchmark manifests use two finite timeout values:

- `timeout_seconds` limits execution of the compiled benchmark program and
  defaults to 30 seconds for compatibility with existing manifests.
- `build_timeout_seconds` limits compiler subprocesses and defaults to 60
  seconds. It can be set per implementation when a legitimate compiler needs
  more time.

Both values must be positive. A timeout still terminates the subprocess and
preserves the existing timeout error and cleanup behavior; neither field can
disable the timeout or request an infinite duration.
