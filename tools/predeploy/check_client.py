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
from tools.predeploy.asset_policy import apply_policy, configure_context, excluded_source
from tools.predeploy.project_rules import check_project_settings
from tools.predeploy.resource_rules import check_resources
from tools.predeploy.script_rules import check_scripts
from tools.predeploy.signal_rules import check_signals


EXTENSIONS = {".gd", ".tscn", ".tres", ".gdshader", ".json"}
ASSET_CODES = {"build-time-asset", "missing-build-asset"}


def _is_link(path: Path) -> bool:
    """Do not follow asset junctions implicitly during a source-only scan."""
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def check_project(project_root: Path, assets_root: Path | None = None) -> list[Finding]:
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
                         and not _is_link(Path(folder) / d))
        ctx.directories.update((Path(folder) / d).relative_to(root).as_posix() for d in dirs)
        for name in sorted(names):
            path = Path(folder) / name
            if _is_link(path):
                continue
            ctx.files.add(path.relative_to(root).as_posix())
    for relative in sorted(ctx.files):
        path = root / relative
        if excluded_source(relative):
            continue
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
    # External asset names can satisfy references, but must never be parsed as
    # project scripts/configuration or introduce declarations into the checks.
    configure_context(ctx, assets_root)
    check_resources(ctx)
    check_scripts(ctx)
    check_project_settings(ctx)
    check_signals(ctx)
    apply_policy(ctx)
    return sorted(ctx.findings, key=lambda f: (f.file, f.line, f.severity, f.code, f.message))


def _one_line(value: str, limit: int = 240) -> str:
    value = " ".join(value.split())
    return value if len(value) <= limit else value[:limit - 3] + "..."


def _scope(assets_root: Path | None) -> str:
    if assets_root is None:
        return "Scope: source-only; build-time assets require --assets-root validation."
    return f"Scope: supplied assets at {_one_line(str(assets_root.resolve()))}"


def _summary(findings: list[Finding], assets_root: Path | None) -> list[str]:
    """Keep the report within 30 physical lines, including unusual filenames."""
    blockers = sorted((finding for finding in findings if finding.severity == "blocker"),
                      key=lambda finding: finding.code == "missing-build-asset")
    warnings = sum(finding.severity == "warning" for finding in findings)
    assets = [finding for finding in findings if finding.code in ASSET_CODES]
    statuses = ", ".join(f"{status}={sum(f.status == status for f in assets)}"
                         for status in ("missing", "available", "generated", "pattern"))
    lines = [_scope(assets_root),
             f"Result: {len(blockers)} blocker(s), {warnings} warning(s).",
             f"Build-time assets: {len(assets)} reference(s); {statuses}."]
    if not blockers:
        lines.append("Blockers: none.")
    for finding in blockers[:26]:
        lines.append(_one_line(f"BLOCKER {finding.file}:{finding.line} "
                               f"[{finding.code}] {finding.message}"))
    if len(blockers) > 26:
        lines.append(f"... {len(blockers) - 26} more blocker(s); use --json for the complete report.")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=Path(__file__).resolve().parents[2] / "game",
                        help="Godot project directory (default: this repository's game/)")
    parser.add_argument("--assets-root", type=Path,
                        help="Asset directory to validate build-time resources before building")
    output = parser.add_mutually_exclusive_group()
    output.add_argument("--json", action="store_true", help="Write a machine-readable JSON report to stdout")
    output.add_argument("--summary", action="store_true", help="Write a summary of at most 30 lines")
    args = parser.parse_args(argv)
    findings = check_project(args.project_root, assets_root=args.assets_root)
    blockers = sum(f.severity == "blocker" for f in findings)
    warnings = sum(f.severity == "warning" for f in findings)
    assets = [finding for finding in findings if finding.code in ASSET_CODES]
    if args.json:
        payload = {"project_root": str(args.project_root.resolve()), "blockers": blockers,
                   "warnings": warnings, "findings": [asdict(f) for f in findings],
                   "build_time_assets": [asdict(f) for f in assets]}
        if args.assets_root is not None:
            payload["assets_root"] = str(args.assets_root.resolve())
        print(json.dumps(payload, ensure_ascii=True, indent=2))
    elif args.summary:
        print("\n".join(_summary(findings, args.assets_root)))
    else:
        print(_scope(args.assets_root))
        for finding in findings:
            if finding.code in ASSET_CODES:
                continue
            print(f"{finding.severity.upper()} {args.project_root.name}/{finding.file}:{finding.line} "
                  f"[{finding.code}] {finding.message}")
        if assets:
            print("Build-time assets:")
            for finding in assets:
                print(f"  {finding.status}: {finding.resource} "
                      f"({finding.file}:{finding.line}) [{finding.code}] {finding.message}")
        print(f"Result: {blockers} blocker(s), {warnings} warning(s).")
    return 1 if blockers else 0


if __name__ == "__main__":
    raise SystemExit(main())
