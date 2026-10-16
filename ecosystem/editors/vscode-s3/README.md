# S3 Language Support for VS Code

This local-installable extension supplies `.s3` syntax coloring and connects VS
Code to the S3 repository's existing `LanguageServer` through bounded JSON-RPC
stdio. It does not include another S3 parser or bundle a compiler copy.

Requirements:

- Python 3.11+ available as one executable (`s3.pythonPath`, default `python`).
- An S3 checkout containing `bootstrap/s3` and `ecosystem/editors/vscode_s3`.
- Open that checkout as the workspace, or set `s3.repositoryPath` to its path.

The server validates an opened S3 document and publishes compiler diagnostics.
Supported editor requests are document symbols, hover, definition, references,
workspace symbols across open documents, and formatting through the existing
conservative formatter. Positions crossing non-BMP Unicode are converted
between VS Code UTF-16 and the current server's code-point columns.

References and workspace symbols are limited to documents currently open in the
server. Rename is intentionally not registered because the server's analysis
does not establish a complete workspace edit for unopened files. Completion is
not registered: the current transport advertises completion in its capability
object but does not dispatch `textDocument/completion`. The extension does not
claim either feature.

Opening a file never executes it. `S3: Check Current File` validates only;
project inspection/build are compile-only; `S3: Run Project (Explicit)` is the
only contributed command that executes S3 code, through the existing hosted
project tooling. Native execution and FFI are not implied by this extension.

To create a VSIX locally, from the repository root run:

```text
python -m ecosystem.editors.vscode_s3.package_vsix
```

The default output is `ecosystem/editors/vscode-s3/dist/s3-language-0.1.0.vsix`.
Install it manually with VS Code's `Install from VSIX...` command. This project
does not publish to the Marketplace.
