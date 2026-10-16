"use strict";

function utf16ToCodePoint(line, column) {
  let units = 0;
  let points = 0;
  for (const character of line) {
    if (units + character.length > column) break;
    units += character.length;
    points += 1;
  }
  return points;
}

function codePointToUtf16(line, column) {
  return Array.from(line).slice(0, Math.max(0, column)).join("").length;
}

function toServerPosition(document, position) {
  const line = Math.max(0, Math.min(position.line, document.lineCount - 1));
  return {
    line,
    character: utf16ToCodePoint(document.lineAt(line).text, position.character),
  };
}

function toClientPosition(document, position) {
  const line = Math.max(0, Math.min(position.line, document.lineCount - 1));
  return {
    line,
    character: codePointToUtf16(document.lineAt(line).text, position.character),
  };
}

function toClientRange(document, range, vscode) {
  const start = toClientPosition(document, range.start);
  const end = toClientPosition(document, range.end);
  return new vscode.Range(start.line, start.character, end.line, end.character);
}

module.exports = { utf16ToCodePoint, codePointToUtf16, toServerPosition, toClientPosition, toClientRange };
