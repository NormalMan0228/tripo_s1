"""Repository-backed build inputs; never treat every ignored path as optional.

Only declared DevAssets folders and the bake scripts' explicit output lists are
eligible. External folders supply binary assets, never scripts or manifests to
scan. No producer, Git command, Godot process or network request is executed.
"""
from __future__ import annotations

import ast
from dataclasses import dataclass
import fnmatch
from pathlib import Path, PurePosixPath
import re

from .common import Context, Source, arguments, lex, significant


COPY_ROOTS = {
    "assets/interior", "assets/monsters", "assets/npc", "assets/portraits",
    "maps/archipelago/assets", "maps/survival/assets",
}
BINARY_SUFFIXES = {".glb", ".gltf", ".bin", ".png", ".jpg", ".jpeg", ".webp",
                   ".tga", ".exr", ".ktx", ".res", ".scn"}


def excluded_source(relative: str) -> bool:
    """Exclude developer entry points, not runtime scripts with tool features."""
    return relative.split("/", 1)[0] in {"tests", "tools"}


def _literal_lists(text: str) -> dict[str, list[str]]:
    result = {}
    try:
        tree = ast.parse(text)
    except SyntaxError:
        return result
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        try:
            value = ast.literal_eval(node.value)
        except (ValueError, TypeError, SyntaxError):
            continue
        if isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    result[target.id] = list(value)
    return result


def _glob(path: str, pattern: str) -> bool:
    # Git '*' does not cross a slash. '**' can span directories.
    parts, wanted = path.split("/"), pattern.split("/")
    def match(i: int, j: int) -> bool:
        if j == len(wanted):
            return i == len(parts)
        if wanted[j] == "**":
            return match(i, j + 1) or (i < len(parts) and match(i + 1, j))
        return i < len(parts) and fnmatch.fnmatchcase(parts[i], wanted[j]) and match(i + 1, j + 1)
    return match(0, 0)


def _ignored(path: str, rules: list[str]) -> bool:
    """Evaluate root .gitignore rules for the narrowly allowlisted asset roots."""
    result = False
    ancestors = ["/".join(path.split("/")[:i]) for i in range(1, len(path.split("/")) + 1)]
    for raw in rules:
        if not raw or raw.startswith("#"):
            continue
        negate = raw.startswith("!")
        pattern = raw[1:] if negate else raw
        anchored = "/" in pattern.rstrip("/")
        pattern = pattern.strip("/")
        if any(_glob(part, pattern) if anchored else fnmatch.fnmatchcase(part.rsplit("/", 1)[-1], pattern)
               for part in ancestors):
            result = not negate
    return result


@dataclass(frozen=True)
class AssetGroup:
    prefix: str
    evidence: str
    outputs: tuple[str, ...] | None = None

    @property
    def generated(self) -> bool:
        return self.outputs is not None


