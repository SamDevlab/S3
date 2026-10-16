"use strict";

const { EventEmitter } = require("node:events");

class JsonRpcClient extends EventEmitter {
  constructor(child, { maxMessageBytes = 1024 * 1024, maxHeaderBytes = 16384 } = {}) {
    super();
    this.child = child;
    this.maxMessageBytes = maxMessageBytes;
    this.maxHeaderBytes = maxHeaderBytes;
    this.buffer = Buffer.alloc(0);
    this.nextId = 1;
    this.pending = new Map();
    this.closed = false;
    this.exitPromise = new Promise((resolve) => child.once("exit", (code, signal) => {
      this.closed = true;
      const error = new Error(`S3 language server exited (${code ?? signal ?? "unknown"})`);
      for (const item of this.pending.values()) item.reject(error);
      this.pending.clear();
      this.emit("serverExit", { code, signal });
      resolve({ code, signal });
    }));
    child.stdout.on("data", (chunk) => this._read(chunk));
    child.stderr.on("data", (chunk) => this.emit("stderr", chunk.toString("utf8")));
    child.on("error", (error) => this.emit("serverError", error));
  }

  request(method, params = {}) {
    if (this.closed) return Promise.reject(new Error("language server is closed"));
    const id = this.nextId++;
    const promise = new Promise((resolve, reject) => this.pending.set(id, { resolve, reject }));
    this._write({ jsonrpc: "2.0", id, method, params });
    return promise;
  }

  notify(method, params = {}) {
    if (this.closed) return false;
    this._write({ jsonrpc: "2.0", method, params });
    return true;
  }

  onNotification(method, listener) {
    this.on(`notification:${method}`, listener);
    return () => this.off(`notification:${method}`, listener);
  }

  async stop() {
    if (this.closed) return this.exitPromise;
    try {
      await this.request("shutdown", {});
    } catch (_error) {
      // The process may already be exiting; still send the protocol exit notification.
    }
    this.notify("exit", {});
    this.child.stdin.end();
    let timeout;
    const timer = new Promise((resolve) => { timeout = setTimeout(() => resolve(null), 1500); });
    const result = await Promise.race([this.exitPromise, timer]);
    clearTimeout(timeout);
    if (result === null && !this.closed) this.child.kill();
    return result;
  }

  _write(message) {
    const body = Buffer.from(JSON.stringify(message), "utf8");
    if (body.length > this.maxMessageBytes) throw new Error("JSON-RPC message exceeds configured bound");
    this.child.stdin.write(Buffer.concat([
      Buffer.from(`Content-Length: ${body.length}\r\n\r\n`, "ascii"),
      body,
    ]));
  }

  _read(chunk) {
    this.buffer = Buffer.concat([this.buffer, Buffer.from(chunk)]);
    for (;;) {
      const boundary = this.buffer.indexOf("\r\n\r\n");
      if (boundary < 0) {
        if (this.buffer.length > this.maxHeaderBytes) this.emit("serverError", new Error("LSP header exceeds bound"));
        return;
      }
      if (boundary > this.maxHeaderBytes) {
        this.emit("serverError", new Error("LSP header exceeds bound"));
        this.child.kill();
        return;
      }
      const header = this.buffer.subarray(0, boundary).toString("ascii");
      const lengths = header.split("\r\n").filter((line) => /^content-length\s*:/i.test(line));
      if (lengths.length !== 1) {
        this.emit("serverError", new Error("LSP frame requires one Content-Length header"));
        this.child.kill();
        return;
      }
      const lengthText = lengths[0].split(":", 2)[1].trim();
      if (!/^\d+$/.test(lengthText)) {
        this.emit("serverError", new Error("invalid LSP Content-Length"));
        this.child.kill();
        return;
      }
      const length = Number(lengthText);
      if (length > this.maxMessageBytes) {
        this.emit("serverError", new Error("LSP body exceeds bound"));
        this.child.kill();
        return;
      }
      const bodyStart = boundary + 4;
      if (this.buffer.length < bodyStart + length) return;
      const body = this.buffer.subarray(bodyStart, bodyStart + length);
      this.buffer = this.buffer.subarray(bodyStart + length);
      let message;
      try {
        message = JSON.parse(body.toString("utf8"));
      } catch (error) {
        this.emit("serverError", new Error(`invalid LSP JSON: ${error.message}`));
        this.child.kill();
        return;
      }
      this._deliver(message);
    }
  }

  _deliver(message) {
    if (Object.prototype.hasOwnProperty.call(message, "id") &&
        !Object.prototype.hasOwnProperty.call(message, "method")) {
      const pending = this.pending.get(message.id);
      if (!pending) return;
      this.pending.delete(message.id);
      if (message.error) pending.reject(new Error(message.error.message || "JSON-RPC request failed"));
      else pending.resolve(message.result);
      return;
    }
    if (typeof message.method === "string") {
      this.emit(`notification:${message.method}`, message.params || {});
    }
  }
}

module.exports = { JsonRpcClient };
