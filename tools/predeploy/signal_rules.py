"""Conservative, token-based duplicate signal connection checks."""

from __future__ import annotations

from dataclasses import dataclass

from .common import Context, Source, Token, arguments, significant


@dataclass(frozen=True)
class _Scope:
    start: int
    end: int
    name: str


@dataclass(frozen=True)
class _Call:
    index: int
    start: int
    end: int
    method: str
    receiver: tuple
    callback: tuple


def _key(tokens: list[Token]) -> tuple:
    # self.signal and signal denote the same signal within one function.
    if len(tokens) >= 2 and tokens[0].value == "self" and tokens[1].value == ".":
        tokens = tokens[2:]
    result = []
    for index, token in enumerate(tokens):
        if token.value == "&" and index + 1 < len(tokens) and tokens[index + 1].kind == "STRING":
            continue
        # Distinct lambda expressions create distinct Callable instances.
        if token.kind == "IDENT" and token.value == "func":
            result.append(("lambda", token.start))
        else:
            result.append((token.kind, token.value))
    return tuple(result)


def _structure(tokens: list[Token]) -> tuple[dict[int, int], list[tuple[int, ...]]]:
    matching: dict[int, int] = {}
    enclosing: list[tuple[int, ...]] = []
    stack: list[int] = []
    pairs = {")": "(", "]": "[", "}": "{"}
    for index, token in enumerate(tokens):
        enclosing.append(tuple(stack))
        if token.kind != "SYMBOL":
            continue
        if token.value in {"(", "[", "{"}:
            stack.append(index)
        elif token.value in pairs and stack and tokens[stack[-1]].value == pairs[token.value]:
            opening = stack.pop()
            matching[opening] = index
            matching[index] = opening
    return matching, enclosing


def _indents(source: Source) -> dict[int, int]:
    result = {}
    for number, line in enumerate(source.text.splitlines(), 1):
        prefix = line[:len(line) - len(line.lstrip(" \t"))]
        result[number] = len(prefix.expandtabs(4))
    return result


def _body_end(tokens: list[Token], start: int, colon: int, indents: dict[int, int],
              enclosing: list[tuple[int, ...]]) -> int:
    indent = indents.get(tokens[start].line, 0)
    inline = colon + 1 < len(tokens) and tokens[colon + 1].line == tokens[colon].line
    for index in range(colon + 1, len(tokens)):
        token = tokens[index]
        if token.line <= tokens[colon].line:
            # A lambda's inline body ends before its enclosing call closes.
            if token.value in {")", "]", "}"} and enclosing[index] and enclosing[index][-1] < start:
                return index
            continue
        if index and token.line == tokens[index - 1].line:
            continue
        if any(opening >= colon + 1 for opening in enclosing[index]):
            continue
        if inline or indents.get(token.line, 0) <= indent:
            return index
    return len(tokens)


def _functions(tokens: list[Token], matching: dict[int, int], indents: dict[int, int],
               enclosing: list[tuple[int, ...]]) -> list[_Scope]:
    scopes = []
    for index, token in enumerate(tokens):
        if token.kind != "IDENT" or token.value != "func":
            continue
        opening = index + 1
        name = f"lambda@{token.line}:{token.column}"
        if opening < len(tokens) and tokens[opening].kind == "IDENT":
            name = tokens[opening].value
            opening += 1
        if opening >= len(tokens) or tokens[opening].value != "(" or opening not in matching:
            continue
        colon = matching[opening] + 1
        while colon < len(tokens) and tokens[colon].value != ":":
            if tokens[colon].value in {"func", "class", "="}:
                break
            colon += 1
        if colon < len(tokens) and tokens[colon].value == ":":
            scopes.append(_Scope(colon + 1, _body_end(tokens, index, colon, indents, enclosing), name))
    return scopes


def _receiver_start(tokens: list[Token], end: int, matching: dict[int, int]) -> int | None:
    """Read a postfix expression backward without swallowing a statement prefix."""
    index = end - 1
    if index < 0:
        return None
    while index >= 0:
        token = tokens[index]
        if token.value in {")", "]"} and index in matching:
            opening = matching[index]
            index = opening - 1
            if index >= 0 and (tokens[index].kind == "IDENT" or tokens[index].value in {")", "]"}):
                continue  # Function invocation or subscript.
            start = opening
        elif token.kind in {"IDENT", "STRING"}:
            start = index
            index -= 1
        else:
            return None
        if index >= 0 and tokens[index].value == ".":
            index -= 1
            continue
        if index >= 0 and tokens[index].value in {"$", "%"}:
            start = index
        return start
    return None


