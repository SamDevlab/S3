"use strict";

const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { JsonRpcClient } = require("./client");
const { toServerPosition, toClientRange } = require("./positions");

const SERVER_MODULE = "ecosystem.editors.vscode_s3.server";
const TOOLKIT_MODULE = "ecosystem.devtools";
let stopActiveServer = null;

function isS3Repository(root) {
  return fs.existsSync(path.join(root, "bootstrap", "s3", "lsp.py")) &&
    fs.existsSync(path.join(root, "ecosystem", "editors", "vscode_s3", "server.py"));
}

function repositoryFor(vscode, document) {
  const configured = vscode.workspace.getConfiguration("s3").get("repositoryPath", "");
  if (configured) return path.resolve(configured);
  const folder = vscode.workspace.getWorkspaceFolder(document.uri);
  if (folder && isS3Repository(folder.uri.fsPath)) return folder.uri.fsPath;
  return null;
}

function mapDiagnostic(vscode, document, item) {
  const range = toClientRange(document, item.range, vscode);
  const severity = item.severity === 2 ? vscode.DiagnosticSeverity.Warning :
    item.severity === 3 ? vscode.DiagnosticSeverity.Information :
      item.severity === 4 ? vscode.DiagnosticSeverity.Hint : vscode.DiagnosticSeverity.Error;
  const diagnostic = new vscode.Diagnostic(range, item.message || "S3 diagnostic", severity);
  diagnostic.source = item.source || "s3";
  if (typeof item.code === "string" || typeof item.code === "number") diagnostic.code = item.code;
  return diagnostic;
}

function lspLocation(vscode, documents, location) {
  const document = documents.get(location.uri);
  const uri = vscode.Uri.parse(location.uri);
  const range = document ? toClientRange(document, location.range, vscode) :
    new vscode.Range(
      location.range.start.line,
      location.range.start.character,
      location.range.end.line,
      location.range.end.character,
    );
  return new vscode.Location(uri, range);
}

