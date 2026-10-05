"""Korean-source localisation helpers for the Godot client.

wrap     Wrap user-facing Korean string literals in game/scripts with tr() (or
         TranslationServer.translate() inside static functions). Constants,
         dictionary keys, comparisons and log calls are left alone; constant
         data is translated where it is displayed.
extract  Write every Korean literal from the client and the server's player-facing
         modules to game/i18n/source.json, keeping translations already present in
         game/i18n/strings.json.
merge    Merge translated JSON files ({"ko text": "translation"}) for one language
         into game/i18n/strings.json.
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "game" / "scripts"
CATALOG = ROOT / "game" / "i18n" / "strings.json"
SOURCE = ROOT / "game" / "i18n" / "source.json"
SERVER_FILES = ["app.py", "campaign.py", "catalog.py", "coop.py", "homestead.py", "simulation.py", "multiplayer.py"]
SKIP_SCRIPTS = {"i18n.gd"}
HANGUL = re.compile(r"[가-힣]")
LITERAL = re.compile(r'"((?:[^"\\\n]|\\.)*)"')
LOG_CALL = re.compile(r"\b(print|printerr|push_error|push_warning|assert)\s*\($")


def wrap_file(path: Path) -> int:
    lines = path.read_text(encoding="utf-8").split("\n")
    changed = 0
    in_const = 0
    static = False
    for n, line in enumerate(lines):
        stripped = line.lstrip()
        if re.match(r"(static\s+)?func\s", stripped) and not line.startswith((" ", "\t")):
            static = stripped.startswith("static")
        if stripped.startswith("#"):
            continue
        if in_const or re.match(r"const\s", stripped):
            depth = line.count("[") + line.count("{") + line.count("(") - line.count("]") - line.count("}") - line.count(")")
            in_const = max(0, in_const + depth) if in_const or depth > 0 else 0
            continue
        out, last = [], 0
        for match in LITERAL.finditer(line):
            if not HANGUL.search(match.group(1)):
                continue
            before, after = line[:match.start()], line[match.end():]
            if re.search(r"(\btr|translate|I18n\.t|I18n\.server)\(\s*$", before):
                continue
            if re.match(r"\s*:", after) and not re.search(r"\bif\b", before):
                continue  # dictionary key or match pattern
            if re.search(r"(==|!=|\bin)\s*$", before) or re.match(r"\s*(==|!=|\bin\b)", after):
                continue
            if LOG_CALL.search(before.rstrip()):
                continue
            call = "TranslationServer.translate" if static else "tr"
            out.append(line[last:match.start()] + f"{call}({match.group(0)})")
            last = match.end()
            changed += 1
        if out:
            lines[n] = "".join(out) + line[last:]
    path.write_text("\n".join(lines), encoding="utf-8", newline="")
    return changed


def unescape(value: str) -> str:
    return value.replace("\\n", "\n").replace('\\"', '"').replace("\\'", "'")


def literals(text: str, pattern: re.Pattern) -> list[str]:
    return [m.group(1) for m in pattern.finditer(text) if HANGUL.search(m.group(1))]


def extract() -> None:
    strings: dict[str, dict] = {}
    for path in sorted(SCRIPTS.glob("*.gd")):
        for value in literals(path.read_text(encoding="utf-8"), LITERAL):
            strings.setdefault(unescape(value), {"where": path.name})
    py = re.compile(r"""(?<![A-Za-z_])['"]((?:[^'"\\\n]|\\.)*)['"]""")
    for name in SERVER_FILES:
        text = (ROOT / "server" / name).read_text(encoding="utf-8")
        for value in literals(text, py):
            if "{" in value:
                continue  # f-string templates are listed separately
            strings.setdefault(unescape(value), {"where": "server/" + name})
    known = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {"strings": {}, "templates": []}
    for key, entry in strings.items():
        entry.update({k: v for k, v in known["strings"].get(key, {}).items() if k in ("en", "zh")})
    SOURCE.parent.mkdir(parents=True, exist_ok=True)
    SOURCE.write_text(json.dumps(strings, ensure_ascii=False, indent=1), encoding="utf-8")
    missing = sum(1 for e in strings.values() if not (e.get("en") and e.get("zh")))
    print(f"{len(strings)} strings, {missing} need translation -> {SOURCE.relative_to(ROOT)}")


def merge(language: str, files: list[str]) -> None:
    catalog = json.loads(CATALOG.read_text(encoding="utf-8")) if CATALOG.exists() else {"strings": {}, "templates": []}
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    for name in files:
        for key, value in json.loads(Path(name).read_text(encoding="utf-8")).items():
            if key in source and value:
                catalog["strings"].setdefault(key, {})[language] = value
    CATALOG.write_text(json.dumps(catalog, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
    done = sum(1 for e in catalog["strings"].values() if e.get(language))
    print(f"{language}: {done} translated in {CATALOG.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["wrap", "extract", "merge"])
    parser.add_argument("--language")
    parser.add_argument("files", nargs="*")
    args = parser.parse_args()
    if args.command == "wrap":
        total = 0
        for path in sorted(SCRIPTS.glob("*.gd")):
            if path.name not in SKIP_SCRIPTS:
                total += wrap_file(path)
        print("wrapped", total)
    elif args.command == "extract":
        extract()
    else:
        merge(args.language, args.files)


if __name__ == "__main__":
    main()
