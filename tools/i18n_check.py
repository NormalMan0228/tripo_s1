"""Read-only check of Godot translation literals and the en/zh catalog.

Run ``python tools/i18n_check.py --report docs/I18N_MISSING_KO.md`` to refresh
the Korean report. Exit status is 1 for missing translations, 0 when complete.
Every game/**/*.gd is scanned, including maps, tests, and nested script folders.
Dynamic values (variables, lookups, and runtime formatting) are not evaluated.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = ("en", "zh")
# Translation entry points used by the client. Other local and imported wrappers
# are inferred from their bodies. DayFolk.line() translates the daytime variant.
WRAPPERS = {"TranslationServer.translate": 0, "I18n.t": 0,
            "I18n.server": 0, "DayFolk.line": 0, "t.call": 0}
LEXER = re.compile(
    r'(?P<comment>\#[^\n]*)|'
    r'(?P<string>r?(?:"""(?:\\[\s\S]|(?!""")[^\\])*"""|'
    r"'''(?:\\[\s\S]|(?!''')[^\\])*'''|"
    r'"(?:\\[\s\S]|[^"\\\n])*"|'
    r"'(?:\\[\s\S]|[^'\\\n])*'))|"
    r'(?P<name>[A-Za-z_][A-Za-z_0-9]*)|(?P<symbol>[^\s])'
)
FORMAT = re.compile(r"%%|%[-+ #0]*(?:\d+|\*)?(?:\.(?:\d+|\*))?[sdoxXcfv]|\{[^{}]*\}")
BBCODE = re.compile(r"\[/?(?:color|font|font_size|b|i|u|s|center|right|url)(?:=[^\]]*)?\]")
MEASUREMENT = re.compile(r"\s*[+-]?(?:\d+(?:\.\d*)?|\.\d+)\s*(?:mm|cm|m|km|ms|s|g|kg|Hz|kHz|MHz|°C|°F)\s*")


class Token(NamedTuple):
    kind: str
    text: str
    line: int
    column: int


class Reference(NamedTuple):
    path: str
    line: int
    key: str


class Issue(NamedTuple):
    key: str
    locations: tuple[Reference, ...]
    missing_key: bool
    languages: tuple[str, ...]


class Result(NamedTuple):
    script_count: int
    references: tuple[Reference, ...]
    issues: tuple[Issue, ...]

    @property
    def missing_key_count(self) -> int:
        return sum(issue.missing_key for issue in self.issues)


def tokenize(source: str) -> list[Token]:
    """Keep source lines while ignoring comments and treating strings atomically."""
    tokens = []
    line, previous = 1, 0
    for match in LEXER.finditer(source):
        line += source.count("\n", previous, match.start())
        if match.lastgroup != "comment":
            column = match.start() - source.rfind("\n", 0, match.start()) - 1
            tokens.append(Token(match.lastgroup, match.group(), line, column))
        line += match.group().count("\n")
        previous = match.end()
    return tokens


def unescape(literal: str) -> str:
    raw = literal.startswith("r")
    if raw:
        literal = literal[1:]
    width = 3 if literal.startswith(('"""', "'''")) else 1
    value = literal[width:-width]
    if raw:
        return value
    escapes = {"a": "\a", "b": "\b", "f": "\f", "n": "\n", "r": "\r",
               "t": "\t", "v": "\v", "e": "\x1b", "\\": "\\", '"': '"', "'": "'", "\n": ""}

    def replace(match: re.Match) -> str:
        escaped = match.group()[1:]
        if escaped.startswith(("u", "U")) and len(escaped) in (5, 7, 9):
            return chr(int(escaped[1:], 16))
        return escapes.get(escaped, match.group())

    return re.sub(r"\\(?:u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|U[0-9a-fA-F]{6}|[\s\S])", replace, value)


def is_text(key: str) -> bool:
    """Symbols, numbers, markup, paths, and interpolation-only labels need no entry."""
    if key.startswith(("res://", "user://")) or re.fullmatch(r"#[0-9a-fA-F]{3,8}", key):
        return False
    if MEASUREMENT.fullmatch(FORMAT.sub("0", BBCODE.sub("", key))):
        return False
    return any(char.isalpha() for char in FORMAT.sub("", BBCODE.sub("", key)))


def split_top(tokens: list[Token], separator: str, maxsplit: int = -1) -> list[list[Token]]:
    result, start, depth = [], 0, 0
    for i, token in enumerate(tokens):
        if token.kind == "symbol":
            if token.text in "([{":
                depth += 1
            elif token.text in ")]}":
                depth -= 1
        if (depth == 0 and token.kind != "string" and token.text == separator
                and (maxsplit < 0 or len(result) < maxsplit)):
            result.append(tokens[start:i])
            start = i + 1
    return result + [tokens[start:]]


def closing(tokens: list[Token], start: int) -> int | None:
    depth = 0
    for i in range(start, len(tokens)):
        if tokens[i].kind != "symbol":
            continue
        if tokens[i].text in "([{":
            depth += 1
        elif tokens[i].text in ")]}":
            depth -= 1
            if depth == 0:
                return i
    return None


def literal_values(tokens: list[Token]) -> list[tuple[str, int]]:
    """Extract whole literal keys, including ternary branches and literal joins.

    Do not mistake a lookup's field name or a ternary condition for a key, or a
    literal prefix of a dynamic expression for the complete translated string.
    """
    while tokens and tokens[0].text == "(" and closing(tokens, 0) == len(tokens) - 1:
        tokens = tokens[1:-1]
    if len(tokens) == 2 and tokens[0].text == "&":  # Godot StringName literal
        tokens = tokens[1:]
    if len(tokens) == 1 and tokens[0].kind == "string":
        return [(unescape(tokens[0].text), tokens[0].line)]
    choices = split_top(tokens, "if", 1)
    if len(choices) == 2:
        tail = split_top(choices[1], "else", 1)
        if len(tail) == 2:
            return literal_values(choices[0]) + literal_values(tail[1])
    parts = split_top(tokens, "+")
    if len(parts) > 1:
        values = [literal_values(part) for part in parts]
        if all(len(value) == 1 for value in values):
            return [("".join(value[0][0] for value in values), values[0][0][1])]
        return []
    if (len(tokens) >= 3 and tokens[0].text in ("str", "String", "StringName")
            and tokens[1].text == "(" and closing(tokens, 1) == len(tokens) - 1):
        return literal_values(tokens[2:-1])
    return []


def calls(tokens: list[Token]):
    """Yield actual calls and their arguments, excluding function declarations."""
    for i, token in enumerate(tokens):
        if token.kind != "symbol" or token.text != "(" or i == 0 or tokens[i - 1].kind != "name":
            continue
        start = i - 1
        while start >= 2 and tokens[start - 1].text == "." and tokens[start - 2].kind == "name":
            start -= 2
        if start and tokens[start - 1].text == "func":
            continue
        name = "".join(part.text for part in tokens[start:i])
        end = closing(tokens, i)
        if end is None:
            continue
        yield name, split_top(tokens[i + 1:end], ","), token.line


def functions(tokens: list[Token]):
    """Module functions and their parameter names/body line ranges.

    Keep discovery within a script, so a similarly named unrelated callback in
    another file is never classified as a translation wrapper.
    """
    for i, token in enumerate(tokens[:-2]):
        if token.text != "func" or tokens[i + 1].kind != "name" or tokens[i + 2].text != "(":
            continue
        start = i - 1 if i and tokens[i - 1].text == "static" else i
        if tokens[start].column != 0:
            continue
        end = closing(tokens, i + 2)
        if end is None:
            continue
        params = [arg[0].text for arg in split_top(tokens[i + 3:end], ",") if arg]
        body = end + 1
        while body < len(tokens) and tokens[body].text != ":":
            body += 1
        if body == len(tokens):
            continue
        last_line = next((part.line for part in tokens[body + 1:]
                          if part.line > tokens[body].line and part.column == 0), float("inf"))
        yield tokens[i + 1].text, params, tokens[body].line, last_line


def parameter_name(tokens: list[Token]) -> str | None:
    """Only a directly forwarded parameter, optionally wrapped in a string cast."""
    while tokens and tokens[0].text == "(" and closing(tokens, 0) == len(tokens) - 1:
        tokens = tokens[1:-1]
    if len(tokens) == 1 and tokens[0].kind == "name":
        return tokens[0].text
    if (len(tokens) >= 3 and tokens[0].text in ("str", "String", "StringName")
            and tokens[1].text == "(" and closing(tokens, 1) == len(tokens) - 1):
        return parameter_name(tokens[2:-1])
    return None


def argument_positions(name: str, wrappers: dict[str, set[int]]) -> set[int]:
    if name in wrappers:
        return wrappers[name]
    if name.startswith("self.") and name[5:] in wrappers:
        return wrappers[name[5:]]
    if name == "tr" or name.endswith(".tr"):
        return {0}
    if name in WRAPPERS:
        return {WRAPPERS[name]}
    return set()


def imported_scripts(tokens: list[Token]) -> dict[str, str]:
    """Resolve module-level preload aliases used by the game's static helpers."""
    imports = {}
    for i, token in enumerate(tokens[:-7]):
        if token.text != "const" or token.column != 0 or tokens[i + 1].kind != "name":
            continue
        equal = i + 2
        while equal < len(tokens) and tokens[equal].line == token.line and tokens[equal].text != "=":
            equal += 1
        if equal + 4 >= len(tokens) or tokens[equal].text != "=":
            continue
        value = tokens[equal + 1:equal + 5]
        if value[0].text == "preload" and value[1].text == "(" and value[2].kind == "string" and value[3].text == ")":
            path = unescape(value[2].text)
            if path.startswith("res://") and path.endswith(".gd"):
                imports[tokens[i + 1].text] = "game/" + path[6:]
    return imports


def discover_wrappers(scripts: dict[str, list[Token]]) -> dict[str, dict[str, set[int]]]:
    """Follow direct parameter forwarding, including chains and preload helpers."""
    declarations = {path: list(functions(tokens)) for path, tokens in scripts.items()}
    call_sites = {path: list(calls(tokens)) for path, tokens in scripts.items()}
    imports = {path: imported_scripts(tokens) for path, tokens in scripts.items()}
    local: dict[str, dict[str, set[int]]] = {path: {} for path in scripts}

    def scoped(path):
        wrappers = dict(local[path])
        for alias, target in imports[path].items():
            for name, positions in local.get(target, {}).items():
                wrappers[f"{alias}.{name}"] = positions
        return wrappers

    changed = True
    while changed:
        changed = False
        for path, declarations_in_file in declarations.items():
            wrappers = scoped(path)
            for name, params, first, last in declarations_in_file:
                positions = set(local[path].get(name, ()))
                for callee, args, line in call_sites[path]:
                    if not first <= line < last:
                        continue
                    for position in argument_positions(callee, wrappers):
                        forwarded = parameter_name(args[position]) if position < len(args) else None
                        if forwarded in params:
                            positions.add(params.index(forwarded))
                if positions and positions != local[path].get(name):
                    local[path][name] = positions
                    changed = True
    return {path: scoped(path) for path in scripts}


def extract_references(source: str, path: str, *, tokens: list[Token] | None = None,
                       wrappers: dict[str, set[int]] | None = None) -> list[Reference]:
    tokens = tokenize(source) if tokens is None else tokens
    wrappers = discover_wrappers({path: tokens})[path] if wrappers is None else wrappers
    references = []
    for name, args, _ in calls(tokens):
        for position in argument_positions(name, wrappers):
            if position < len(args):
                for key, line in literal_values(args[position]):
                    if is_text(key):
                        references.append(Reference(path, line, key))
    return sorted(set(references), key=lambda ref: (ref.path, ref.line, ref.key))


def check(root: Path = ROOT) -> Result:
    root = Path(root)
    catalog_path = root / "game/i18n/strings.json"
    catalog_text = catalog_path.read_text(encoding="utf-8-sig")
    catalog = json.loads(catalog_text)["strings"]
    if not isinstance(catalog, dict):
        raise ValueError("strings.json의 strings는 객체여야 합니다.")
    scripts = sorted((root / "game").rglob("*.gd"))
    tokens = {path.relative_to(root).as_posix(): tokenize(path.read_text(encoding="utf-8-sig")) for path in scripts}
    wrappers = discover_wrappers(tokens)
    references = tuple(ref for path in tokens for ref in extract_references(
        "", path, tokens=tokens[path], wrappers=wrappers[path]))
    by_key: dict[str, list[Reference]] = {}
    for ref in references:
        by_key.setdefault(ref.key, []).append(ref)
    # Also validate catalog-only entries, used by dynamically translated strings.
    catalog_lines = {}
    for line, text in enumerate(catalog_text.splitlines(), 1):
        match = re.match(r'\s*("(?:\\.|[^"\\])*")\s*:', text)
        if match:
            catalog_lines.setdefault(json.loads(match.group(1)), line)
    issues = []
    for key in sorted(set(by_key) | {key for key in catalog if is_text(key)}):
        missing = key not in catalog
        entry = catalog.get(key)
        languages = tuple(language for language in LANGUAGES if not isinstance(entry, dict)
                          or not isinstance(entry.get(language), str) or not entry[language].strip())
        if missing or languages:
            locations = tuple(by_key.get(key, [Reference("game/i18n/strings.json", catalog_lines.get(key, 1), key)]))
            issues.append(Issue(key, locations, missing, languages))
    return Result(len(scripts), references, tuple(issues))


def korean_report(result: Result) -> str:
    language_count = sum(not issue.missing_key for issue in result.issues)
    lines = ["# 번역 누락 점검", "",
             "`python tools/i18n_check.py --report docs/I18N_MISSING_KO.md`로 재생성합니다.", "",
             f"- 검사: `game/**/*.gd` {result.script_count}개, 번역 문자열 {len({ref.key for ref in result.references})}개(중복 제외).",
             f"- 카탈로그에 없는 키: **{result.missing_key_count}개**.",
             f"- 기존 키의 `en` 또는 `zh` 값 누락: **{language_count}개**.", "",
             "`tr`, `TranslationServer.translate`, `I18n.t/server`, `t.call`, 로컬 `t/_t`, "
             "`DayFolk.line` 및 이 함수들에 인수를 직접 전달하는 래퍼를 검사합니다. "
             "래퍼는 파일별로 탐지하며 `preload` 별칭과 래퍼 간 전달도 추적합니다. "
             "조건식의 문자열 분기와 리터럴 결합도 포함합니다. "
             "주석·기호·서식 전용 값은 제외하고 변수·조회 결과 등 동적 인수는 추론하지 않습니다. "
             "카탈로그의 기존 텍스트 키는 사용 여부와 관계없이 두 언어의 빈 값도 검사합니다.", ""]
    if not result.issues:
        lines.append("누락 없음.")
    else:
        lines.extend(["| 누락 | 위치 (파일:줄) | 키 |", "| --- | --- | --- |"])
        for issue in sorted(result.issues, key=lambda item: (item.locations[0].path, item.locations[0].line, item.key)):
            kind = "키 없음" if issue.missing_key else ", ".join(issue.languages)
            locations = "<br>".join(f"`{ref.path}:{ref.line}`" for ref in issue.locations)
            key = json.dumps(issue.key, ensure_ascii=False).replace("|", "&#124;").replace("`", "&#96;")
            lines.append(f"| {kind} | {locations} | {key} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root (default: this script's repository)")
    parser.add_argument("--report", type=Path, help="Write a Korean Markdown report (relative to --root)")
    args = parser.parse_args(argv)
    result = check(args.root)
    report = korean_report(result)
    if args.report:
        destination = args.report if args.report.is_absolute() else args.root / args.report
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(report, encoding="utf-8")
    print(report, end="")
    return int(bool(result.issues))


if __name__ == "__main__":
    raise SystemExit(main())