async function activate(context) {
  const vscode = require("vscode");
  const output = vscode.window.createOutputChannel("S3 Language Server");
  const diagnostics = vscode.languages.createDiagnosticCollection("s3");
  const documents = new Map();
  const disposables = [output, diagnostics];
  let activeClient = null;
  let clientReady = false;
  let repositoryRoot = null;
  let serverCapabilities = {};
  let providersRegistered = false;

  const pythonPath = () => vscode.workspace.getConfiguration("s3").get("pythonPath", "python");
  const writeOutput = (text) => output.appendLine(String(text).replace(/[\r\n]+$/, ""));

  function clientForRequest() {
    if (!activeClient) throw new Error("S3 language server is not running");
    return activeClient;
  }

  async function request(method, params) {
    try {
      return await clientForRequest().request(method, params);
    } catch (error) {
      writeOutput(`${method}: ${error.message}`);
      return null;
    }
  }

  function notifyOpen(document) {
    if (!clientReady || !activeClient || document.languageId !== "s3") return;
    documents.set(document.uri.toString(), document);
    activeClient.notify("textDocument/didOpen", {
      textDocument: {
        uri: document.uri.toString(),
        languageId: "s3",
        version: document.version,
        text: document.getText(),
      },
    });
  }

  async function stopServer() {
    const oldClient = activeClient;
    activeClient = null;
    clientReady = false;
    serverCapabilities = {};
    diagnostics.clear();
    if (oldClient) await oldClient.stop();
  }

  async function startServer() {
    const editor = vscode.window.activeTextEditor;
    const sourceDocument = editor && editor.document.languageId === "s3"
      ? editor.document
      : vscode.workspace.textDocuments.find((item) => item.languageId === "s3");
    if (!sourceDocument) return false;
    repositoryRoot = repositoryFor(vscode, sourceDocument);
    if (!repositoryRoot || !isS3Repository(repositoryRoot)) {
      vscode.window.showWarningMessage(
        "S3 support needs an S3 checkout. Set s3.repositoryPath to the checkout root; source execution is never automatic.",
      );
      return false;
    }
    const child = spawn(pythonPath(), ["-m", SERVER_MODULE], {
      cwd: repositoryRoot,
      shell: false,
      windowsHide: true,
      stdio: ["pipe", "pipe", "pipe"],
    });
    const client = new JsonRpcClient(child);
    client.on("stderr", (text) => writeOutput(text));
    client.on("serverError", (error) => writeOutput(error.message));
    client.on("serverExit", ({ code }) => {
      if (activeClient === client) {
        activeClient = null;
        clientReady = false;
        diagnostics.clear();
        writeOutput(`language server exited with status ${code}`);
      }
    });
    activeClient = client;
    const initializeTimeout = setTimeout(() => child.kill(), 10000);
    try {
      const response = await client.request("initialize", {
        processId: process.pid,
        rootUri: vscode.Uri.file(repositoryRoot).toString(),
        capabilities: {},
      });
      serverCapabilities = response && response.capabilities ? response.capabilities : {};
      client.notify("initialized", {});
      client.onNotification("textDocument/publishDiagnostics", (params) => {
        const document = documents.get(params.uri);
        if (!document) {
          diagnostics.delete(vscode.Uri.parse(params.uri));
          return;
        }
        const items = Array.isArray(params.diagnostics) ? params.diagnostics : [];
        diagnostics.set(
          document.uri,
          items.map((item) => mapDiagnostic(vscode, document, item)),
        );
      });
      clientReady = true;
      for (const document of vscode.workspace.textDocuments) notifyOpen(document);
      output.appendLine(`S3 language server ready (${response.serverInfo?.name || "unknown"})`);
      return true;
    } catch (error) {
      activeClient = null;
      await client.stop();
      writeOutput(`could not start language server: ${error.message}`);
      vscode.window.showErrorMessage(`Could not start S3 language server: ${error.message}`);
      return false;
    } finally {
      clearTimeout(initializeTimeout);
    }
  }

  function registerProviders() {
    if (providersRegistered) return;
    providersRegistered = true;
    if (serverCapabilities.documentSymbolProvider) {
      disposables.push(vscode.languages.registerDocumentSymbolProvider("s3", {
        async provideDocumentSymbols(document) {
          const symbols = await request("textDocument/documentSymbol", {
            textDocument: { uri: document.uri.toString() },
          });
          if (!Array.isArray(symbols)) return [];
          const kinds = {
            10: vscode.SymbolKind.Enum,
            12: vscode.SymbolKind.Function,
            23: vscode.SymbolKind.Struct,
          };
          return symbols.map((item) => new vscode.DocumentSymbol(
            item.name,
            item.detail || "",
            kinds[item.kind] || vscode.SymbolKind.Variable,
            toClientRange(document, item.range, vscode),
            toClientRange(document, item.selectionRange, vscode),
          ));
        },
      }));
    }
    if (serverCapabilities.hoverProvider) {
      disposables.push(vscode.languages.registerHoverProvider("s3", {
        async provideHover(document, position) {
          const value = await request("textDocument/hover", {
            textDocument: { uri: document.uri.toString() },
            position: toServerPosition(document, position),
          });
          if (!value || !value.contents) return undefined;
          return new vscode.Hover(new vscode.MarkdownString(value.contents.value || ""));
        },
      }));
    }
    if (serverCapabilities.definitionProvider) {
      disposables.push(vscode.languages.registerDefinitionProvider("s3", {
        async provideDefinition(document, position) {
          const values = await request("textDocument/definition", {
            textDocument: { uri: document.uri.toString() },
            position: toServerPosition(document, position),
          });
          return Array.isArray(values) ? values.map((item) => lspLocation(vscode, documents, item)) : [];
        },
      }));
    }
    if (serverCapabilities.referencesProvider) {
      disposables.push(vscode.languages.registerReferenceProvider("s3", {
        async provideReferences(document, position) {
          const values = await request("textDocument/references", {
            textDocument: { uri: document.uri.toString() },
            position: toServerPosition(document, position),
            context: { includeDeclaration: true },
          });
          return Array.isArray(values) ? values.map((item) => lspLocation(vscode, documents, item)) : [];
        },
      }));
    }
    if (serverCapabilities.workspaceSymbolProvider) {
      disposables.push(vscode.languages.registerWorkspaceSymbolProvider({
        async provideWorkspaceSymbols(query) {
          const values = await request("workspace/symbol", { query });
          if (!Array.isArray(values)) return [];
          return values.map((item) => new vscode.SymbolInformation(
            item.name,
            item.kind === 12 ? vscode.SymbolKind.Function :
              item.kind === 23 ? vscode.SymbolKind.Struct : vscode.SymbolKind.Enum,
            item.containerName || "",
            lspLocation(vscode, documents, { uri: item.uri, range: item.range }),
          ));
        },
      }));
    }
    if (serverCapabilities.documentFormattingProvider) {
      disposables.push(vscode.languages.registerDocumentFormattingEditProvider("s3", {
        async provideDocumentFormattingEdits(document, options) {
          const values = await request("textDocument/formatting", {
            textDocument: { uri: document.uri.toString() },
            options,
          });
          if (!Array.isArray(values)) return [];
          return values.map((item) => vscode.TextEdit.replace(
            toClientRange(document, item.range, vscode),
            item.newText,
          ));
        },
      }));
    }
  }

  async function runToolkit(action, project = false) {
    if (!repositoryRoot) {
      vscode.window.showErrorMessage("Open an S3 checkout or set s3.repositoryPath first.");
      return;
    }
    const folder = vscode.workspace.workspaceFolders && vscode.workspace.workspaceFolders[0];
    const active = vscode.window.activeTextEditor && vscode.window.activeTextEditor.document;
    const target = project ? (folder && folder.uri.fsPath) : (active && active.uri.fsPath);
    if (!target) return;
    const args = project
      ? ["-m", TOOLKIT_MODULE, "project", action, target]
      : ["-m", TOOLKIT_MODULE, "source", action, target];
    const child = spawn(pythonPath(), args, {
      cwd: repositoryRoot,
      shell: false,
      windowsHide: true,
      stdio: ["ignore", "pipe", "pipe"],
    });
    let stdout = "";
    let stderr = "";
    child.stdout.setEncoding("utf8").on("data", (part) => { stdout += part; });
    child.stderr.setEncoding("utf8").on("data", (part) => { stderr += part; });
    child.once("error", (error) => vscode.window.showErrorMessage(`S3 command failed: ${error.message}`));
    child.once("exit", (code) => {
      if (stdout) output.append(stdout);
      if (stderr) output.append(stderr);
      output.show(true);
      if (code === 0) vscode.window.showInformationMessage(`S3 ${action} completed.`);
      else vscode.window.showErrorMessage(`S3 ${action} failed (exit ${code}).`);
    });
  }

  disposables.push(vscode.workspace.onDidOpenTextDocument((document) => notifyOpen(document)));
  disposables.push(vscode.workspace.onDidChangeTextDocument((event) => {
    if (!clientReady || !activeClient || event.document.languageId !== "s3") return;
    const uri = event.document.uri.toString();
    documents.set(uri, event.document);
    activeClient.notify("textDocument/didChange", {
      textDocument: { uri, version: event.document.version },
      contentChanges: [{ text: event.document.getText() }],
    });
  }));
  disposables.push(vscode.workspace.onDidCloseTextDocument((document) => {
    const uri = document.uri.toString();
    if (clientReady && activeClient && document.languageId === "s3") {
      activeClient.notify("textDocument/didClose", { textDocument: { uri } });
    }
    documents.delete(uri);
    diagnostics.delete(document.uri);
  }));
  disposables.push(vscode.commands.registerCommand("s3.restartLanguageServer", async () => {
    await stopServer();
    if (await startServer()) registerProviders();
  }));
  disposables.push(vscode.commands.registerCommand("s3.checkCurrentFile", () => runToolkit("check")));
  disposables.push(vscode.commands.registerCommand("s3.inspectProject", () => runToolkit("inspect", true)));
  disposables.push(vscode.commands.registerCommand("s3.buildProject", () => runToolkit("build", true)));
  disposables.push(vscode.commands.registerCommand("s3.runProject", () => runToolkit("run", true)));
  stopActiveServer = stopServer;
  disposables.push(new vscode.Disposable(() => { void stopServer(); }));
  context.subscriptions.push(...disposables);

  for (const document of vscode.workspace.textDocuments) {
    if (document.languageId === "s3") documents.set(document.uri.toString(), document);
  }
  if (await startServer()) registerProviders();

  return {
    dispose: async () => {
      await stopServer();
      for (const item of disposables) item.dispose();
    },
  };
}

async function deactivate() {
  if (stopActiveServer) await stopActiveServer();
  stopActiveServer = null;
}

module.exports = { activate, deactivate, isS3Repository, mapDiagnostic };
