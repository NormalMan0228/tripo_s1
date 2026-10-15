"""Small lexical helpers, shared by the static checks (not a Godot parser)."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import posixpath
import re


@dataclass(frozen=True)
class Token:
    kind: str
    value: str
    line: int
    column: int
    start: int
    end: int


def lex(text: str, *, line_comments: tuple[str, ...] = ("#", "//")) -> list[Token]:
    """Tokenize strings/comments first so their contents cannot become code."""
    tokens: list[Token] = []
    i, line, column = 0, 1, 0
    while i < len(text):
        ch = text[i]
        if ch in " \t\r\ufeff":
            column += 1
            i += 1
            continue
        if ch == "\n":
            tokens.append(Token("NEWLINE", ch, line, column, i, i + 1))
            i, line, column = i + 1, line + 1, 0
            continue
        if any(text.startswith(marker, i) for marker in line_comments):
            end = text.find("\n", i)
            end = len(text) if end < 0 else end
            column += end - i
            i = end
            continue
        if text.startswith("/*", i):
            end = text.find("*/", i + 2)
            end = len(text) if end < 0 else end + 2
            chunk = text[i:end]
            count = chunk.count("\n")
            column = len(chunk.rsplit("\n", 1)[-1]) if count else column + len(chunk)
            line += count
            i = end
            continue
        start, start_line, start_column = i, line, column
        if ch in "\"'":
            delimiter = ch * 3 if text.startswith(ch * 3, i) else ch
            i += len(delimiter)
            value: list[str] = []
            while i < len(text) and not text.startswith(delimiter, i):
                if text[i] == "\\" and i + 1 < len(text):
                    escaped = text[i + 1]
                    if escaped in "uU" and re.fullmatch(
                        r"[0-9a-fA-F]{%d}" % (4 if escaped == "u" else 8),
                        text[i + 2:i + 2 + (4 if escaped == "u" else 8)],
                    ):
                        size = 4 if escaped == "u" else 8
                        try:
                            value.append(chr(int(text[i + 2:i + 2 + size], 16)))
                            i += 2 + size
                            continue
                        except ValueError:
                            pass
                    value.append({"n": "\n", "r": "\r", "t": "\t"}.get(escaped, escaped))
                    i += 2
                else:
                    value.append(text[i])
                    i += 1
            if text.startswith(delimiter, i):
                i += len(delimiter)
            chunk = text[start:i]
            count = chunk.count("\n")
            line += count
            column = len(chunk.rsplit("\n", 1)[-1]) if count else column + len(chunk)
            tokens.append(Token("STRING", "".join(value), start_line, start_column, start, i))
            continue
        if ch.isalpha() or ch == "_":
            i += 1
            while i < len(text) and (text[i].isalnum() or text[i] == "_"):
                i += 1
            kind = "IDENT"
        elif ch.isdigit():
            i += 1
            while i < len(text) and (text[i].isalnum() or text[i] in "._"):
                i += 1
            kind = "NUMBER"
        else:
            i += 1
            kind = "SYMBOL"
        column += i - start
        tokens.append(Token(kind, text[start:i], start_line, start_column, start, i))
    return tokens


def significant(tokens: list[Token]) -> list[Token]:
    return [token for token in tokens if token.kind != "NEWLINE"]


def arguments(tokens: list[Token], open_index: int) -> tuple[list[list[Token]], int]:
    """Split a balanced call/array, retaining nested commas within arguments."""
    pairs = {"(": ")", "[": "]", "{": "}"}
    if open_index >= len(tokens) or tokens[open_index].value not in pairs:
        return [], open_index
    stack = [pairs[tokens[open_index].value]]
    result: list[list[Token]] = []
    current: list[Token] = []
    for i in range(open_index + 1, len(tokens)):
        token = tokens[i]
        value = token.value if token.kind == "SYMBOL" else ""
        if value in pairs:
            stack.append(pairs[value])
        elif stack and value == stack[-1]:
            stack.pop()
            if not stack:
                if current or result:
                    result.append(current)
                return result, i
        if value == "," and len(stack) == 1:
            result.append(current)
            current = []
        else:
            current.append(token)
    return [], open_index


@dataclass
class Source:
    path: Path
    relative: str
    text: str
    tokens: list[Token]


@dataclass(frozen=True)
class Finding:
    severity: str
    code: str
    file: str
    line: int
    message: str


@dataclass
class Context:
    root: Path
    sources: dict[str, Source]
    files: set[str]
    findings: list[Finding] = field(default_factory=list)
    directories: set[str] = field(default_factory=set)

    def resource_relative(self, path: str) -> str | None:
        if not path.startswith("res://"):
            return None
        relative = posixpath.normpath(path[6:].split("::", 1)[0])
        if relative.startswith("/") or relative == ".." or relative.startswith("../"):
            return None
        return relative

    def exists(self, path: str) -> bool:
        relative = self.resource_relative(path)
        if relative is None:
            # Tools and capture scripts use res://../ to refer to the checkout.
            # Permit existing siblings within the project parent's tree, never
            # an arbitrary path outside that tree, and still enforce case.
            if path.startswith("res://"):
                target = self.root / path[6:].split("::", 1)[0]
                boundary = self.root.parent.resolve()
                try:
                    parts = target.resolve().relative_to(boundary).parts
                    cursor = boundary
                    for part in parts:
                        if part not in {item.name for item in cursor.iterdir()}:
                            return False
                        cursor = cursor / part
                        if cursor.is_symlink():
                            return False
                    return cursor.exists()
                except (OSError, ValueError):
                    return False
            return False
        if relative == ".":
            return True
        # Compare indexed names exactly, including on case-insensitive Windows.
        return relative in self.files or relative in self.directories or any(
            name.startswith(relative.rstrip("/") + "/") for name in self.files
        )

    def emit(self, severity: str, code: str, source: Source | str, line: int, message: str) -> None:
        finding = Finding(severity, code, source.relative if isinstance(source, Source) else source,
                          line, message)
        if finding not in self.findings:
            self.findings.append(finding)
