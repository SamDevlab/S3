# Getting started

Run commands from the repository root with Python 3.11 or newer. The tested
baseline is Python 3.13 on Windows; the application lab rejects a checkout whose
`bootstrap/s3` differs from its pinned compiler commit.

```powershell
python -m ecosystem.devtools commands
python -m ecosystem.devtools project init .\scratch\hello --name hello
python -m ecosystem.devtools project inspect .\scratch\hello
python -m ecosystem.devtools project build .\scratch\hello
python -m ecosystem.devtools project run .\scratch\hello
python -m ecosystem.devtools source check .\scratch\hello\src\main.s3
python -m ecosystem.devtools source format .\scratch\hello\src\main.s3
python -m ecosystem.devtools source docs .\scratch\hello\src\main.s3
```

`project run` is explicit and executes through the existing hosted project
tooling. Merely opening a file in VS Code never runs it. `commands` prints the
actual pinned CLI's help; the toolkit does not claim unsupported CLI options.

List and validate the independent applications:

```powershell
python -m ecosystem.application_lab list
python -m ecosystem.application_lab run
python -m ecosystem.application_lab run graph-path-report --mode compile-only
python -m ecosystem.application_lab run --mode native
python -m ecosystem.application_lab run --mode ffi
```

Hosted runs compare actual results to each manifest's expected integer and
report compiler, source, fixture, and package-source hashes. `native` and `ffi`
are distinct modes; on an unsupported host they return
`UNSUPPORTED_ENVIRONMENT`, not `PASS`.

The `ffi-native-library` example is intentionally qualified only by
`--mode ffi`. On Linux x86-64 that command builds a temporary ELF shared object
from versioned S3 source, verifies its exported symbol, and calls it from a
separate Python `ctypes` process. Other applications report
`FFI_NOT_APPLICABLE`; the FFI example reports `NOT_APPLICABLE` in hosted,
compile-only, and standalone native modes. These outcomes are explicit skips,
not successful executions.

The existing test-runner report's `target` field is compiler target metadata;
it is not evidence that native code ran on that operating system. For hosted
results, use the explicit `execution_mode` and `host_environment` fields in the
application-lab report.

Run focused tests without invoking the historical full compiler suite:

```powershell
python -m pytest tests/ecosystem -q
python -m bootstrap.s3.cli test ecosystem/learning_path/s3-test.toml
node --test ecosystem/editors/vscode-s3/client.test.js
python -m ecosystem.editors.vscode_s3.package_vsix
```

For VS Code, open this S3 checkout or configure `s3.repositoryPath`, then
install the generated VSIX manually with “Install from VSIX…”. No Marketplace
account or network download is used. The local packager writes its artifact
under the extension's ignored `dist/` directory.