class AssetPolicy:
    def __init__(self, ctx: Context, assets_root: Path | None):
        self.root = ctx.root
        self.repo = ctx.root.parent
        self.strict = assets_root is not None
        self.rules = self.read(".gitignore").splitlines()
        package = _literal_lists(self.read("tools/package_release.py"))
        packaged = package.get("MAP_ASSETS", []) + package.get("ART_ASSETS", [])
        self.groups = [AssetGroup(prefix, f".gitignore; tools/package_release.py: {prefix}")
                       for prefix in sorted(COPY_ROOTS) if f"game/{prefix}" in packaged]
        manifests = {
            "assets/monsters": ("assets/monsters/manifest.json",),
            "assets/interior": ("assets/interior/manifest.json",),
            "maps/survival/assets": ("maps/survival/assets/manifest.json",),
            "maps/archipelago/assets": ("maps/archipelago/building_placements.json",
                                         "maps/archipelago/environment_layout.json",
                                         "maps/archipelago/door_leaves.json"),
        }
        self.declared: dict[str, set[str]] = {}
        for prefix, names in manifests.items():
            sources = [ctx.sources[name] for name in names if name in ctx.sources]
            if sources:
                self.declared[prefix] = {
                    token.value[6:] for source in sources for token in source.tokens
                    if token.kind == "STRING" and token.value.startswith("res://" + prefix + "/")
                }
        build = self.read("tools/build_game.ps1")
        build_code = "".join(token.value for token in lex(build, line_comments=("#",)))
        for area in ("archipelago", "survival"):
            producer = f"tools/bake_{area}.py"
            outputs = [name for name in _literal_lists(self.read(producer)).get("FILES", [])
                       if PurePosixPath(name).name == name
                       and (PurePosixPath(name).suffix in {".res", ".scn"} or name == "manifest.json")]
            if f"bake_{area}.py" in build_code and outputs:
                self.groups.append(AssetGroup(f"maps/{area}/generated",
                                             f".gitignore; tools/build_game.ps1; {producer} FILES; "
                                             "tools/package_release.py / tools/game_patch.py bake validation",
                                             tuple(outputs)))
        self.export_binary = ("--export-release" in build_code
                              and "project.binary" in self.read("tools/game_patch.py"))

    def read(self, relative: str) -> str:
        try:
            return (self.repo / relative).read_text(encoding="utf-8-sig")
        except (OSError, UnicodeError):
            # Missing evidence must fail closed, never broaden exemptions.
            return ""

    def group(self, resource: str) -> AssetGroup | None:
        if not resource.startswith("res://"):
            return None
        relative = resource[6:].split("::", 1)[0].rstrip("/")
        if ".." in PurePosixPath(relative).parts or "\\" in relative:
            return None
        for group in self.groups:
            if relative != group.prefix and not relative.startswith(group.prefix + "/"):
                continue
            if not _ignored("game/" + relative, self.rules):
                # Interior/monster rules ignore children, not the folder itself.
                if relative != group.prefix or not _ignored("game/" + relative + "/__asset__.glb", self.rules):
                    continue
            if group.generated:
                if relative == group.prefix or any(fnmatch.fnmatchcase(group.prefix + "/" + name, relative)
                                                   for name in group.outputs or ()):
                    return group
            elif (resource.endswith("/") or relative == group.prefix
                  or PurePosixPath(relative).suffix.lower() in BINARY_SUFFIXES
                  or "*" in relative):
                # A missing .gd/.json/.svg under an ignored folder is still a defect.
                if (PurePosixPath(relative).suffix.lower() == ".glb" and "*" not in relative
                        and group.prefix in self.declared and relative not in self.declared[group.prefix]
                        and (group.prefix != "maps/archipelago/assets" or PurePosixPath(relative).parent in {
                            PurePosixPath(name).parent for name in self.declared[group.prefix]
                        })):
                    continue  # Manifest-backed folders must not hide a typo in a runtime reference.
                return group
        return None

    def present(self, ctx: Context, resource: str) -> bool:
        relative = ctx.resource_relative(resource)
        if relative is None:
            return False
        if resource.endswith("/"):
            return ctx.exists(resource)
        return relative in ctx.files

    def inspect(self, ctx: Context, source: Source, line: int, resource: str, dynamic: bool,
                position: int | None = None) -> bool:
        # These are capture destinations / optional authoring metadata in runtime
        # scripts. Do not exempt the script itself or other res://../ references.
        output = {
            "maps/archipelago/building_layout.gd": "res://../art/maps/archipelago_placement_v1/",
            "maps/archipelago/environment_layout.gd": "res://../art/maps/archipelago_environment_v1/",
        }.get(source.relative)
        if output and resource.startswith(output):
            return True
        if (source.relative == "maps/archipelago/environment_layout.gd" and resource == "res://../*/"
                and source.text.splitlines()[line - 1].lstrip().startswith("output_path =")):
            return True
        # The SAMPLES dictionary is passed to SfxBank.pick, then expanded to
        # <family>_<number>.wav. Require actual takes instead of hiding typos.
        if (source.relative == "scripts/life_sfx.gd" and _in_samples(source, position)
                and re.fullmatch(r"res://assets/sfx/combat/harvest_\w+", resource)):
            if any(re.fullmatch(re.escape(resource[6:]) + r"_\d+\.wav", name) for name in ctx.files):
                return True
            ctx.emit("blocker", "missing-sound-family", source, line,
                     f"No numbered WAV takes for sound family {resource}; restore <family>_1.wav.", resource=resource)
            return True
        if self.export_binary and resource == "res://project.binary" and source.relative == "scripts/patch_boot.gd":
            ctx.emit("build-time", "build-time-asset", source, line,
                     "Godot export creates res://project.binary; patch settings are read from the exported PCK.",
                     resource=resource, status="generated",
                     evidence="tools/build_game.ps1 --export-release; tools/game_patch.py project_settings/pack_version")
            return True
        group = self.group(resource)
        if group is None:
            return False
        if dynamic and "*" in resource:
            matches = sorted(name for name in ctx.files if fnmatch.fnmatchcase("res://" + name, resource))
            status = "generated" if group.generated else "pattern"
            message = (f"Build-time pattern {resource}: {len(matches)} matching file(s). "
                       "Runtime values remain unchecked; inspect the manifest and required asset entries.")
            if matches:
                message += " Examples: " + ", ".join(matches[:3])
        else:
            # Constants composed only from strings have no unknown runtime values.
            status = "generated" if group.generated else ("available" if self.present(ctx, resource) else "missing")
            message = f"Build-time asset {resource}: {status}."
            if status == "missing":
                message += " Restore it from DevAssets (repository-relative paths), then use --assets-root."
            elif status == "generated":
                message += " The build must regenerate/validate this output; existence does not prove freshness."
        missing = self.strict and status == "missing"
        ctx.emit("blocker" if missing else "build-time", "missing-build-asset" if missing else "build-time-asset",
                 source, line, message, resource=resource, status=status, evidence=group.evidence)
        return True

    def overlay(self, ctx: Context, supplied: Path) -> None:
        supplied = supplied.absolute()
        # Accept a checkout / extracted DevAssets archive root, or a game root.
        if not supplied.is_dir():
            ctx.emit("blocker", "invalid-assets-root", "project.godot", 1,
                     f"Asset directory does not exist: {supplied}")
            return
        base = supplied / "game" if (supplied / "game").is_dir() else supplied
        if not any((base / name).is_dir() for name in ("assets", "maps")):
            ctx.emit("blocker", "invalid-assets-root", "project.godot", 1,
                     f"Expected a repository root with game/ or a game root with assets/ or maps/: {supplied}")
            return

        def walk(folder: Path, relative: str, ancestors: frozenset[Path]) -> None:
            try:
                real = folder.resolve()
                if real in ancestors:
                    ctx.emit("blocker", "asset-link-cycle", relative, 1, f"Cyclic asset directory link: {folder}")
                    return
                entries = sorted(folder.iterdir(), key=lambda item: item.name)
                ctx.directories.add(relative)
                for entry in entries:
                    name = relative + "/" + entry.name
                    if entry.is_dir():
                        if entry.name not in {".godot", ".git", "__pycache__"}:
                            walk(entry, name, ancestors | {real})
                    elif (entry.is_file() and _ignored("game/" + name, self.rules)
                          and (entry.suffix.lower() in BINARY_SUFFIXES or self.group("res://" + name) is not None)):
                        ctx.files.add(name)
            except (OSError, RuntimeError) as error:
                ctx.emit("blocker", "unreadable-assets", relative, 1, str(error))

        for group in self.groups:
            # Enumerate each component exactly even on Windows. An incorrectly
            # cased folder must not silently satisfy a Godot resource path.
            cursor = base
            try:
                for part in group.prefix.split("/"):
                    if part not in {entry.name for entry in cursor.iterdir()}:
                        break
                    cursor /= part
                else:
                    if cursor.is_dir():
                        walk(cursor, group.prefix, frozenset())
            except OSError as error:
                ctx.emit("blocker", "unreadable-assets", group.prefix, 1, str(error))