def _calls(tokens: list[Token], matching: dict[int, int]) -> list[_Call]:
    result = []
    for index in range(2, len(tokens) - 1):
        token = tokens[index]
        if token.kind != "IDENT" or token.value not in {"connect", "is_connected", "disconnect"}:
            continue
        if tokens[index - 1].value != "." or tokens[index + 1].value != "(":
            continue
        start = _receiver_start(tokens, index - 1, matching)
        if start is None:
            continue
        args, close = arguments(tokens, index + 1)
        if not args or not args[0]:
            continue
        receiver = _key(tokens[start:index - 1])
        callback = args[0]
        signal = significant(args[0])
        if len(signal) == 2 and signal[0].value == "&":
            signal = signal[1:]
        if len(args) >= 2 and len(signal) == 1 and signal[0].kind == "STRING":
            # Object.connect("signal", callable) and Signal.connect(callable)
            # refer to the same connection when their receiver names agree.
            receiver += (("SYMBOL", "."), ("IDENT", signal[0].value))
            if receiver[:2] == (("IDENT", "self"), ("SYMBOL", ".")):
                receiver = receiver[2:]
            callback = args[1]
        result.append(_Call(index, start, close, token.value, receiver, _key(callback)))
    return result


def _guard_headers(tokens: list[Token], calls: list[_Call], matching: dict[int, int],
                   indents: dict[int, int], enclosing: list[tuple[int, ...]]) -> list[tuple[int, int, _Call]]:
    """Return negative is_connected guards and the ranges they protect.

    OR conditions do not guarantee that a signal is unconnected. A guard is
    applied only to later connections in its own body, never to the whole file.
    """
    guards = []
    for index, token in enumerate(tokens):
        if token.kind != "IDENT" or token.value not in {"if", "elif"}:
            continue
        cursor = index + 1
        while cursor < len(tokens):
            if tokens[cursor].value in {"(", "[", "{"} and cursor in matching:
                cursor = matching[cursor] + 1
                continue
            if tokens[cursor].value == ":":
                break
            if tokens[cursor].line > token.line and not enclosing[cursor]:
                break
            cursor += 1
        if cursor >= len(tokens) or tokens[cursor].value != ":":
            continue
        condition = tokens[index + 1:cursor]
        if any(item.kind == "IDENT" and item.value == "or" for item in condition):
            continue
        end = _body_end(tokens, index, cursor, indents, enclosing)
        for call in calls:
            if call.method != "is_connected" or not index < call.start < call.end < cursor:
                continue
            # Remove only parentheses around the call itself. In particular,
            # `not (is_connected(cb) and enabled)` is not a safe guard.
            left, right = call.start, call.end
            while left > index + 1 and tokens[left - 1].value == "(" and matching.get(left - 1) == right + 1:
                left -= 1
                right += 1
            previous = left - 1
            negations = 0
            while previous > index and tokens[previous].value in {"not", "!"}:
                negations += 1
                previous -= 1
            negative = bool(negations % 2)
            tail = [item.value for item in tokens[right + 1:cursor] if item.value != ")"]
            if "".join(tail).startswith(("==false", "!=true")):
                negative = not negative
            if negative:
                guards.append((index, end, call))
    return guards


def check_signals(ctx: Context) -> None:
    """Warn on repeated textual signal/callable identities in the same function."""
    for source in ctx.sources.values():
        if source.path.suffix != ".gd":
            continue
        tokens = significant(source.tokens)
        matching, enclosing = _structure(tokens)
        indents = _indents(source)
        scopes = _functions(tokens, matching, indents, enclosing)
        calls = _calls(tokens, matching)
        guards = _guard_headers(tokens, calls, matching, indents, enclosing)
        seen: dict[tuple, _Call] = {}
        for call in calls:
            active = [scope for scope in scopes if scope.start <= call.index < scope.end]
            if not active or call.method == "is_connected":
                continue
            scope = max(active, key=lambda item: item.start)
            identity = (scope.start, call.receiver, call.callback)
            if call.method == "disconnect":
                seen.pop(identity, None)
                continue
            previous = seen.get(identity)
            if previous is not None:
                guarded = any(
                    previous.index < start < call.index < end
                    and guard.receiver == call.receiver and guard.callback == call.callback
                    for start, end, guard in guards
                )
                if not guarded:
                    receiver = "".join(str(value) for _, value in call.receiver)
                    ctx.emit("warning", "duplicate-signal-connect", source, tokens[call.index].line,
                             f"{receiver}.connect repeats the same callable in function {scope.name!r}; "
                             f"first connection is on line {tokens[previous.index].line} without a new matching is_connected guard.")
            seen[identity] = call
