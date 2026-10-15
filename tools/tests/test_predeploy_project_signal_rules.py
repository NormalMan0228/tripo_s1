"""Small on-disk fixtures for project settings and duplicate signal checks."""

from pathlib import Path
import tempfile
import unittest

from tools.predeploy.common import Context, Source, lex
from tools.predeploy.project_rules import check_project_settings
from tools.predeploy.signal_rules import check_signals


class ProjectAndSignalRulesTests(unittest.TestCase):
    def inspect(self, files, checker):
        with tempfile.TemporaryDirectory(prefix="predeploy-fixture-", dir=Path(__file__).resolve().parent) as temporary:
            root = Path(temporary)
            sources = {}
            for relative, content in files.items():
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
                sources[relative] = Source(path, relative, content, lex(content))
            ctx = Context(root, sources, set(files))
            checker(ctx)
            return ctx.findings

    def signals(self, script):
        return self.inspect({"test.gd": script}, check_signals)

    def test_autoload_missing_file_and_directory(self):
        findings = self.inspect({
            "project.godot": '[autoload]\nGood="*res://ok.gd"\nBad="res://missing.gd"\nFolder="res://folder"\n',
            "ok.gd": "extends Node\n",
            "folder/child.gd": "extends Node\n",
        }, check_project_settings)
        self.assertEqual([(item.code, item.line) for item in findings],
                         [("missing-autoload", 3), ("missing-autoload", 4)])

    def test_project_comments_and_path_punctuation(self):
        findings = self.inspect({
            "project.godot": '; comment with {\n[autoload]\nGood="*res://semi;colon.gd" ; comment\n[input]\n"say/hello"={"events": []}\n',
            "semi;colon.gd": 'func f():\n\tInput.is_action_pressed(&"say/hello")\n',
        }, check_project_settings)
        self.assertEqual(findings, [])

    def test_input_api_literal_arguments_and_comments(self):
        findings = self.inspect({
            "project.godot": '[input]\nknown={"events": []}\n',
            "test.gd": ('# Input.is_action_pressed("comment")\n'
                        'var text = \'InputMap.has_action("string")\'\n'
                        'func f():\n'
                        '\tInput.is_action_pressed(\n\t\t&"known"\n\t)\n'
                        '\tInput.is_action_just_released("missing")\n'
                        '\tInputMap.event_is_action(event, "missing_event")\n'
                        '\tInputMap.add_action("runtime_only")\n'
                        '\tInputMap.has_action(action)\n'),
        }, check_project_settings)
        self.assertEqual([item.code for item in findings],
                         ["undefined-input-action"] * 3 + ["dynamic-input-action"])
        self.assertEqual([item.line for item in findings], [7, 8, 9, 10])

    def test_builtin_input_requires_explicit_project_declaration(self):
        findings = self.inspect({"project.godot": "[input]\n",
                                 "test.gd": 'func f(): Input.is_action_pressed("ui_accept")\n'},
                                check_project_settings)
        self.assertEqual([item.code for item in findings], ["undefined-input-action"])

    def test_missing_project(self):
        findings = self.inspect({"test.gd": "extends Node"}, check_project_settings)
        self.assertEqual([item.code for item in findings], ["missing-project-settings"])

    def test_duplicate_signal_reports_later_line(self):
        findings = self.signals("func f():\n\tbutton.pressed.connect(cb)\n\tbutton.pressed.connect(cb)\n")
        self.assertEqual([(item.code, item.line) for item in findings], [("duplicate-signal-connect", 3)])

    def test_functions_and_nested_classes_have_distinct_scopes(self):
        findings = self.signals("func f():\n\tbutton.pressed.connect(cb)\n"
                                "func g():\n\tbutton.pressed.connect(cb)\n"
                                "class Inner:\n\tfunc f():\n\t\tbutton.pressed.connect(cb)\n")
        self.assertEqual(findings, [])

    def test_distinct_receivers_bound_arguments_and_lambdas(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb.bind(1))\n"
                                "\ta.pressed.connect(cb.bind(2))\n\tb.pressed.connect(cb.bind(1))\n"
                                "\ta.pressed.connect(func(): pass)\n\ta.pressed.connect(func(): pass)\n")
        self.assertEqual(findings, [])

    def test_comments_and_strings_do_not_create_connections(self):
        findings = self.signals('func f():\n\t# a.pressed.connect(cb)\n'
                                '\tvar text = "a.pressed.connect(cb)"\n\ta.pressed.connect(cb)\n')
        self.assertEqual(findings, [])

    def test_separate_matching_guards_protect_each_connection(self):
        findings = self.signals("func f():\n\tif not a.pressed.is_connected(cb): a.pressed.connect(cb)\n"
                                "\tif not a.pressed.is_connected(cb):\n\t\ta.pressed.connect(cb)\n")
        self.assertEqual(findings, [])

    def test_one_guard_does_not_protect_two_connections(self):
        findings = self.signals("func f():\n\tif not a.pressed.is_connected(cb):\n"
                                "\t\ta.pressed.connect(cb)\n\t\ta.pressed.connect(cb)\n")
        self.assertEqual(len(findings), 1)

    def test_unrelated_or_late_guard_does_not_hide_duplicates(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb)\n"
                                "\tif not b.pressed.is_connected(cb): a.pressed.connect(cb)\n"
                                "\tif not a.pressed.is_connected(other): a.pressed.connect(cb)\n"
                                "\tif not a.pressed.is_connected(cb): pass\n")
        self.assertEqual(len(findings), 2)

    def test_or_guard_is_not_sufficient(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb)\n"
                                "\tif not a.pressed.is_connected(cb) or enabled: a.pressed.connect(cb)\n")
        self.assertEqual(len(findings), 1)

    def test_double_negation_and_negated_conjunction_are_not_guards(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb)\n"
                                "\tif not not a.pressed.is_connected(cb): a.pressed.connect(cb)\n"
                                "\tif not (a.pressed.is_connected(cb) and enabled): a.pressed.connect(cb)\n")
        self.assertEqual(len(findings), 2)

    def test_false_comparison_is_a_guard(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb)\n"
                                "\tif a.pressed.is_connected(cb) == false: a.pressed.connect(cb)\n")
        self.assertEqual(findings, [])

    def test_multiline_receiver_call_and_guard(self):
        findings = self.signals("func f():\n\tget_tree().process_frame.connect(\n\t\tcb.bind(1)\n\t)\n"
                                "\tif (not get_tree().process_frame.is_connected(\n\t\tcb.bind(1)\n\t)):\n"
                                "\t\tget_tree().process_frame.connect(cb.bind(1))\n")
        self.assertEqual(findings, [])

    def test_object_and_signal_connect_are_normalized(self):
        findings = self.signals('func f():\n\ta.connect("pressed", cb)\n\ta.pressed.connect(cb)\n')
        self.assertEqual(len(findings), 1)

    def test_explicit_disconnect_clears_previous_connection(self):
        findings = self.signals("func f():\n\ta.pressed.connect(cb)\n"
                                "\ta.pressed.disconnect(cb)\n\ta.pressed.connect(cb)\n")
        self.assertEqual(findings, [])


if __name__ == "__main__":
    unittest.main()
