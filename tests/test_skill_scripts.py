import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
SRC_DIR = ROOT_DIR / "src"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
sys.path.insert(0, str(SCRIPTS_DIR))

import draft_planner_context  # noqa: E402
import inventory_accessibility_ids  # noqa: E402
import triage_ui_contract_failure  # noqa: E402


class SkillScriptTests(unittest.TestCase):
    def package_env(self) -> dict[str, str]:
        env = os.environ.copy()
        existing_pythonpath = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            f"{SRC_DIR}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(SRC_DIR)
        )
        return env

    def test_inventory_accessibility_ids_grades_dynamic_assignments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "Sources" / "RecipeView.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                """
                struct RecipeView: View {
                    var body: some View {
                        VStack {
                            TextField("URL", text: .constant(""))
                                .accessibilityIdentifier("sample.recipeForm.videoURL")
                            Text("Row")
                                .accessibilityIdentifier("sample.recipes.row.\\(recipe.id.uuidString)")
                            Button("Next") {}
                                .accessibilityIdentifier(step == .finish ? "sample.onboarding.finish" : "sample.onboarding.next")
                        }
                    }
                }
                """,
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)
            acceptable_dynamic = report["acceptable_dynamic"]
            review_needed_dynamic = report["review_needed_dynamic"]

            self.assertEqual(len(report["identifiers"]), 1)
            self.assertEqual(len(acceptable_dynamic), 1)
            self.assertEqual(len(review_needed_dynamic), 1)
            self.assertEqual(len(report["likely_parent_container_collisions"]), 0)

    def test_inventory_accessibility_ids_detects_parent_container_collisions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "Sources" / "RecipeFormView.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                """
                struct RecipeFormView: View {
                    var body: some View {
                        VStack {
                            TextField("URL", text: .constant(""))
                                .accessibilityIdentifier("sample.recipeForm.videoURL")
                        }
                        .accessibilityIdentifier("sample.recipeForm")
                    }
                }
                """,
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)
            collisions = report["likely_parent_container_collisions"]

            self.assertEqual(len(collisions), 1)
            self.assertEqual(collisions[0]["identifier"], "sample.recipeForm")
            self.assertIn("sample.recipeForm.videoURL", collisions[0]["child_identifiers"])

    def test_draft_planner_context_includes_launch_and_identifier_guidance(self) -> None:
        launch_report = {
            "environment_keys": ["SAMPLE_AUTOMATION_ROUTE"],
            "launch_arguments": ["-automation-add-recipe"],
            "url_schemes": [{"scheme": "sample", "file": "/tmp/Info.plist"}],
            "route_hints": [{"file": "AppRouting.swift", "line": 12, "source": "route"}],
            "automation_hints": [],
        }
        accessibility_report = {
            "identifiers": {
                "sample.recipeForm.videoURL": [],
                "sample.recipes.add": [],
            },
            "review_needed_dynamic": [
                {
                    "identifier": "sample.onboarding.finish",
                    "file": "Onboarding.swift",
                    "line": 10,
                    "source": "conditional id",
                }
            ],
        }

        markdown = draft_planner_context.build_markdown(
            launch_report=launch_report,
            accessibility_report=accessibility_report,
            max_identifiers=8,
        )

        self.assertIn("SAMPLE_AUTOMATION_ROUTE", markdown)
        self.assertIn("-automation-add-recipe", markdown)
        self.assertIn("sample.recipeForm.videoURL", markdown)
        self.assertIn("Review these dynamic identifiers", markdown)

    def test_triage_ui_contract_failure_classifies_scenario_contract(self) -> None:
        report = triage_ui_contract_failure.classify(
            summary_text=(
                "Planner generated a scenario that failed accessibility or conditional-state validation."
            ),
            scenario_ids=["sample.paywall.cta", "sample.recipeForm.videoURL"],
            ui_tree_ids={"sample.recipeForm.videoURL"},
            planner_validation_error_text="unknown identifier sample.paywall.cta",
        )

        self.assertEqual(report["bucket"], "scenario contract")
        self.assertIn("sample.paywall.cta", report["missing_scenario_ids"])
        self.assertTrue(report["planner_validation_error_present"])
        self.assertGreaterEqual(len(report["patch_plan"]), 2)

    def test_triage_extracts_structured_ui_tree_and_nested_scenario_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ui_tree = root / "ui-tree.json"
            scenario = root / "scenario.json"
            ui_tree.write_text(
                """
                {
                  "tree": {
                    "identifier": "sample.login",
                    "label": "Log In",
                    "children": [
                      {
                        "accessibilityIdentifier": "sample.login.email",
                        "label": "Email"
                      },
                      {
                        "identifier": "sample.login.submit",
                        "label": "Continue"
                      },
                      {
                        "identifier": "sample.login.forgotPassword",
                        "label": "Forgot Password"
                      },
                      {
                        "identifier": "sample.login.cancel",
                        "label": "Cancel"
                      }
                    ]
                  }
                }
                """,
                encoding="utf-8",
            )
            scenario.write_text(
                """
                {
                  "steps": [
                    {
                      "action": "type",
                      "target": {
                        "accessibilityIdentifier": "sample.login.email"
                      }
                    },
                    {
                      "action": "tap",
                      "selector": {
                        "identifier": "sample.login.submit"
                      }
                    },
                    {
                      "action": "tap",
                      "selector": {
                        "strategy": "accessibilityIdentifier",
                        "value": "sample.login.forgotPassword"
                      }
                    },
                    {
                      "action": "tap",
                      "by": "accessibilityId",
                      "value": "sample.login.cancel"
                    },
                    {
                      "action": "type",
                      "by": "accessibilityId",
                      "name": "sample.login.email",
                      "value": "person@example.com"
                    },
                    {
                      "action": "type",
                      "by": "accessibilityId",
                      "value": "sample.login.email",
                      "text": "person@example.com"
                    },
                    {
                      "action": "assert",
                      "target": {
                        "identifier": "sample.login.submit"
                      },
                      "assertion": "visible"
                    },
                    {
                      "action": "assert",
                      "assertion": {
                        "expected": {
                          "id": "order-123",
                          "text": "Done"
                        }
                      }
                    },
                    {
                      "action": "assert",
                      "assertion": {
                        "target": "Done"
                      }
                    },
                    {
                      "action": "type",
                      "payload": {
                        "selector": "person@example.com"
                      }
                    }
                  ]
                }
                """,
                encoding="utf-8",
            )

            self.assertEqual(
                triage_ui_contract_failure.collect_scenario_ids(scenario),
                [
                    "sample.login.email",
                    "sample.login.submit",
                    "sample.login.forgotPassword",
                    "sample.login.cancel",
                ],
            )
            self.assertNotIn("visible", triage_ui_contract_failure.collect_scenario_ids(scenario))
            self.assertNotIn("person@example.com", triage_ui_contract_failure.collect_scenario_ids(scenario))
            self.assertNotIn("order-123", triage_ui_contract_failure.collect_scenario_ids(scenario))
            self.assertNotIn("Done", triage_ui_contract_failure.collect_scenario_ids(scenario))
            self.assertEqual(
                triage_ui_contract_failure.collect_ui_tree_identifiers(ui_tree),
                {
                    "sample.login",
                    "sample.login.cancel",
                    "sample.login.email",
                    "sample.login.forgotPassword",
                    "sample.login.submit",
                },
            )
            self.assertIn("Email", triage_ui_contract_failure.collect_ui_tree_labels(ui_tree))

    def test_triage_patch_plan_mode_uses_fixture_bundle(self) -> None:
        fixture_root = FIXTURES_DIR / "sample_failure_bundle"

        completed = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS_DIR / "triage_ui_contract_failure.py"),
                "--summary",
                str(fixture_root / "summary.md"),
                "--ui-tree",
                str(fixture_root / "ui-tree.json"),
                "--scenario",
                str(fixture_root / "scenario.json"),
                "--planner-validation-error",
                str(fixture_root / "planner-validation-error.txt"),
                "--report-mode",
                "patch-plan",
            ],
            check=True,
            capture_output=True,
            text=True,
        )

        self.assertIn("Patch plan", completed.stdout)
        self.assertIn("planner-validation-error.txt", completed.stdout)
        self.assertIn("sample.recipeForm.submit", completed.stdout)

    def test_packaged_cli_triage_uses_fixture_bundle(self) -> None:
        fixture_root = FIXTURES_DIR / "sample_failure_bundle"

        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ios_ui_testability_contract",
                "triage",
                "--summary",
                str(fixture_root / "summary.md"),
                "--ui-tree",
                str(fixture_root / "ui-tree.json"),
                "--scenario",
                str(fixture_root / "scenario.json"),
                "--planner-validation-error",
                str(fixture_root / "planner-validation-error.txt"),
                "--report-mode",
                "patch-plan",
            ],
            check=True,
            capture_output=True,
            env=self.package_env(),
            text=True,
        )

        self.assertIn("Patch plan", completed.stdout)
        self.assertIn("sample.recipeForm.submit", completed.stdout)

    def test_draft_planner_context_can_write_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "Repo"
            output_path = Path(tmp) / "planner-context.md"
            source_path = repo_root / "Sources" / "RecipeView.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                """
                struct RecipeView: View {
                    var body: some View {
                        TextField("URL", text: .constant(""))
                            .accessibilityIdentifier("sample.recipeForm.videoURL")
                    }
                }
                """,
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS_DIR / "draft_planner_context.py"),
                    str(repo_root),
                    "--output",
                    str(output_path),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertTrue(output_path.exists())
            self.assertIn("sample.recipeForm.videoURL", output_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
