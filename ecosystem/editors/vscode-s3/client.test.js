"use strict";

const assert = require("node:assert/strict");
const path = require("node:path");
const { spawn } = require("node:child_process");
const test = require("node:test");
const { JsonRpcClient } = require("./client");
const { utf16ToCodePoint, codePointToUtf16, toServerPosition, toClientPosition } = require("./positions");

const repositoryRoot = path.resolve(__dirname, "../../..");
const python = process.env.PYTHON || "python";

function startServer() {
  const child = spawn(python, ["-m", "ecosystem.editors.vscode_s3.server"], {
    cwd: repositoryRoot,
    shell: false,
    windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
  });
  return new JsonRpcClient(child);
}

function notification(client, method, timeoutMs = 5000) {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => {
      client.off(`notification:${method}`, listener);
      reject(new Error(`timeout waiting for ${method}`));
    }, timeoutMs);
    const listener = (params) => {
      clearTimeout(timer);
      resolve(params);
    };
    client.on(`notification:${method}`, listener);
  });
}

test("UTF-16 editor columns map to the server's code-point positions", () => {
  const line = "α😀name";
  assert.equal(utf16ToCodePoint(line, 4), 3);
  assert.equal(codePointToUtf16(line, 3), 4);
  const document = { lineCount: 1, lineAt: () => ({ text: line }) };
  assert.deepEqual(toServerPosition(document, { line: 0, character: 4 }), { line: 0, character: 3 });
  assert.deepEqual(toClientPosition(document, { line: 0, character: 3 }), { line: 0, character: 4 });
});

test("stdio integration initializes, validates, formats, answers language requests, closes, and reconnects", async () => {
  const client = startServer();
  const initialization = await client.request("initialize", {
    processId: process.pid,
    rootUri: `file://${repositoryRoot.replaceAll("\\", "/")}`,
    capabilities: {},
  });
  assert.equal(initialization.serverInfo.name, "s3-language-server");
  assert.equal(initialization.capabilities.documentFormattingProvider, true);
  client.notify("initialized", {});

  const uri = "file:///workspace/main.s3";
  const invalidSource = "fn main() -> i64:\n    return missing(1)  \n";
  const openedDiagnostics = notification(client, "textDocument/publishDiagnostics");
  client.notify("textDocument/didOpen", {
    textDocument: { uri, languageId: "s3", version: 1, text: invalidSource },
  });
  const invalid = await openedDiagnostics;
  assert.equal(invalid.uri, uri);
  assert.ok(invalid.diagnostics[0].code);

  const symbols = await client.request("textDocument/documentSymbol", { textDocument: { uri } });
  assert.deepEqual(symbols.map((item) => item.name), ["main"]);
  const hover = await client.request("textDocument/hover", {
    textDocument: { uri }, position: { line: 0, character: 4 },
  });
  assert.match(hover.contents.value, /fn main\(\)/);
  const definition = await client.request("textDocument/definition", {
    textDocument: { uri }, position: { line: 0, character: 4 },
  });
  assert.equal(definition[0].uri, uri);
  const references = await client.request("textDocument/references", {
    textDocument: { uri }, position: { line: 0, character: 4 },
    context: { includeDeclaration: true },
  });
  assert.equal(references.length, 1);

  const formatting = await client.request("textDocument/formatting", {
    textDocument: { uri }, options: { tabSize: 4, insertSpaces: true },
  });
  assert.equal(formatting.length, 1);
  assert.ok(!formatting[0].newText.includes("  \n"));
  await assert.rejects(
    client.request("textDocument/completion", { textDocument: { uri }, position: { line: 0, character: 0 } }),
    /method not found/,
  );

  const correctedSource = "fn main() -> i64:\n    return 7\n";
  const changedDiagnostics = notification(client, "textDocument/publishDiagnostics");
  client.notify("textDocument/didChange", {
    textDocument: { uri, version: 2 }, contentChanges: [{ text: correctedSource }],
  });
  assert.deepEqual((await changedDiagnostics).diagnostics, []);
  const closedDiagnostics = notification(client, "textDocument/publishDiagnostics");
  client.notify("textDocument/didClose", { textDocument: { uri } });
  assert.deepEqual((await closedDiagnostics).diagnostics, []);
  await client.stop();

  const reconnected = startServer();
  const secondInitialization = await reconnected.request("initialize", { processId: process.pid, capabilities: {} });
  assert.equal(secondInitialization.serverInfo.name, "s3-language-server");
  await reconnected.stop();
});
