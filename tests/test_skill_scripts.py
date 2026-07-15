import json
import os
import plistlib
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = ROOT_DIR / "scripts"
SRC_DIR = ROOT_DIR / "src"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"
MINIMUM_NODE24_ACTION_MAJORS = {
    "actions/checkout": 5,
    "actions/setup-python": 6,
    "actions/upload-artifact": 6,
    "actions/download-artifact": 7,
}
ACTION_REFERENCE = re.compile(
    r"^[ \t]*(?:-[ \t]*)?(?:uses|['\"]uses['\"]):[ \t]*['\"]?"
    r"(?P<action>actions/[a-z0-9_-]+)@(?P<ref>[^'\"\s#]+)",
    re.IGNORECASE | re.MULTILINE,
)
ACTION_MAJOR_REF = re.compile(r"v(?P<major>\d+)(?:\.\d+){0,2}\Z", re.IGNORECASE)
BLOCK_SCALAR_START = re.compile(
    r"^[ ]*(?:-[ ]*)?(?:[A-Za-z0-9_-]+|['\"][^'\"]+['\"]):"
    r"[ ]*[|>][0-9+-]*[ ]*(?:#.*)?$"
)
sys.path.insert(0, str(SCRIPTS_DIR))

import draft_planner_context  # noqa: E402
import inventory_accessibility_ids  # noqa: E402
import inventory_launch_contract  # noqa: E402
import triage_ui_contract_failure  # noqa: E402
from ios_ui_testability_contract import __version__  # noqa: E402


def action_references(text: str):
    block_parent_indent: int | None = None
    for line in text.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip(" "))

        if block_parent_indent is not None:
            if not stripped or indent > block_parent_indent:
                continue
            block_parent_indent = None

        if BLOCK_SCALAR_START.match(line):
            block_parent_indent = indent
            continue

        match = ACTION_REFERENCE.match(line)
        if match:
            yield match


