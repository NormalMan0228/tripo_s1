"""Literal resource references, conservative dynamic patterns, and scene UIDs."""
from __future__ import annotations

import fnmatch
import re

from .common import Context, Source, Token, arguments, significant


FORMAT = re.compile(r"%(?:[-+0 #]*\d*(?:\.\d+)?[sdifxXocv])")


def _format_pattern(value: str) -> str:
    # A doubled percent is literal, not a formatting placeholder.
    return FORMAT.sub("*", value.replace("%%", "\x00")).replace("\x00", "%")


def _atom(tokens: list[Token], index: int, constants: dict[str, str]) -> tuple[str, int]:
    if index >= len(tokens):
        return "*", index
    token = tokens[index]
    if token.kind == "STRING":
        return _format_pattern(token.value), index + 1
    if token.kind == "IDENT":
        value = constants.get(token.value, "*")
        end = index + 1
        # Consume index/call/member chains as one unknown operand.
        while end < len(tokens):
            if tokens[end].value in ("(", "["):
                _, close = arguments(tokens, end)
                if close == end:
                    break
                value, end = "*", close + 1
            elif tokens[end].value == "." and end + 1 < len(tokens):
                value, end = "*", end + 2
            else:
                break
        return _format_pattern(value), end
    if token.value in ("(", "[", "{"):
        _, close = arguments(tokens, index)
        return "*", max(index + 1, close + 1)
    return "*", index + 1


def _expression(tokens: list[Token], index: int, constants: dict[str, str]) -> tuple[str, int, bool]:
    pattern, end = _atom(tokens, index, constants)
    dynamic = "*" in pattern
    while end < len(tokens) and tokens[end].value in ("+", "%"):
        operator = tokens[end].value
        value, following = _atom(tokens, end + 1, constants)
        if operator == "+":
            pattern += value
        # Formatting arguments are already represented by wildcards above.
        dynamic, end = True, following
    return pattern, end, dynamic


def _constants(tokens: list[Token]) -> dict[str, str]:
    constants: dict[str, str] = {}
    for i, token in enumerate(tokens):
        if token.value != "const" or token.column != 0 or i + 1 >= len(tokens):
            continue
        name = tokens[i + 1].value
        j = i + 2
        while j < len(tokens) and tokens[j].line == token.line and tokens[j].value != "=":
            j += 1
        if j + 1 < len(tokens) and tokens[j].value == "=":
            pattern, _, _ = _expression(tokens, j + 1, constants)
            if pattern.startswith("res://"):
                constants[name] = pattern
    return constants


def _dynamic_message(ctx: Context, pattern: str) -> str:
    relative = ctx.resource_relative(pattern)
    matches = sorted(name for name in ctx.files if relative is not None and fnmatch.fnmatchcase(name, relative))
    if matches:
        examples = ", ".join("res://" + name for name in matches[:3])
        return f"Dynamic path {pattern!r}: {len(matches)} matching file(s); examples: {examples}. Runtime values remain unchecked."
    return f"Dynamic path {pattern!r}: no matching files in the project tree; verify runtime values or generated assets."


def _uid_references(ctx: Context, source: Source, sidecars: set[str]) -> None:
    tokens = significant(source.tokens)
    declarations: set[int] = set()
    fallback: set[str] = set()
    for i, token in enumerate(tokens):
        if token.kind != "SYMBOL" or token.value != "[" or i + 1 >= len(tokens):
            continue
        kind = tokens[i + 1].value
        if kind not in ("gd_scene", "gd_resource", "ext_resource"):
            continue
        _, close = arguments(tokens, i)
        attrs: dict[str, Token] = {}
        for j in range(i + 2, close - 1):
            if tokens[j].kind == "IDENT" and tokens[j + 1].value == "=" and tokens[j + 2].kind == "STRING":
                attrs[tokens[j].value] = tokens[j + 2]
        uid = attrs.get("uid")
        if uid is not None:
            if kind in ("gd_scene", "gd_resource"):
                declarations.add(uid.start)
            elif "path" in attrs:
                path = attrs["path"].value
                if ctx.exists(path) and (ctx.root / path[6:].split("::", 1)[0]).is_file():
                    fallback.add(uid.value)
    for token in tokens:
        if token.kind == "STRING" and token.value.startswith("uid://") and token.start not in declarations:
            if token.value not in sidecars and token.value not in fallback:
                ctx.emit("blocker", "unresolved-uid", source, token.line,
                         f"UID {token.value!r} has no live .uid sidecar or ext_resource with an existing path.")


def check_resources(ctx: Context) -> None:
    sidecars: set[str] = set()
    for name in sorted(ctx.files):
        if not name.endswith(".uid") or name[:-4] not in ctx.files:
            continue
        try:
            value = (ctx.root / name).read_text(encoding="utf-8-sig").strip()
        except (OSError, UnicodeError) as error:
            ctx.emit("blocker", "unreadable-file", name, 1, str(error))
            continue
        if re.fullmatch(r"uid://[a-z0-9]+", value):
            sidecars.add(value)
    for source in ctx.sources.values():
        if source.path.suffix not in (".gd", ".tscn", ".tres", ".gdshader", ".json"):
            continue
        tokens = significant(source.tokens)
        constants = _constants(tokens) if source.path.suffix == ".gd" else {}
        consumed: set[int] = set()
        for i, token in enumerate(tokens):
            literal = token.kind == "STRING" and token.value.startswith("res://")
            alias = token.kind == "IDENT" and token.value in constants
            if i in consumed or not (literal or alias):
                continue
            # Only expand constant usages in actual concatenation/formatting expressions.
            if alias and (i + 1 >= len(tokens) or tokens[i + 1].value not in ("+", "%")):
                continue
            if alias and i > 0 and tokens[i - 1].value == ".":
                continue
            pattern, end, dynamic = _expression(tokens, i, constants)
            if dynamic:
                # Only the operands forming this path are consumed. A nested
                # call may itself contain another independent res:// reference.
                depth = 0
                for cursor in range(i, end):
                    item = tokens[cursor]
                    if item.kind == "SYMBOL" and item.value in ("(", "[", "{"):
                        depth += 1
                    elif item.kind == "SYMBOL" and item.value in (")", "]", "}"):
                        depth -= 1
                    elif depth == 0:
                        consumed.add(cursor)
                ctx.emit("warning", "dynamic-resource", source, token.line, _dynamic_message(ctx, pattern))
            elif literal and not ctx.exists(token.value):
                # The script-specific diagnostics give missing preload/extends a better label.
                prior = tokens[max(0, i - 2):i]
                if source.path.suffix == ".gd" and (
                    [t.value for t in prior] == ["preload", "("]
                    or (i > 0 and tokens[i - 1].value == "extends")
                ):
                    continue
                ctx.emit("blocker", "missing-resource", source, token.line,
                         f"Resource path does not exist in the tree: {token.value}")
        if source.path.suffix in (".tscn", ".tres"):
            _uid_references(ctx, source, sidecars)
