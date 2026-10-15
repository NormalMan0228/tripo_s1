"""Pure-Python integration checks using small Godot projects on disk."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import unittest


REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURES = Path(__file__).resolve().parent / "fixtures" / "predeploy"
sys.path.insert(0, str(REPO_ROOT))

from tools.predeploy.check_client import check_project  # noqa: E402


class PredeployFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.results = {
            project.name: check_project(project)
            for project in FIXTURES.iterdir()
            if project.is_dir()
        }

    def findings(self, fixture: str, code: str | None = None):
        findings = self.results[fixture]
        if code is not None:
            findings = [finding for finding in findings if finding.code == code]
        return findings

    def test_clean_project_has_no_findings(self) -> None:
        self.assertEqual(self.findings("clean"), [])

    def test_missing_resources_cover_every_scanned_extension(self) -> None:
        findings = self.findings("resources", "missing-resource")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {
                ("main.gd", 3),
                ("main.tscn", 4),
                ("main.tres", 4),
                ("main.gdshader", 4),
                ("main.json", 1),
            },
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_resource_comments_and_existing_paths_are_ignored(self) -> None:
        findings = self.findings("resources")
        self.assertEqual(len(findings), 5)
        self.assertFalse(any("comment-only" in item.message for item in findings))
        self.assertFalse(any("hash#asset" in item.message for item in findings))

    def test_uids_resolve_via_sidecar_or_valid_external_resource_path(self) -> None:
        findings = self.findings("uids", "unresolved-uid")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("missing.tscn", 3), ("missing.tres", 3)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))
        self.assertEqual(len(self.findings("uids")), 2)

    def test_dynamic_paths_remain_warnings_even_when_folder_is_missing(self) -> None:
        findings = self.findings("dynamic_resources")
        self.assertTrue(findings)
        self.assertTrue(all(item.severity == "warning" for item in findings))
        dynamic = self.findings("dynamic_resources", "dynamic-resource")
        self.assertEqual({item.line for item in dynamic}, {5, 6, 7, 8, 9})

    def test_dynamic_common_folder_pattern_reports_matching_files(self) -> None:
        dynamic = self.findings("dynamic_resources", "dynamic-resource")
        matched = [item for item in dynamic if item.line in {5, 6, 7}]
        self.assertEqual(len(matched), 3)
        self.assertTrue(all(".glb" in item.message for item in matched))
        self.assertTrue(
            all(any(token in item.message.lower() for token in ("match", "candidate", "일치", "후보")) for item in matched)
        )

    def test_format_placeholders_stored_in_constants_are_dynamic(self) -> None:
        findings = [
            item for item in self.findings("resource_regressions", "dynamic-resource")
            if item.line in {2, 5}
        ]
        self.assertEqual({item.line for item in findings}, {2, 5})
        self.assertTrue(all(item.severity == "warning" for item in findings))
        self.assertTrue(all("sample.glb" in item.message for item in findings))

    def test_addition_outside_nested_calls_does_not_hide_static_missing_paths(self) -> None:
        findings = [
            item for item in self.findings("resource_regressions", "missing-resource")
            if item.file == "main.gd" and item.line == 6
        ]
        self.assertEqual(len(findings), 2)
        self.assertTrue(any("missing_nested_a.txt" in item.message for item in findings))
        self.assertTrue(any("missing_nested_b.txt" in item.message for item in findings))

    def test_resource_path_case_must_match_on_every_operating_system(self) -> None:
        findings = [
            item for item in self.findings("resource_regressions", "missing-resource")
            if item.file == "main.gd" and item.line == 7
        ]
        self.assertEqual(len(findings), 1)
        self.assertIn("res://case.txt", findings[0].message)

    def test_dynamic_operand_does_not_hide_its_nested_resource_literal(self) -> None:
        findings = [item for item in self.findings("resource_regressions") if item.line == 14]
        self.assertEqual({(item.code, item.severity) for item in findings}, {
            ("dynamic-resource", "warning"), ("missing-resource", "blocker")
        })
        self.assertTrue(any("absent-nested.txt" in item.message for item in findings))

    def test_uid_self_declarations_are_not_refs_but_orphan_sidecars_are_invalid(self) -> None:
        findings = self.findings("resource_regressions", "unresolved-uid")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("references.tscn", 3), ("references.tscn", 4)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_duplicate_top_level_declarations_include_all_four_kinds(self) -> None:
        findings = self.findings("structure", "duplicate-declaration")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("duplicates.gd", line) for line in (3, 5, 7, 12)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_missing_preload_is_a_blocker(self) -> None:
        findings = self.findings("structure", "missing-preload")
        self.assertEqual([(item.file, item.line) for item in findings], [("preloads.gd", 2)])
        self.assertEqual(findings[0].severity, "blocker")

    def test_missing_script_and_class_parents_are_blockers(self) -> None:
        findings = self.findings("structure", "missing-extends")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("missing_path_parent.gd", 1), ("missing_class_parent.gd", 1)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_sibling_script_paths_are_checked_and_existing_targets_are_accepted(self) -> None:
        findings = self.findings("parent_paths")
        self.assertEqual(
            {(item.code, item.file, item.line) for item in findings},
            {("missing-preload", "main.gd", 3), ("missing-extends", "missing_parent.gd", 1)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_method_resolution_handles_class_names_preloads_and_parents(self) -> None:
        findings = self.findings("inheritance", "missing-method")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("calls.gd", 16), ("calls.gd", 17)},
        )
        self.assertTrue(all(item.severity == "blocker" for item in findings))
        self.assertEqual(len(self.findings("inheritance")), 2)

    def test_repeated_connections_only_warn_for_same_function_and_pair(self) -> None:
        findings = self.findings("signals", "duplicate-signal-connect")
        self.assertEqual(
            {(item.file, item.line) for item in findings},
            {("main.gd", 7), ("main.gd", 27), ("self_connection.gd", 6)},
        )
        self.assertTrue(all(item.severity == "warning" for item in findings))
        self.assertEqual(len(self.findings("signals")), 3)

    def test_autoload_paths_are_checked_in_project_configuration(self) -> None:
        findings = self.findings("project_config", "missing-autoload")
        self.assertEqual([(item.file, item.line) for item in findings], [("project.godot", 5)])
        self.assertEqual(findings[0].severity, "blocker")

    def test_input_and_input_map_actions_must_be_configured(self) -> None:
        findings = self.findings("project_config", "undefined-input-action")
        self.assertEqual({item.line for item in findings}, {7, 8, 9, 10, 11, 12})
        self.assertTrue(all(item.file == "main.gd" for item in findings))
        self.assertTrue(all(item.severity == "blocker" for item in findings))

    def test_output_has_relative_paths_positive_lines_and_stable_order(self) -> None:
        for fixture, findings in self.results.items():
            with self.subTest(fixture=fixture):
                self.assertEqual(findings, check_project(FIXTURES / fixture))
                for finding in findings:
                    self.assertFalse(Path(finding.file).is_absolute())
                    self.assertNotIn("\\", finding.file)
                    self.assertGreater(finding.line, 0)
                    self.assertTrue(finding.message)

    def test_cli_json_and_exit_code_for_blockers_warnings_and_clean_project(self) -> None:
        for fixture, expected_code in (("resources", 1), ("signals", 0), ("clean", 0)):
            with self.subTest(fixture=fixture):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(REPO_ROOT / "tools" / "predeploy" / "check_client.py"),
                        "--project-root",
                        str(FIXTURES / fixture),
                        "--json",
                    ],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, expected_code, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(Path(payload["project_root"]), (FIXTURES / fixture).resolve())
                self.assertEqual(payload["blockers"], sum(item.severity == "blocker" for item in self.results[fixture]))
                self.assertEqual(payload["warnings"], sum(item.severity == "warning" for item in self.results[fixture]))
                self.assertEqual(len(payload["findings"]), len(self.results[fixture]))
                for finding in payload["findings"]:
                    self.assertTrue({"severity", "code", "file", "line", "message"} <= finding.keys())


if __name__ == "__main__":
    unittest.main()
