"""Small, isolated fixture projects for the GDScript structure checker."""

from pathlib import Path
import tempfile
import unittest

from tools.predeploy.common import Context, Source, lex
from tools.predeploy.script_rules import check_scripts


class ScriptRulesTests(unittest.TestCase):
    def check(self, fixture: dict[str, str]):
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            sources = {}
            for name, text in fixture.items():
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(text, encoding="utf-8")
                if name.endswith(".gd"):
                    sources[name] = Source(path, name, text, lex(text))
            ctx = Context(root, sources, set(fixture))
            check_scripts(ctx)
            return ctx.findings

    def test_duplicate_top_level_names_across_kinds(self):
        findings = self.check({"main.gd": """extends Node
signal changed
@export var changed: int
static func repeat(): pass
static var repeat: int
const EXISTING = 1
const EXISTING = 2
"""})
        self.assertEqual([(f.code, f.line) for f in findings], [
            ("duplicate-declaration", 3),
            ("duplicate-declaration", 5),
            ("duplicate-declaration", 7),
        ])

    def test_inner_classes_locals_comments_strings_are_not_top_level(self):
        self.assertEqual(self.check({"main.gd": '''extends Node
var same: int
class Inner:
    var same: int
    func run(): pass
func run():
    var same = "func run(): preload('res://missing.gd')"
    # var same = 2
    var text = """const same = 3
func run(): pass"""
func another():
    var same = 4
'''}), [])

    def test_preload_missing_multiline_and_relative_paths(self):
        findings = self.check({
            "scripts/main.gd": '''const Exists = preload("helper.gd")
const Missing = preload(
    "res://absent.gd"
)
const Folder = preload("res://scripts")
''',
            "scripts/helper.gd": "extends RefCounted\n",
        })
        self.assertEqual([(f.code, f.line) for f in findings], [
            ("missing-preload", 3), ("missing-preload", 5)])

    def test_extends_named_native_relative_missing_and_inner(self):
        findings = self.check({
            "base.gd": "class_name Known\nextends Node\n",
            "child.gd": "extends Known\n",
            "native.gd": "extends SkeletonModifier3D\n",
            "relative.gd": "extends 'base.gd'\n",
            "missing_class.gd": "extends MissingCustomClass\n",
            "missing_path.gd": "extends 'absent.gd'\n",
            "inner.gd": "class Child:\n    extends 'absent.gd'\n",
        })
        self.assertEqual(sorted((f.code, f.file, f.line) for f in findings), [
            ("missing-extends", "inner.gd", 2),
            ("missing-extends", "missing_class.gd", 1),
            ("missing-extends", "missing_path.gd", 1),
        ])

    def test_method_lookup_follows_class_names_and_script_parents(self):
        findings = self.check({
            "base.gd": "class_name Base\nextends RefCounted\nstatic func inherited(): pass\n",
            "middle.gd": "extends Base\n",
            "child.gd": "class_name Child\nextends 'middle.gd'\nstatic func own(): pass\n",
            "main.gd": '''const Alias = preload("res://child.gd")
func run():
    Child.inherited()
    Alias.inherited()
    Child.own()
    Alias.new()
    Alias.get_script_method_list()
    Child.absent()
    Alias.absent()
''',
        })
        self.assertEqual([(f.code, f.line) for f in findings], [
            ("missing-method", 8), ("missing-method", 9)])

    def test_shadowed_class_names_and_non_script_preload_are_skipped(self):
        self.assertEqual(self.check({
            "class.gd": "class_name Helper\nextends Node\n",
            "scene.tscn": "[gd_scene format=3]\n",
            "main.gd": '''const Scene = preload("res://scene.tscn")
func parameter(Helper):
    Helper.anything()
func local():
    var Helper = {}
    Helper.anything()
func inline(): var Helper = {}; Helper.anything()
func lambda():
    signal_name.connect(func(Helper): Helper.anything())
func scene():
    Scene.instantiate()
    NativeThing.anything()
    object.Helper.anything()
class Inner:
    var Helper = {}
    func run():
        Helper.anything()
''',
        }), [])

    def test_local_const_preload_is_checked(self):
        findings = self.check({
            "helper.gd": "extends RefCounted\nstatic func good(): pass\n",
            "main.gd": '''func run():
    const Helper = preload("res://helper.gd")
    Helper.good()
    Helper.missing()
''',
        })
        self.assertEqual([(f.code, f.line) for f in findings], [("missing-method", 4)])

    def test_unresolved_inheritance_does_not_invent_missing_methods(self):
        self.assertEqual(self.check({
            "special.gd": "class_name Special\nextends Image\n",
            "outer.gd": "class Nested:\n    static func known(): pass\n",
            "inner.gd": "class_name Inner\nextends 'outer.gd'.Nested\n",
            "main.gd": "func run():\n    Special.create(1, 1, false, 0)\n    Inner.known()\n",
        }), [])

    def test_outside_project_and_uid_script_paths(self):
        findings = self.check({"main.gd": '''extends "res://../outside.gd"
const Outside = preload("res://../outside.gd")
const Relative = preload("../outside.gd")
const ByUid = preload("uid://abcdef")
class Inner:
    extends "uid://ghijkl"
'''})
        self.assertEqual([(f.severity, f.code, f.line) for f in findings], [
            ("blocker", "missing-extends", 1),
            ("blocker", "missing-preload", 2),
            ("blocker", "missing-preload", 3),
            ("warning", "unresolved-preload", 4),
            ("warning", "unresolved-extends", 6),
        ])

    def test_semicolon_top_level_declarations_and_inline_function_body(self):
        findings = self.check({"main.gd": '''var value = 1; var value = 2
@export var other = 3; const other = 4
func inline(): var local = 1; var local = 2
func next():
    var value = 5; var value = 6
'''})
        self.assertEqual([(f.code, f.line) for f in findings], [
            ("duplicate-declaration", 1), ("duplicate-declaration", 2)])

    def test_string_keyword_does_not_become_a_declaration(self):
        self.assertEqual(self.check({"main.gd": '''var value = 1
"var" value
"extends" MissingClass
"preload"("res://missing.gd")
"static" var value
'''}), [])

    def test_nested_class_parent_names_respect_enclosing_scope(self):
        findings = self.check({"main.gd": '''class Outer:
    class InnerBase:
        pass
    class Child extends InnerBase:
        pass
class Other extends InnerBase:
    pass
var NotAClass = 1
class Invalid extends NotAClass:
    pass
'''})
        self.assertEqual([(f.code, f.line) for f in findings], [
            ("missing-extends", 6), ("missing-extends", 9)])


if __name__ == "__main__":
    unittest.main()
