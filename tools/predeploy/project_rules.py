"""Read-only checks for project autoloads and explicitly declared input actions."""

from __future__ import annotations

import re
import posixpath

from .common import Context, Token, arguments, lex, significant


_SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*(?:[;#].*)?$")
_ASSIGNMENT = re.compile(r'^\s*("(?:\\.|[^"\\])*"|[^\s=;#]+)\s*=\s*(.*)$')
_INPUT_MAP_ACTION_ARGUMENT = {
    "action_add_event": 0,
    "action_erase_event": 0,
    "action_erase_events": 0,
    "action_get_deadzone": 0,
    "action_get_events": 0,
    "action_has_event": 0,
    "action_set_deadzone": 0,
    "add_action": 0,
    "erase_action": 0,
    "event_is_action": 1,
    "has_action": 0,
}


def _literal(tokens: list[Token]) -> str | None:
    tokens = significant(tokens)
    while len(tokens) >= 2 and tokens[0].value == "(" and tokens[-1].value == ")":
        _, close = arguments(tokens, 0)
        if close != len(tokens) - 1:
            break
        tokens = tokens[1:-1]
    if len(tokens) == 2 and tokens[0].value == "&":
        tokens = tokens[1:]
    if len(tokens) == 1 and tokens[0].kind == "STRING":
        return tokens[0].value
    return None


def _config_tokens(value: str) -> list[Token]:
    tokens = lex(value)
    for index, token in enumerate(tokens):
        if token.kind == "SYMBOL" and token.value == ";":
            return tokens[:index]
    return tokens


def check_project_settings(ctx: Context) -> None:
    """Check literal action references; report unresolved expressions as warnings.

    Built-in UI actions are deliberately not added to the set: this check enforces
    the task's requirement that every action be explicit in project.godot.
    Runtime InputMap.add_action calls do not count as project declarations.
    """
    project = ctx.sources.get("project.godot")
    if project is None:
        ctx.emit("blocker", "missing-project-settings", "project.godot", 1,
                 "project.godot is missing; autoloads and input actions cannot be checked.")
        return

    section = ""
    actions: set[str] = set()
    depth = 0
    for number, line in enumerate(project.text.splitlines(), 1):
        heading = _SECTION.match(line) if depth == 0 else None
        if heading:
            section = heading.group(1)
            continue
        assignment = _ASSIGNMENT.match(line) if depth == 0 else None
        if assignment and section in {"autoload", "input"}:
            raw_key, value = assignment.groups()
            key = _literal(lex(raw_key)) if raw_key.startswith('"') else raw_key
            if section == "input" and key is not None:
                actions.add(key)
            elif section == "autoload":
                path = _literal(_config_tokens(value))
                if path is None:
                    ctx.emit("blocker", "missing-autoload", project, number,
                             f"Autoload {key!r} does not have a valid literal resource path.")
                else:
                    path = path.removeprefix("*")
                    relative = posixpath.normpath(path.removeprefix("res://"))
                    if not path.startswith("res://") or not ctx.exists(path) or relative not in ctx.files:
                        ctx.emit("blocker", "missing-autoload", project, number,
                                 f"Autoload {key!r} references a missing file: {path}")
        # Godot's object/dictionary values may span many lines. Only top-level
        # assignments declare actions; quoted strings cannot alter this depth.
        for token in _config_tokens(line):
            if token.kind == "SYMBOL":
                if token.value in {"{", "[", "("}:
                    depth += 1
                elif token.value in {"}", "]", ")"}:
                    depth = max(0, depth - 1)

    for source in ctx.sources.values():
        if source.path.suffix != ".gd":
            continue
        tokens = significant(source.tokens)
        for index in range(len(tokens) - 3):
            owner, dot, method, opening = tokens[index:index + 4]
            if owner.kind != "IDENT" or dot.value != "." or method.kind != "IDENT" or opening.value != "(":
                continue
            if index and tokens[index - 1].value == ".":
                continue  # A member called Input is not necessarily the singleton.
            if owner.value == "Input" and method.value.startswith("is_action_"):
                action_index = 0
            elif owner.value == "InputMap" and method.value in _INPUT_MAP_ACTION_ARGUMENT:
                action_index = _INPUT_MAP_ACTION_ARGUMENT[method.value]
            else:
                continue
            args, _ = arguments(tokens, index + 3)
            if action_index >= len(args):
                continue
            action = _literal(args[action_index])
            if action is None:
                ctx.emit("warning", "dynamic-input-action", source, owner.line,
                         f"{owner.value}.{method.value} uses a dynamic action; verify its values against project.godot [input].")
            elif action not in actions:
                ctx.emit("blocker", "undefined-input-action", source, owner.line,
                         f"Action {action!r} used by {owner.value}.{method.value} is not declared in project.godot [input].")
