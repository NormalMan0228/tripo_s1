#!/usr/bin/env python3
"""Run read-only client pre-deploy checks without importing or starting Godot."""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.predeploy.common import Context, Finding, Source, lex
from tools.predeploy.project_rules import check_project_settings
from tools.predeploy.resource_rules import check_resources
from tools.predeploy.script_rules import check_scripts
from tools.predeploy.signal_rules import check_signals


EXTENSIONS = {".gd", ".tscn", ".tres", ".gdshader", ".json"}


def check_project(project_root: Path) -> list[Finding]:
    """Check a Godot project directory and return deterministically ordered findings."""
    root = Path(project_root).resolve()
    ctx = Context(root, {}, set())
    if not root.is_dir():
        ctx.emit("blocker", "missing-project", "project.godot", 1, f"Project directory does not exist: {root}")
        return ctx.findings

    def walk_error(error: OSError) -> None:
        ctx.emit("blocker", "unreadable-file", ".", 1, str(error))

    for folder, dirs, names in os.walk(root, followlinks=False, onerror=walk_error):
        dirs[:] = sorted(d for d in dirs if d not in (".godot", ".git", "__pycache__")
                         and not (Path(folder) / d).is_symlink())
        ctx.directories.update((Path(folder) / d).relative_to(root).as_posix() for d in dirs)
        for name in sorted(names):
            path = Path(folder) / name
            if path.is_symlink():
                continue
            ctx.files.add(path.relative_to(root).as_posix())
    for relative in sorted(ctx.files):
        path = root / relative
        if path.suffix not in EXTENSIONS and relative != "project.godot":
            continue
        try:
            content = path.read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError) as error:
            ctx.emit("blocker", "unreadable-file", relative, 1, str(error))
            continue
        comments = {".tscn": (";", "#"), ".tres": (";", "#"),
                    ".gdshader": ("//",), ".json": ()}.get(path.suffix, ("#", "//"))
        ctx.sources[relative] = Source(path, relative, content, lex(content, line_comments=comments))
    check_resources(ctx)
    check_scripts(ctx)
    check_project_settings(ctx)
    check_signals(ctx)
    return sorted(ctx.findings, key=lambda f: (f.file, f.line, f.severity, f.code, f.message))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2] / "game",
                        help="Godot project directory (default: this repository's game/)")
    parser.add_argument("--json", action="store_true", help="Write a machine-readable JSON report to stdout")
    args = parser.parse_args(argv)
    findings = check_project(args.project_root)
    blockers = sum(f.severity == "blocker" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    if args.json:
        print(json.dumps({"project_root": str(args.project_root.resolve()), "blockers": blockers,
                          "warnings": warnings, "findings": [asdict(f) for f in findings]},
                         ensure_ascii=True, indent=2))
    else:
        for finding in findings:
            print(f"{finding.severity.upper()} {args.project_root.name}/{finding.file}:{finding.line} "
                  f"[{finding.code}] {finding.message}")
        print(f"Result: {blockers} blocker(s), {warnings} warning(s).")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