def reviewed_node24_major(action: str, ref: str) -> int:
    minimum = MINIMUM_NODE24_ACTION_MAJORS.get(action)
    if minimum is None:
        raise ValueError(f"{action} has no reviewed Node 24 minimum")
    version = ACTION_MAJOR_REF.fullmatch(ref)
    if version is None:
        raise ValueError(f"{action}@{ref} requires explicit Node 24 review")
    major = int(version.group("major"))
    if major < minimum:
        raise ValueError(
            f"{action}@{ref} requires at least v{minimum} for Node 24"
        )
    return major


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

    def test_package_and_runtime_versions_match(self) -> None:
        pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")
        match = re.search(r'^version\s*=\s*"([^"]+)"', pyproject, re.MULTILINE)

        self.assertIsNotNone(match)
        self.assertEqual(match.group(1), __version__)

        citation = (ROOT_DIR / "CITATION.cff").read_text(encoding="utf-8")
        citation_match = re.search(
            r'^version:\s*["\']?([^"\'\s]+)["\']?\s*$',
            citation,
            re.MULTILINE,
        )
        self.assertIsNotNone(citation_match)
        self.assertEqual(citation_match.group(1), __version__)

        citation_reader = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "read-citation-version.py")],
            cwd=ROOT_DIR,
            check=True,
            capture_output=True,
            text=True,
        )
        self.assertEqual(citation_reader.stdout.strip(), __version__)

    def test_pep_639_metadata_requires_a_compatible_setuptools(self) -> None:
        pyproject = (ROOT_DIR / "pyproject.toml").read_text(encoding="utf-8")

        self.assertIn('requires = ["setuptools>=77.0.3"]', pyproject)
        self.assertIn('license = "MIT"', pyproject)
        self.assertIn('license-files = ["LICENSE"]', pyproject)

    def test_published_skill_uses_release_pinned_ephemeral_cli(self) -> None:
        skill = (
            ROOT_DIR / "skills" / "ios-ui-testability-contract" / "SKILL.md"
        ).read_text(encoding="utf-8")

        self.assertIn(
            "uvx --from ios-ui-testability-contract==0.4.1 ios-ui-testability",
            skill,
        )

    def test_release_flow_dispatches_sha_pinned_oidc_publish_workflow(self) -> None:
        publish_workflow = (
            ROOT_DIR / ".github" / "workflows" / "publish-pypi.yml"
        ).read_text(encoding="utf-8")
        release_workflow = (
            ROOT_DIR / ".github" / "workflows" / "release.yml"
        ).read_text(encoding="utf-8")

        self.assertIn("workflow_dispatch:", publish_workflow)
        self.assertNotIn("workflow_call:", publish_workflow)
        self.assertIn("id-token: write", publish_workflow)
        self.assertIn(
            "ref: ${{ inputs.release_tag || github.event.release.tag_name }}",
            publish_workflow,
        )
        self.assertRegex(
            publish_workflow,
            r"pypa/gh-action-pypi-publish@[0-9a-f]{40} # release/v1",
        )
        self.assertIn("skip-existing: true", publish_workflow)
        self.assertIn("attestations: true", publish_workflow)
        self.assertIn(
            "python scripts/read-citation-version.py",
            publish_workflow,
        )
        self.assertIn(
            "python scripts/read-citation-version.py",
            release_workflow,
        )
        self.assertIn("actions: write", release_workflow)
        self.assertIn("gh workflow run publish-pypi.yml", release_workflow)
        self.assertIn(
            "PUBLISH_WORKFLOW_REF: ${{ github.event.repository.default_branch }}",
            release_workflow,
        )
        self.assertIn('--ref "${PUBLISH_WORKFLOW_REF}"', release_workflow)
        self.assertIn('--field release_tag="${VERSION_TAG}"', release_workflow)

    def test_tag_push_can_create_a_release_without_personal_auth(self) -> None:
        workflow = (
            ROOT_DIR / ".github" / "workflows" / "release-tag.yml"
        ).read_text(encoding="utf-8")

        self.assertIn('tags:\n      - "v*.*.*"', workflow)
        self.assertIn("actions: write", workflow)
        self.assertIn("contents: write", workflow)
        self.assertIn("GH_TOKEN: ${{ github.token }}", workflow)
        self.assertIn('gh release create "${RELEASE_TAG}"', workflow)
        self.assertIn("gh workflow run publish-pypi.yml", workflow)
        self.assertIn('--field release_tag="${RELEASE_TAG}"', workflow)
        self.assertNotIn("secrets.", workflow)

    def test_workflows_use_node24_action_generations(self) -> None:
        workflows_dir = ROOT_DIR / ".github" / "workflows"
        workflows = "\n".join(
            workflow.read_text(encoding="utf-8")
            for workflow in sorted(workflows_dir.glob("*.y*ml"))
        )

        checked_references = 0
        for match in action_references(workflows):
            action = match.group("action").lower()
            checked_references += 1
            reviewed_node24_major(action, match.group("ref"))

        self.assertGreater(checked_references, 0)
        self.assertIsNone(
            ACTION_REFERENCE.search("# migrated from uses: actions/setup-python@v5")
        )
        self.assertEqual(
            [
                match.group("ref")
                for match in action_references(
                    "run: |\n  uses: actions/setup-python@v5\n"
                    "- uses: actions/setup-python@v6\n"
                )
            ],
            ["v6"],
        )
        self.assertEqual(
            [
                match.group("ref")
                for match in action_references(
                    '- "uses": actions/setup-python@v5\n'
                )
            ],
            ["v5"],
        )
        with self.assertRaisesRegex(ValueError, "requires explicit Node 24 review"):
            reviewed_node24_major("actions/setup-python", "a" * 40)
        self.assertIn("actions/setup-python@v6", workflows)
        self.assertIn("actions/upload-artifact@v6", workflows)
        self.assertIn("actions/download-artifact@v7", workflows)

    def test_canonical_agent_skill_uses_portable_frontmatter(self) -> None:
        skill_dir = ROOT_DIR / "skills" / "ios-ui-testability-contract"
        skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
        frontmatter_match = re.match(r"\A---\n(.*?)\n---\n", skill_text, re.DOTALL)

        self.assertIsNotNone(frontmatter_match)
        frontmatter_keys = {
            line.split(":", 1)[0].strip()
            for line in frontmatter_match.group(1).splitlines()
            if line.strip()
        }
        self.assertEqual(frontmatter_keys, {"name", "description"})
        self.assertIn("name: ios-ui-testability-contract", skill_text)
        self.assertTrue((skill_dir / "agents" / "openai.yaml").is_file())
        self.assertTrue((skill_dir / "references" / "failure-patterns.md").is_file())

    def test_root_skill_preserves_legacy_direct_clone_installations(self) -> None:
        root_skill = (ROOT_DIR / "SKILL.md").read_text(encoding="utf-8")

        self.assertIn("name: ios-ui-testability-contract", root_skill)
        self.assertIn(
            "skills/ios-ui-testability-contract/SKILL.md",
            root_skill,
        )
        self.assertTrue((ROOT_DIR / "agents" / "openai.yaml").is_file())

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
                            Text("Unstable name")
                                .accessibilityIdentifier("sample.recipes.row.\\(recipe.name)")
                            Text("Unstable index")
                                .accessibilityIdentifier("sample.recipes.row.\\(index)")
                            ForEach(ingredients) { ingredient in
                                Text(ingredient.name)
                                    .accessibilityIdentifier("sample.recognized.\\(ingredient.id)")
                            }
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
            self.assertEqual(len(acceptable_dynamic), 2)
            self.assertEqual(len(review_needed_dynamic), 3)
            self.assertEqual(len(report["likely_parent_container_collisions"]), 0)

    def test_dynamic_identifier_requires_a_stable_model_member(self) -> None:
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier=None,
                source=".accessibilityIdentifier(identifier)",
                repeated_context=True,
            ),
            "review_needed",
        )
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier=None,
                source=".accessibilityIdentifier(item.id)",
                repeated_context=True,
            ),
            "acceptable",
        )

    def test_dynamic_identifier_distinguishes_delimiters_and_unstable_hashes(self) -> None:
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier="sample.row:\\(item.id)",
                source='.accessibilityIdentifier("sample.row:\\(item.id)")',
                repeated_context=True,
            ),
            "acceptable",
        )
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier="sample.row.\\(item.id.hashValue)",
                source='.accessibilityIdentifier("sample.row.\\(item.id.hashValue)")',
                repeated_context=True,
            ),
            "review_needed",
        )

    def test_dynamic_identifier_requires_every_interpolation_to_be_stable(self) -> None:
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier="sample.row.\\(section.id)-\\(item.id)",
                source=(
                    '.accessibilityIdentifier('
                    '"sample.row.\\(section.id)-\\(item.id)"'
                    ')'
                ),
                repeated_context=True,
            ),
            "acceptable",
        )
        for identifier in (
            "sample.row.\\(item.id)-\\(UUID())",
            "sample.row.\\(item.id)-\\(Int.random(in: 1...9))",
            "sample.row.\\(item.id)-\\(Date().timeIntervalSince1970)",
        ):
            with self.subTest(identifier=identifier):
                self.assertEqual(
                    inventory_accessibility_ids.classify_dynamic_entry(
                        identifier=identifier,
                        source=f'.accessibilityIdentifier("{identifier}")',
                        repeated_context=True,
                    ),
                    "review_needed",
                )

    def test_inventory_respects_each_string_interpolation_delimiter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "RawIdentifiers.swift"
            source_path.write_text(
                '''
                ForEach(items) { item in
                    Text("escaped")
                        .accessibilityIdentifier("sample.escaped.\\\\(item.id)")
                    Text("raw literal")
                        .accessibilityIdentifier(#"sample.raw.\\(item.id)"#)
                    Text("wrong hash")
                        .accessibilityIdentifier(##"sample.raw2.\\#(item.id)"##)
                    Text("raw interpolation")
                        .accessibilityIdentifier(#"sample.correct.\\#(item.id)"#)
                }
                ''',
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(len(report["identifiers"]), 3)
            self.assertEqual(len(report["interpolated"]), 1)
            self.assertEqual(len(report["acceptable_dynamic"]), 1)
            self.assertEqual(
                report["acceptable_dynamic"][0]["identifier"],
                "sample.correct.\\#(item.id)",
            )
        self.assertEqual(
            inventory_accessibility_ids.classify_dynamic_entry(
                identifier="sample.row.\\(enabled ? item.id : fallback.id)",
                source=(
                    '.accessibilityIdentifier('
                    '"sample.row.\\(enabled ? item.id : fallback.id)"'
                    ')'
                ),
                repeated_context=True,
            ),
            "review_needed",
        )

    def test_inventory_ignores_comments_and_recognizes_multiline_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "CommentedView.swift"
            source_path.write_text(
                """
                // .accessibilityIdentifier("sample.dead.line")
                /*
                 .accessibilityIdentifier("sample.dead.block")
                 accessibilityIdentifier = "sample.dead.assignment"
                */
                Button("Save") {}
                    .accessibilityIdentifier(
                        "sample.save"
                    )
                """,
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(set(report["identifiers"]), {"sample.save"})
            self.assertEqual(report["likely_dynamic"], [])

    def test_inventory_ignores_code_examples_inside_multiline_and_raw_strings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "DocumentedView.swift"
            source_path.write_text(
                '''
                let documentation = """
                .accessibilityIdentifier("sample.fake.multiline")
                """
                let rawPattern = #"prefix " /* raw-string content"#
                Button("Save") {}
                    .accessibilityIdentifier(#"sample.save"#)
                ''',
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(set(report["identifiers"]), {"sample.save"})
            self.assertEqual(report["likely_dynamic"], [])

    def test_inventory_honors_escaped_multiline_and_raw_string_delimiters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "EscapedStrings.swift"
            source_path.write_text(
                'let multiline = """\n'
                'prefix \\""" /* .accessibilityIdentifier("sample.fake.multiline")\n'
                '"""\n'
                'let raw = #"prefix \\#"# /* .accessibilityIdentifier("sample.fake.raw")"#\n'
                'Button("Save") {}\n'
                '    .accessibilityIdentifier("sample.save")\n',
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(set(report["identifiers"]), {"sample.save"})

    def test_inventory_ignores_comment_tokens_inside_extended_regex_literals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "RegexView.swift"
            source_path.write_text(
                'let one = #/foo/*bar/#\n'
                'let two = ##/baz/*qux/##\n'
                'Button("Save") {}\n'
                '    .accessibilityIdentifier("sample.save")\n',
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(set(report["identifiers"]), {"sample.save"})

    def test_inventory_recognizes_objective_c_setter_messages(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "Button.m"
            source_path.write_text(
                '- (void)setAccessibilityIdentifier:(NSString *)identifier;\n'
                '- (void)setAccessibilityIdentifier:(NSString *)identifier {\n'
                '    _identifier = identifier;\n'
                '}\n'
                '[button setAccessibilityIdentifier:@"sample.button"];\n'
                '[row setAccessibilityIdentifier:dynamicIdentifier];\n',
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertIn("sample.button", report["identifiers"])
            self.assertEqual(len(report["likely_dynamic"]), 1)
            self.assertIn("dynamicIdentifier", report["likely_dynamic"][0]["source"])

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

    def test_inventory_does_not_treat_leaf_identifier_text_as_a_container(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "Sources" / "PantryFormView.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                """
                struct PantryFormView: View {
                    var body: some View {
                        TextField("Name", text: .constant(""))
                            .textContentType(.name)
                            .textInputAutocapitalization(.words)
                            .accessibilityIdentifier("sample.pantryForm.name")
                    }
                }
                """,
                encoding="utf-8",
            )

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertEqual(report["likely_parent_container_assignments"], [])

    def test_draft_planner_context_includes_launch_and_identifier_guidance(self) -> None:
        launch_report = {
            "environment_keys": ["SAMPLE_AUTOMATION_ROUTE"],
            "launch_arguments": ["-automation-add-recipe"],
            "url_schemes": [{"scheme": "sample", "file": "/tmp/Info.plist"}],
            "route_hints": [{"file": "AppRouting.swift", "line": 12, "source": "route"}],
            "automation_hints": [],
            "skipped_plists": [
                {"file": "Config/Broken.plist", "reason": "malformed plist"}
            ],
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
        self.assertIn("Config/Broken.plist", markdown)

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

    def test_triage_preserves_explicit_assertion_accessibility_selector(self) -> None:
        identifiers: list[str] = []

        triage_ui_contract_failure.collect_scenario_identifiers(
            {
                "action": "assert",
                "by": "accessibilityId",
                "value": "sample.login.submit",
                "expected": "visible",
            },
            identifiers,
            top_level=True,
        )

        self.assertEqual(identifiers, ["sample.login.submit"])

    def test_triage_uses_label_based_scenario_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            scenario = root / "scenario.json"
            ui_tree = root / "ui-tree.json"
            scenario.write_text(
                '{"steps":[{"action":"tap","label":"Save"}]}',
                encoding="utf-8",
            )
            ui_tree.write_text(
                '{"tree":{"label":"Cancel","children":[]}}',
                encoding="utf-8",
            )

            scenario_labels = triage_ui_contract_failure.collect_scenario_labels(scenario)
            ui_tree_labels = triage_ui_contract_failure.collect_ui_tree_labels(ui_tree)
            report = triage_ui_contract_failure.classify(
                "The intended screen is visible.",
                [],
                set(),
                scenario_labels=scenario_labels,
                ui_tree_labels=ui_tree_labels,
            )

            self.assertEqual(scenario_labels, ["Save"])
            self.assertEqual(report["missing_scenario_labels"], ["Save"])
            self.assertEqual(report["bucket"], "launch determinism")

    def test_triage_gives_identifier_precedence_over_fallback_label(self) -> None:
        labels: list[str] = []

        triage_ui_contract_failure.collect_scenario_label_values(
            {
                "action": "tap",
                "id": "sample.save",
                "label": "Save",
            },
            labels,
            top_level=True,
        )
        report = triage_ui_contract_failure.classify(
            "The save control is visible.",
            ["sample.save"],
            {"sample.save"},
            scenario_labels=labels,
            ui_tree_labels={"Guardar"},
        )

        self.assertEqual(labels, [])
        self.assertEqual(report["missing_scenario_labels"], [])

    def test_triage_label_strategy_does_not_treat_typed_value_as_locator(self) -> None:
        labels: list[str] = []

        triage_ui_contract_failure.collect_scenario_label_values(
            {
                "action": "type",
                "by": "label",
                "name": "Email",
                "value": "person@example.com",
            },
            labels,
            top_level=True,
        )

        self.assertEqual(labels, ["Email"])

    def test_triage_prioritizes_decisive_failure_phrases(self) -> None:
        report = triage_ui_contract_failure.classify(
            "App launch succeeded, but the submit Button is not hittable.",
            ["sample.submit"],
            {"sample.submit"},
        )
        tapping_report = triage_ui_contract_failure.classify(
            "Tapping rapidly did not reproduce the reported issue.",
            [],
            set(),
        )
        unrelated_failure = triage_ui_contract_failure.classify(
            "App launch succeeded, but the network request failed.",
            [],
            set(),
        )

        self.assertEqual(report["bucket"], "app contract")
        self.assertNotIn(
            "summary points at a startup, inspect, simulator, or route failure",
            report["evidence"],
        )
        self.assertNotIn(
            "summary mentions a backend, network, OCR, or AI dependency",
            tapping_report["evidence"],
        )
        self.assertEqual(unrelated_failure["bucket"], "backend or network dependency")
        self.assertNotIn(
            "summary points at a startup, inspect, simulator, or route failure",
            unrelated_failure["evidence"],
        )

    def test_triage_associates_failures_with_their_clause_subject(self) -> None:
        backend_failure = triage_ui_contract_failure.classify(
            "After launch, the network request failed.",
            [],
            set(),
        )
        launch_failure = triage_ui_contract_failure.classify(
            "Network succeeded, but app launch failed.",
            [],
            set(),
        )

        self.assertEqual(backend_failure["bucket"], "backend or network dependency")
        self.assertNotIn(
            "summary points at a startup, inspect, simulator, or route failure",
            backend_failure["evidence"],
        )
        self.assertEqual(launch_failure["bucket"], "launch determinism")
        self.assertNotIn(
            "summary mentions a backend, network, OCR, or AI dependency",
            launch_failure["evidence"],
        )

    def test_triage_keeps_negated_launch_success_as_failure_evidence(self) -> None:
        for summary in (
            "Launch did not succeed.",
            "The simulator failed to become ready.",
            "Startup did not complete successfully.",
        ):
            with self.subTest(summary=summary):
                self.assertTrue(
                    triage_ui_contract_failure.summary_points_at_launch_failure(summary.lower())
                )

    def test_triage_handles_failure_polarity_ordering_and_routes(self) -> None:
        for summary in (
            "Launch never succeeded.",
            "Startup was not successful.",
            "Launch didn't succeed.",
            "App won't launch.",
            "App didn't launch.",
            "App does not launch.",
            "The simulator couldn't boot.",
            "Launch couldn't complete.",
            "Never succeeded during launch.",
            "Never succeeded during launch before the network request.",
            "Unable to complete launch.",
            "Could not complete startup.",
            "On launch\nNever succeeded.",
            "Launch succeeded initially then failed.",
            "App launch is failing.",
            "The automation route failed to open the screen.",
            "Routing failed before the scenario began.",
            "The app crashed during launch.",
            "Launch, unexpectedly, failed.",
            "Launch, after backend initialization, failed.",
            "The app, during launch, crashed.",
            "The app, when launched, crashed.",
            "The app, because launch failed, never reached the home screen.",
        ):
            with self.subTest(summary=summary):
                self.assertTrue(
                    triage_ui_contract_failure.summary_points_at_launch_failure(summary.lower())
                )

        for summary in (
            "Launch did not fail.",
            "No launch failure occurred.",
            "No launch attempt failed.",
            "No failure to launch.",
            "Never failed to launch.",
            "The run completed without failure to launch.",
            "Without any launch failure, the app remained responsive.",
            "The app, despite no launch failure, remained blank.",
            "The button assertion failed after launch.",
            "UI test failed after launch.",
            "Launch completed without error.",
            "Launch had no failure.",
            "The backend failed to launch the processing job.",
            "Network request routing failed.",
            "On launch; no failure occurred.",
            "During startup\nCompleted without error.",
            "Upon app launch; no crash occurred.",
            "The app, after launch succeeded, failed later.",
            "The app, although launch completed successfully, crashed during checkout.",
            "Never succeeded on the network request after launch.",
            "Unable to complete the network request after launch.",
            "The backend, on launch, failed.",
            "The button, upon launch, failed.",
        ):
            with self.subTest(summary=summary):
                self.assertFalse(
                    triage_ui_contract_failure.summary_points_at_launch_failure(summary.lower())
                )

        self.assertTrue(
            triage_ui_contract_failure.summary_points_at_backend_failure(
                "Network request succeeded initially then failed.".lower()
            )
        )
        self.assertTrue(
            triage_ui_contract_failure.summary_points_at_backend_failure(
                "Network never succeeded.".lower()
            )
        )
        self.assertTrue(
            triage_ui_contract_failure.summary_points_at_backend_failure(
                "Never succeeded on the network request.".lower()
            )
        )
        self.assertFalse(
            triage_ui_contract_failure.summary_points_at_backend_failure(
                "Network did not fail.".lower()
            )
        )
        for summary in (
            "HTTP 500 from the API.",
            "The network request, after retrying, failed.",
            "The backend failed to launch the processing job.",
            "Network request routing failed.",
            "The backend, after launch, failed.",
            "Network did not recover and failed.",
            "Network connected without retries and failed later.",
            "Network request is failing.",
            "Never succeeded on the network request after launch.",
            "Unable to complete the network request after launch.",
            "The app, because the network request failed, remained blank.",
            "The app, although the API returned HTTP 500, stayed responsive.",
            "The backend, on launch, failed.",
        ):
            with self.subTest(summary=summary):
                self.assertTrue(
                    triage_ui_contract_failure.summary_points_at_backend_failure(
                        summary.lower()
                    )
                )
        for summary in (
            "Network request completed without error.",
            "The API returned successfully without failure.",
            "There was no backend failure.",
            "No network request failed.",
            "No failure to reach backend.",
            "Without failure to reach server.",
            "Without any network request failure, the app remained responsive.",
            "Never succeeded during launch before the network request.",
        ):
            with self.subTest(summary=summary):
                self.assertFalse(
                    triage_ui_contract_failure.summary_points_at_backend_failure(
                        summary.lower()
                    )
                )

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

    def test_scan_commands_reject_missing_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            missing = Path(tmp) / "missing"
            for command in ("ids", "launch", "draft-context"):
                with self.subTest(command=command):
                    completed = subprocess.run(
                        [
                            sys.executable,
                            "-m",
                            "ios_ui_testability_contract",
                            command,
                            str(missing),
                        ],
                        capture_output=True,
                        env=self.package_env(),
                        text=True,
                    )

                    self.assertEqual(completed.returncode, 2)
                    self.assertIn("scan path does not exist", completed.stderr)

    def test_triage_rejects_missing_and_malformed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary = root / "summary.md"
            malformed_scenario = root / "scenario.json"
            summary.write_text("The runner failed.", encoding="utf-8")
            malformed_scenario.write_text("not JSON", encoding="utf-8")

            malformed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ios_ui_testability_contract",
                    "triage",
                    "--summary",
                    str(summary),
                    "--scenario",
                    str(malformed_scenario),
                ],
                capture_output=True,
                env=self.package_env(),
                text=True,
            )
            missing = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ios_ui_testability_contract",
                    "triage",
                    "--summary",
                    str(root / "missing-summary.md"),
                ],
                capture_output=True,
                env=self.package_env(),
                text=True,
            )

            self.assertEqual(malformed.returncode, 2)
            self.assertIn("scenario is not valid JSON", malformed.stderr)
            self.assertEqual(missing.returncode, 2)
            self.assertIn("summary does not exist", missing.stderr)

    def test_inventory_paths_are_relative_and_external_symlinks_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            repo_root = temp_root / "Repo"
            source_path = repo_root / "Sources" / "RecipeView.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                'TextField("Name", text: .constant(""))\n'
                '    .accessibilityIdentifier("sample.recipe.name")\n',
                encoding="utf-8",
            )
            outside = temp_root / "Outside.swift"
            outside.write_text(
                'Text("Secret").accessibilityIdentifier("outside.secret")\n',
                encoding="utf-8",
            )
            link = repo_root / "Sources" / "External.swift"
            try:
                link.symlink_to(outside)
            except OSError as error:
                self.skipTest(f"Symlinks unavailable: {error}")

            report = inventory_accessibility_ids.collect(repo_root)

            self.assertIn("sample.recipe.name", report["identifiers"])
            self.assertNotIn("outside.secret", report["identifiers"])
            self.assertEqual(
                report["identifiers"]["sample.recipe.name"][0]["file"],
                "Sources/RecipeView.swift",
            )
            self.assertEqual(report["skipped_symlinks"], ["Sources/External.swift"])

    def test_inventory_rejects_symlink_scan_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            external_directory = temp_root / "ExternalRepo"
            external_directory.mkdir()
            external_file = external_directory / "View.swift"
            external_file.write_text(
                'Text("Outside").accessibilityIdentifier("outside.root")\n',
                encoding="utf-8",
            )
            directory_link = temp_root / "RepoLink"
            file_link = temp_root / "ViewLink.swift"
            try:
                directory_link.symlink_to(external_directory, target_is_directory=True)
                file_link.symlink_to(external_file)
            except OSError as error:
                self.skipTest(f"Symlinks unavailable: {error}")

            for link in (directory_link, file_link):
                with self.subTest(link=link), self.assertRaisesRegex(
                    ValueError,
                    "scan path must not be a symbolic link",
                ):
                    inventory_accessibility_ids.collect(link)

    def test_draft_context_uses_relative_route_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "Repo"
            source_path = repo_root / "Sources" / "AppRouting.swift"
            source_path.parent.mkdir(parents=True)
            source_path.write_text(
                'let route = environment["SAMPLE_AUTOMATION_ROUTE"]\n',
                encoding="utf-8",
            )

            launch_report = inventory_launch_contract.collect(repo_root)
            accessibility_report = inventory_accessibility_ids.collect(repo_root)
            markdown = draft_planner_context.build_markdown(
                launch_report=launch_report,
                accessibility_report=accessibility_report,
                max_identifiers=8,
            )

            self.assertIn("Sources/AppRouting.swift", markdown)
            self.assertNotIn(str(repo_root), markdown)

    def test_launch_inventory_ignores_non_dictionary_plists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "Values.plist").write_bytes(plistlib.dumps(["one", "two"]))

            report = inventory_launch_contract.collect(repo_root)

            self.assertEqual(report["url_schemes"], [])

    def test_launch_inventory_ignores_non_array_url_schemes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "Info.plist").write_bytes(
                plistlib.dumps(
                    {
                        "CFBundleURLTypes": [
                            {"CFBundleURLSchemes": "myapp"},
                            {"CFBundleURLSchemes": ["valid", 123]},
                        ]
                    }
                )
            )

            report = inventory_launch_contract.collect(repo_root)

            self.assertEqual(
                report["url_schemes"],
                [{"scheme": "valid", "file": "Info.plist"}],
            )

    def test_launch_inventory_reports_malformed_plists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            (repo_root / "Broken.plist").write_bytes(b"not a plist")

            report = inventory_launch_contract.collect(repo_root)

            self.assertEqual(report["url_schemes"], [])
            self.assertEqual(
                report["skipped_plists"],
                [{"file": "Broken.plist", "reason": "malformed plist"}],
            )

    def test_duplicates_only_json_excludes_nonduplicates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo_root = Path(tmp)
            source_path = repo_root / "Identifiers.swift"
            source_path.write_text(
                "\n".join(
                    [
                        'Text("A").accessibilityIdentifier("sample.duplicate")',
                        'Text("B").accessibilityIdentifier("sample.duplicate")',
                        'Text("C").accessibilityIdentifier("sample.unique")',
                    ]
                ),
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "ios_ui_testability_contract",
                    "ids",
                    str(repo_root),
                    "--duplicates-only",
                    "--json",
                ],
                check=True,
                capture_output=True,
                env=self.package_env(),
                text=True,
            )
            payload = json.loads(completed.stdout)

            self.assertEqual(set(payload), {"duplicates", "skipped_symlinks"})
            self.assertIn("sample.duplicate", payload["duplicates"])
            self.assertNotIn("sample.unique", payload["duplicates"])

    def test_draft_context_rejects_nonpositive_identifier_limit(self) -> None:
        completed = subprocess.run(
            [
                sys.executable,
                "-m",
                "ios_ui_testability_contract",
                "draft-context",
                str(ROOT_DIR),
                "--max-identifiers",
                "-1",
            ],
            capture_output=True,
            env=self.package_env(),
            text=True,
        )

        self.assertEqual(completed.returncode, 2)
        self.assertIn("must be a positive integer", completed.stderr)


if __name__ == "__main__":
    unittest.main()