def configure_context(ctx: Context, assets_root: Path | None) -> None:
    ctx.asset_policy = AssetPolicy(ctx, assets_root)
    if assets_root is not None:
        ctx.asset_policy.overlay(ctx, Path(assets_root))


def _in_samples(source: Source, position: int | None) -> bool:
    """Only SAMPLES dictionary values are families; a direct load is a file."""
    tokens = significant(source.tokens)
    for index, token in enumerate(tokens):
        if token.value != "const" or token.column != 0 or index + 1 >= len(tokens) or tokens[index + 1].value != "SAMPLES":
            continue
        start = index + 2
        while start < len(tokens) and tokens[start].line == token.line and tokens[start].value != "{":
            start += 1
        if start < len(tokens) and tokens[start].value == "{":
            _, end = arguments(tokens, start)
            return position is not None and tokens[start].start < position < tokens[end].end
    return False


def apply_policy(ctx: Context) -> None:
    policy = ctx.asset_policy
    if policy is None:
        return
    # Resource checks already classify literal preload paths; remove only that
    # duplicate structural diagnostic, leaving ordinary missing scripts intact.
    ctx.findings[:] = [finding for finding in ctx.findings if not (
        finding.code == "missing-preload" and finding.resource and policy.group(finding.resource) is not None
        and any(other.file == finding.file and other.line == finding.line and other.resource == finding.resource
                and other.code in {"build-time-asset", "missing-build-asset"} for other in ctx.findings)
    )]
    # main.gd's finite CAST table supplies four NPC models and portraits. A broad
    # '*.glb' match alone must not make a partial cast look complete.
    source = ctx.sources.get("scripts/main.gd")
    if source is None:
        return
    tokens = significant(source.tokens)
    for index, token in enumerate(tokens):
        if token.value != "const" or token.column != 0 or index + 1 >= len(tokens) or tokens[index + 1].value != "CAST":
            continue
        start = index + 2
        while start < len(tokens) and tokens[start].value not in {"[", "func", "const"}:
            start += 1
        if start >= len(tokens) or tokens[start].value != "[":
            continue
        _, end = arguments(tokens, start)
        for cursor in range(start + 1, end - 2):
            key, colon, value = tokens[cursor:cursor + 3]
            if key.kind == "STRING" and key.value == "cast" and colon.value == ":" and value.kind == "STRING":
                if re.fullmatch(r"[a-zA-Z0-9_-]+", value.value):
                    for folder, suffix in (("npc", "glb"), ("portraits", "png")):
                        policy.inspect(ctx, source, value.line, f"res://assets/{folder}/{value.value}.{suffix}", False)
