"""Focused regression tests for deterministic AI-native detection."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from typing import Optional
from unittest import mock

DETECT_PATH = Path(__file__).with_name("detect.py")
SPEC = importlib.util.spec_from_file_location("ai_native_detect", DETECT_PATH)
assert SPEC is not None and SPEC.loader is not None
detect = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = detect
SPEC.loader.exec_module(detect)


class DetectionRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.store_roots: list[Path] = []

    def tearDown(self) -> None:
        for store_root in self.store_roots:
            git_file = store_root / ".git"
            if git_file.is_file():
                git_file.unlink()
        self.temp_dir.cleanup()

    def write(self, relative_path: str, content: str = "") -> None:
        path = self.root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_at(self, base: Path, relative_path: str, content: str = "") -> None:
        path = base / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def write_openspec_item(
        self,
        base: Path,
        name: str,
        *,
        archived: bool,
        complete: bool = True,
        tasks_checked: bool = True,
    ) -> None:
        prefix = (
            f"openspec/changes/archive/{name}"
            if archived
            else f"openspec/changes/{name}"
        )
        self.write_at(
            base,
            f"{prefix}/proposal.md",
            "# Proposal\n\nUpdate the assessed repository workflow behavior.\n",
        )
        if not complete:
            return
        self.write_at(
            base,
            f"{prefix}/design.md",
            "# Design\n\nApply the change through the documented lifecycle.\n",
        )
        marker = "x" if tasks_checked else " "
        self.write_at(
            base,
            f"{prefix}/tasks.md",
            f"# Tasks\n\n- [{marker}] Implement and validate the planned change.\n",
        )

    def cat1_score(
        self,
        base: Path,
        *,
        cli_validation_passed: Optional[bool] = None,
    ) -> tuple[dict, int]:
        category = detect.detect_cat1(
            base,
            detect.build_tree(base),
            cli_validation_passed,
        )
        score = detect.score_cat1(category["signals"])[0]["score"]
        return category, score

    def register_store(
        self, store_id: str, store_root: Path, metadata_id: Optional[str] = None
    ) -> Path:
        xdg_data = self.root / "xdg-data"
        registry = xdg_data / "openspec/stores/registry.yaml"
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(
            "version: 1\n"
            "stores:\n"
            f"  {store_id}:\n"
            "    backend:\n"
            "      type: git\n"
            f"      local_path: {store_root}\n",
            encoding="utf-8",
        )
        self.write_at(
            store_root,
            ".openspec-store/store.yaml",
            f"version: 1\nid: {metadata_id or store_id}\n",
        )
        self.write_at(store_root, "openspec/config.yaml", "schema: spec-driven\n")
        self.store_roots.append(store_root)
        return xdg_data

    def track_store_files(self) -> Path:
        git_path = shutil.which("git")
        self.assertIsNotNone(git_path, "git is required for store regression tests")
        resolved_git_path = Path(git_path)
        git_dirs = self.root / "git-dirs"
        git_dirs.mkdir(exist_ok=True)
        for index, store_root in enumerate(self.store_roots):
            if not (store_root / ".git").exists():
                subprocess.run(
                    [
                        str(resolved_git_path),
                        "init",
                        "--quiet",
                        f"--separate-git-dir={git_dirs / f'store-{index}.git'}",
                        str(store_root),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                )
            subprocess.run(
                [str(resolved_git_path), "-C", str(store_root), "add", "--all"],
                check=True,
                capture_output=True,
                text=True,
            )
        return resolved_git_path

    def install_isolated_git(self, git_path: Path) -> Path:
        test_bin = self.root / "test-bin"
        test_bin.mkdir(exist_ok=True)
        if sys.platform == "win32":
            (test_bin / "git.cmd").write_text(
                f'@"{git_path}" %*\r\n', encoding="utf-8"
            )
        else:
            (test_bin / "git").symlink_to(git_path)
        return test_bin

    def run_detector(self, target: Path, xdg_data: Path) -> dict:
        git_path = self.track_store_files()
        test_bin = self.install_isolated_git(git_path)

        env = os.environ.copy()
        env["XDG_DATA_HOME"] = str(xdg_data)
        # Keep Git available so store regressions exercise tracked-file scanning,
        # while excluding any globally installed OpenSpec CLI from the test.
        env["PATH"] = str(test_bin)
        completed = subprocess.run(
            [sys.executable, str(DETECT_PATH), str(target), "--with-scoring"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
            timeout=30,
        )
        self.assertEqual(completed.returncode, 0, completed.stderr)
        return json.loads(completed.stdout)

    def test_openspec_package_and_cross_agent_skills_are_detected(self) -> None:
        self.write(
            "package.json",
            json.dumps({"devDependencies": {"@fission-ai/openspec": "1.10.0"}}),
        )
        self.write("openspec/config.yaml", "schema: spec-driven\n")
        self.write(
            ".agents/skills/openspec-propose/SKILL.md",
            "---\nname: openspec-propose\ndescription: Propose a change.\n---\n",
        )
        self.write(
            ".codex/skills/openspec-apply-change/SKILL.md",
            "---\nname: openspec-apply-change\ndescription: Apply a change.\n---\n",
        )

        tree = detect.build_tree(self.root)
        category = detect.detect_cat1(self.root, tree)

        self.assertTrue(category["signals"]["cli_dep"])
        self.assertEqual(category["signals"]["workflow_skills"], 2)

    def test_archive_only_lifecycle_scores_four_without_active_change(self) -> None:
        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
        self.write_at(
            target,
            "AGENTS.md",
            "Use OpenSpec to plan, validate, and archive repository changes.\n",
        )
        self.write_openspec_item(
            target,
            "2026-09-01-admin-ui-facade-routing",
            archived=True,
        )
        self.write_openspec_item(
            target,
            "2026-09-02-admin-ui-facade-validation",
            archived=True,
        )

        category, score = self.cat1_score(target, cli_validation_passed=True)

        self.assertEqual(category["signals"]["changes_count"], 0)
        self.assertEqual(category["signals"]["archived_count"], 2)
        self.assertEqual(category["signals"]["complete_work_items_count"], 2)
        self.assertTrue(category["signals"]["has_recent_spec_activity"])
        self.assertTrue(category["signals"]["workflow_integration_documented"])
        self.assertEqual(score, 4)

    def test_active_and_archived_lifecycle_still_scores_four(self) -> None:
        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
        self.write_at(
            target,
            "CONTRIBUTING.md",
            "Use OpenSpec for every planned repository change.\n",
        )
        self.write_openspec_item(
            target,
            "2026-09-01-completed-change",
            archived=True,
        )
        self.write_openspec_item(
            target,
            "current-change",
            archived=False,
            tasks_checked=False,
        )

        category, score = self.cat1_score(target, cli_validation_passed=True)

        self.assertEqual(category["signals"]["changes_count"], 1)
        self.assertEqual(category["signals"]["archived_count"], 1)
        self.assertEqual(category["signals"]["complete_work_items_count"], 2)
        self.assertEqual(score, 4)

    def test_gsd_phase_artifacts_reach_the_common_maturity_ceiling(self) -> None:
        target = self.root / "target"
        self.write_at(target, ".planning/config.json", "{}\n")
        self.write_at(
            target,
            "AGENTS.md",
            "Follow the GSD workflow to plan, implement, and validate each phase.\n",
        )
        for number, name in (("01", "foundation"), ("02", "delivery")):
            phase = f".planning/phases/{number}-{name}"
            self.write_at(
                target,
                f"{phase}/{number}-PLAN.md",
                "# Phase plan\n\nGoal: deliver the planned repository change.\n"
                "Tasks: implement the phase and run its validation checks.\n",
            )
            self.write_at(
                target,
                f"{phase}/{number}-VERIFICATION.md",
                "status: passed\n\nThe phase goals and checks were verified.\n",
            )

        category, score = self.cat1_score(target)

        self.assertEqual(category["signals"]["complete_work_items_count"], 2)
        self.assertEqual(category["signals"]["completed_work_items_count"], 2)
        self.assertEqual(score, 4)

    def test_bmad_epics_and_sprint_status_reach_the_common_maturity_ceiling(
        self,
    ) -> None:
        target = self.root / "target"
        self.write_at(target, "_bmad/core/config.yaml", "version: 1\n")
        self.write_at(
            target,
            "AGENTS.md",
            "Use the BMAD workflow to plan, implement, and validate repository epics.\n",
        )
        for number, epic_path in (
            ("1", "epic-1/overview.md"),
            ("2", "epic-2.md"),
        ):
            self.write_at(
                target,
                f"_bmad-output/planning-artifacts/epics/{epic_path}",
                f"# Epic {number}\n\n"
                "Goal: deliver repository behavior through planned stories.\n"
                "Stories: implement the change and validate its acceptance criteria.\n",
            )
        self.write_at(
            target,
            "project-tracking/sprint-status.yaml",
            "development_status:\n"
            "  epic-1: in-progress\n"
            "  1-1-foundation: done\n"
            "  1-2-validation: done\n"
            "  epic-2: done\n",
        )

        category, score = self.cat1_score(target)

        self.assertEqual(category["signals"]["complete_work_items_count"], 2)
        self.assertEqual(category["signals"]["completed_work_items_count"], 2)
        self.assertEqual(score, 4)

    def test_completion_requires_all_task_artifacts_to_be_checked(self) -> None:
        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
        prefix = "openspec/changes/in-progress"
        self.write_at(
            target,
            f"{prefix}/proposal.md",
            "# Proposal\n\nPlan a repository change.\n\n- [x] Review the proposal.\n",
        )
        self.write_at(
            target,
            f"{prefix}/design.md",
            "# Design\n\nImplement the documented workflow behavior.\n",
        )
        self.write_at(
            target,
            f"{prefix}/tasks.md",
            "# Tasks\n\n- [x] Implement the change.\n- [ ] Run validation.\n",
        )

        category, _ = self.cat1_score(target)

        self.assertFalse(category["signals"]["has_completed_cycle"])
        self.assertEqual(category["signals"]["completed_work_items_count"], 0)

    def test_bare_spec_mentions_do_not_document_workflow_integration(self) -> None:
        self.assertFalse(
            detect.documents_sdd_workflow("API specifications are in docs.")
        )
        self.assertFalse(detect.documents_sdd_workflow("Do not use specs."))
        self.assertFalse(
            detect.documents_sdd_workflow("Never follow the BMAD workflow.")
        )
        self.assertFalse(
            detect.documents_sdd_workflow("Must not use OpenSpec for changes.")
        )
        self.assertFalse(
            detect.documents_sdd_workflow("Should not follow the BMAD workflow.")
        )
        self.assertFalse(
            detect.documents_sdd_workflow("OpenSpec change history is in docs.")
        )
        self.assertTrue(
            detect.documents_sdd_workflow(
                "Use OpenSpec to plan, validate, and archive repository changes."
            )
        )

        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
        self.write_at(target, "AGENTS.md", "API specifications are in docs.\n")
        for name in ("one", "two"):
            self.write_openspec_item(target, name, archived=True)

        category, score = self.cat1_score(target, cli_validation_passed=True)

        self.assertFalse(category["signals"]["workflow_integration_documented"])
        self.assertEqual(score, 3)

    def test_placeholder_or_unrelated_work_item_files_remain_score_one(self) -> None:
        for case_name, relative_path, content in (
            ("empty", "proposal.md", ""),
            (
                "unrelated",
                "notes.txt",
                "This file contains unrelated repository notes only.\n",
            ),
        ):
            with self.subTest(case=case_name):
                target = self.root / case_name
                self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
                self.write_at(
                    target,
                    f"openspec/changes/example/{relative_path}",
                    content,
                )

                category, score = self.cat1_score(target)

                self.assertTrue(category["signals"]["has_spec_activity"])
                self.assertFalse(category["signals"]["has_substantive_spec_activity"])
                self.assertEqual(score, 1)

    def test_completed_cycle_requires_a_complete_completed_item(self) -> None:
        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
        self.write_at(
            target,
            "AGENTS.md",
            "Use OpenSpec to plan, validate, and archive repository changes.\n",
        )
        for name in ("active-one", "active-two"):
            self.write_openspec_item(
                target,
                name,
                archived=False,
                tasks_checked=False,
            )
        self.write_at(
            target,
            "openspec/changes/archive/placeholder/proposal.md",
            "",
        )

        category, score = self.cat1_score(target, cli_validation_passed=True)

        self.assertEqual(category["signals"]["complete_work_items_count"], 2)
        self.assertEqual(category["signals"]["archived_count"], 1)
        self.assertEqual(category["signals"]["completed_work_items_count"], 0)
        self.assertFalse(category["signals"]["has_completed_cycle"])
        self.assertEqual(score, 3)

    def test_supported_agent_instructions_count_for_integration_and_recency(
        self,
    ) -> None:
        for case_name, instruction_path in (
            ("copilot", ".github/copilot-instructions.md"),
            ("claude", "CLAUDE.md"),
        ):
            with self.subTest(surface=case_name):
                target = self.root / case_name
                self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
                for name in ("one", "two"):
                    self.write_openspec_item(target, name, archived=True)
                stale_timestamp = datetime(2020, 1, 1).timestamp()
                for path in (target / "openspec/changes").rglob("*"):
                    if path.is_file():
                        os.utime(path, (stale_timestamp, stale_timestamp))
                self.write_at(
                    target,
                    instruction_path,
                    "Use OpenSpec to plan, validate, and archive repository changes.\n",
                )

                category, score = self.cat1_score(
                    target,
                    cli_validation_passed=True,
                )

                self.assertEqual(
                    category["signals"]["workflow_integration_paths"],
                    [instruction_path],
                )
                self.assertTrue(category["signals"]["has_recent_spec_activity"])
                self.assertEqual(score, 4)

    def test_missing_lifecycle_signals_keep_score_below_four(self) -> None:
        cases = {
            "incomplete": {
                "archived": True,
                "complete": False,
                "stale": False,
                "cli_validation_passed": True,
            },
            "no-completed-cycle": {
                "archived": False,
                "complete": True,
                "stale": False,
                "cli_validation_passed": True,
            },
            "stale": {
                "archived": True,
                "complete": True,
                "stale": True,
                "cli_validation_passed": True,
            },
            "failed-cli": {
                "archived": True,
                "complete": True,
                "stale": False,
                "cli_validation_passed": False,
            },
        }
        for case_name, case in cases.items():
            with self.subTest(case=case_name):
                target = self.root / case_name
                self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")
                self.write_at(
                    target,
                    "AGENTS.md",
                    "Use OpenSpec to plan and archive repository changes.\n",
                )
                for suffix in ("one", "two"):
                    self.write_openspec_item(
                        target,
                        f"{case_name}-{suffix}",
                        archived=case["archived"],
                        complete=case["complete"],
                        tasks_checked=case["archived"],
                    )
                if case["stale"]:
                    stale_timestamp = datetime(2020, 1, 1).timestamp()
                    for path in (target / "openspec/changes").rglob("*"):
                        if path.is_file():
                            os.utime(path, (stale_timestamp, stale_timestamp))
                    os.utime(
                        target / "AGENTS.md",
                        (stale_timestamp, stale_timestamp),
                    )

                category, score = self.cat1_score(
                    target,
                    cli_validation_passed=case["cli_validation_passed"],
                )

                self.assertLess(score, 4)
                if case_name == "stale":
                    self.assertFalse(category["signals"]["has_recent_spec_activity"])
                if case_name == "failed-cli":
                    self.assertFalse(category["signals"]["cli_validation_passed"])

    def test_local_openspec_cli_validation_failure_is_detected(self) -> None:
        target = self.root / "target"
        self.write_at(target, "openspec/config.yaml", "schema: spec-driven\n")

        with (
            mock.patch.object(
                detect,
                "_find_openspec_cli",
                return_value="/fake/openspec",
            ),
            mock.patch.object(
                detect,
                "_run_json_command",
                return_value=(None, "validation failed"),
            ),
        ):
            passed, error = detect.validate_local_openspec_cli(
                target,
                detect.build_tree(target),
            )

        self.assertFalse(passed)
        self.assertEqual(error, "validation failed")

    def test_speckit_cli_check_failure_blocks_maturity_validation(self) -> None:
        target = self.root / "target"
        self.write_at(target, ".specify/config.json", "{}\n")

        with (
            mock.patch.object(
                detect,
                "_find_local_cli",
                return_value="/fake/specify",
            ),
            mock.patch.object(
                detect,
                "_run_status_command",
                return_value="required agent CLI missing",
            ),
        ):
            passed, error = detect.validate_local_spec_cli(
                target,
                detect.build_tree(target),
            )

        self.assertFalse(passed)
        self.assertIn("SpecKit check failed", error or "")

    def test_installed_cli_without_supported_check_is_unverified(self) -> None:
        cases = {
            "bmad": "_bmad/core/config.yaml",
            "gsd": ".planning/config.json",
        }
        for case_name, relative_path in cases.items():
            with self.subTest(system=case_name):
                target = self.root / case_name
                self.write_at(target, relative_path, "{}\n")
                with mock.patch.object(
                    detect,
                    "_find_local_cli",
                    return_value=f"/fake/{case_name}",
                ):
                    passed, error = detect.validate_local_spec_cli(
                        target,
                        detect.build_tree(target),
                    )

                self.assertFalse(passed)
                self.assertIn("unverified", error or "")

    def test_codex_skill_directory_counts_as_local_ai_tooling(self) -> None:
        self.write(
            ".codex/skills/review-code/SKILL.md",
            "---\nname: review-code\ndescription: Review code.\n---\n",
        )

        tree = detect.build_tree(self.root)
        category = detect.detect_cat3(self.root, tree)

        self.assertEqual(category["signals"]["local_skills"], 1)
        self.assertEqual(category["signals"]["total_skills"], 1)

    def test_local_skill_inventory_preserves_directory_precedence(self) -> None:
        self.write("skills/review-code/SKILL.md")
        self.write(".codex/skills/review-code/SKILL.md")

        skills = detect.find_local_skills(detect.build_tree(self.root))

        self.assertEqual(skills["review-code"], "skills/review-code/SKILL.md")

    def test_agents_file_configures_vendor_neutral_surface(self) -> None:
        self.write(
            "AGENTS.md",
            "# Repository guidance\n\n"
            "Run the repository validation command before submitting changes. "
            "Use the documentation tree for architecture and workflow context. "
            "Do not edit generated files or publish without explicit approval.\n",
        )
        category = detect.detect_cat5(self.root, detect.build_tree(self.root))
        agent_agnostic = category["signals"]["ides"]["agent_agnostic"]

        self.assertNotIn("codex", category["signals"]["ides"])
        self.assertTrue(agent_agnostic["has_config"])
        self.assertTrue(agent_agnostic["has_repo_specific"])
        self.assertFalse(agent_agnostic["has_skills"])

        scores = {
            item["id"]: item["score"] for item in detect.score_cat5(category["signals"])
        }
        self.assertEqual(scores["5.config_exists"], 3)
        self.assertEqual(scores["5.commands_and_skills"], 0)

    def test_agent_skills_configure_vendor_neutral_surface(self) -> None:
        self.write(".agents/skills/validate-change/SKILL.md")
        self.write(".agents/skills/review-change/SKILL.md")

        category = detect.detect_cat5(self.root, detect.build_tree(self.root))
        agent_agnostic = category["signals"]["ides"]["agent_agnostic"]

        self.assertNotIn("codex", category["signals"]["ides"])
        self.assertTrue(agent_agnostic["has_config"])
        self.assertTrue(agent_agnostic["has_skills"])
        self.assertTrue(agent_agnostic["has_multiple_contexts"])

        scores = {
            item["id"]: item["score"] for item in detect.score_cat5(category["signals"])
        }
        self.assertEqual(scores["5.config_exists"], 4)
        self.assertEqual(scores["5.commands_and_skills"], 2)

    def test_codex_config_files_configure_codex(self) -> None:
        self.write(".codex/config.toml", 'model = "gpt-5"\n')

        category = detect.detect_cat5(self.root, detect.build_tree(self.root))
        codex = category["signals"]["ides"]["codex"]

        self.assertTrue(codex["has_config"])
        self.assertFalse(codex["has_mcp"])

        self.write(".codex/mcp.json", "{}\n")
        category = detect.detect_cat5(self.root, detect.build_tree(self.root))
        codex = category["signals"]["ides"]["codex"]

        self.assertTrue(codex["has_config"])
        self.assertTrue(codex["has_mcp"])

    def test_category_five_uses_strongest_surface_for_each_metric(self) -> None:
        signals = {
            "ide_count": 2,
            "ides": {
                "cursor": {
                    "has_config": True,
                    "has_mcp": True,
                    "has_repo_specific": True,
                    "has_multiple_contexts": True,
                },
                "opencode": {
                    "has_config": True,
                    "has_mcp": False,
                    "has_repo_specific": False,
                    "has_multiple_contexts": True,
                    "has_commands": True,
                    "has_skills": True,
                    "has_apm": False,
                },
            },
        }

        scores = {item["id"]: item["score"] for item in detect.score_cat5(signals)}

        self.assertEqual(scores["5.commands_and_skills"], 3)
        self.assertEqual(scores["5.mcp_integration"], 4)

    def test_windows_local_openspec_cli_uses_cmd_shim(self) -> None:
        target = self.root / "target"
        cli = target / "node_modules/.bin/openspec.cmd"
        self.write_at(target, "node_modules/.bin/openspec.cmd", "@echo off\r\n")

        with (
            mock.patch.object(detect.sys, "platform", "win32"),
            mock.patch.object(detect.shutil, "which", return_value=None),
        ):
            resolved = detect._find_openspec_cli(target, {})

        self.assertEqual(resolved, str(cli))

    def test_doctor_failure_rejects_structurally_healthy_store(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\nreferences:\n  - id: shared-platform\n",
        )
        xdg_data = self.register_store("shared-platform", store)
        env = os.environ.copy()
        env["XDG_DATA_HOME"] = str(xdg_data)

        with (
            mock.patch.object(
                detect, "_find_openspec_cli", return_value="/fake/openspec"
            ),
            mock.patch.object(
                detect,
                "_run_json_command",
                side_effect=[
                    (None, "context failed"),
                    (None, "doctor failed"),
                ],
            ),
        ):
            evidence_roots, notes = detect.resolve_openspec_evidence_roots(target, env)

        self.assertEqual(evidence_roots, [])
        self.assertTrue(any("doctor failed" in note for note in notes))
        self.assertTrue(any("unhealthy" in note for note in notes))

    def test_category_one_does_not_combine_lifecycle_maturity_across_roots(
        self,
    ) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "package.json",
            json.dumps({"devDependencies": {"@fission-ai/openspec": "1.10.0"}}),
        )
        self.write_at(
            target,
            "AGENTS.md",
            "Use OpenSpec to plan and validate target repository changes.\n",
        )
        self.write_openspec_item(
            target,
            "target-change-one",
            archived=False,
            tasks_checked=False,
        )
        self.write_openspec_item(
            target,
            "target-change-two",
            archived=False,
            tasks_checked=False,
        )
        self.write_at(
            store,
            "AGENTS.md",
            "Use OpenSpec to plan and archive shared store changes.\n",
        )
        self.write_openspec_item(
            store,
            "2026-09-01-store-change",
            archived=True,
        )

        primary = detect.detect_cat1(target, detect.build_tree(target))
        store_category = detect.detect_cat1(store, detect.build_tree(store))
        merged = detect.merge_cat1_store_evidence(
            primary, [(detect.EvidenceRoot(store, "shared-platform"), store_category)]
        )
        scores = {
            item["id"]: item["score"]
            for item in detect.score_category(merged, detect.score_cat1)
        }

        self.assertEqual(
            detect.score_cat1(primary["signals"])[0]["score"],
            3,
        )
        self.assertEqual(
            detect.score_cat1(store_category["signals"])[0]["score"],
            2,
        )
        self.assertEqual(scores["1.system_and_artifacts"], 3)
        self.assertEqual(merged["signals"]["work_items_count"], 2)

    def test_category_four_uses_complete_documents_from_one_root(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(target, "CONTRIBUTING.md", "Run validation before review.\n")
        self.write_at(
            target,
            "docs/architecture/overview.md",
            "See docs/reference.md.\n",
        )
        self.write_at(
            store,
            "CONTRIBUTING.md",
            "Use OpenSpec and read docs/ before review.\n",
        )
        self.write_at(
            store,
            "docs/validation/workflow.md",
            "See docs/guides/contributing.md.\n",
        )
        self.write_at(store, "docs/guides/contributing.md", "Contributor guide.\n")

        primary = detect.detect_cat4(target, detect.build_tree(target))
        store_category = detect.detect_cat4(store, detect.build_tree(store))
        merged = detect.merge_cat4_store_evidence(
            primary, [(detect.EvidenceRoot(store, "shared-platform"), store_category)]
        )
        scores = {
            item["id"]: item["score"]
            for item in detect.score_category(merged, detect.score_cat4)
        }

        self.assertEqual(scores["4.contributing"], 3)
        self.assertEqual(scores["4.docs_structure"], 2)
        self.assertEqual(scores["4.content_quality"], 1)
        self.assertFalse(merged["signals"]["contributing"]["mentions_validation"])
        self.assertFalse(merged["signals"]["docs_structure"]["has_architecture"])

    def test_configured_store_contributes_to_existing_categories(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\n"
            "references:\n"
            "  - id: shared-platform\n"
            "    remote: git@example.com:platform/shared.git\n",
        )
        xdg_data = self.register_store("shared-platform", store)

        self.write_at(
            store,
            "AGENTS.md",
            "# Shared downstream repository guidance\n\n"
            "This repository map routes agents to docs/ for architecture, "
            "validation, and workflow context.\n"
            + "\n".join(f"Routing note {index}" for index in range(24)),
        )
        self.write_at(
            store,
            "CONTRIBUTING.md",
            "Use OpenSpec for planning. Run validation before review. "
            "Read docs/ for the contributor workflow.\n",
        )
        self.write_at(
            store,
            ".agents/skills/openspec-propose/SKILL.md",
            "---\nname: openspec-propose\ndescription: Plan changes.\n---\n",
        )
        self.write_at(
            store,
            ".agents/skills/validate-change/SKILL.md",
            "---\nname: validate-change\ndescription: Validate changes.\n---\n",
        )
        self.write_at(
            store,
            ".agents/skills/software-security/SKILL.md",
            "---\nname: software-security\ndescription: Perform a security review.\n---\n",
        )
        self.write_openspec_item(
            store,
            "2026-09-01-admin-ui-facade-store-reference",
            archived=True,
        )
        self.write_openspec_item(
            store,
            "2026-09-02-admin-ui-facade-assessment",
            archived=True,
        )
        # The configured store may contain unrelated active platform work. It
        # must not be required for the facade's archive-backed score.
        self.write_openspec_item(
            store,
            "unrelated-active-platform-change",
            archived=False,
            complete=False,
        )
        self.write_at(
            store,
            "docs/architecture/overview.md",
            "See docs/validation/workflow.md.\n",
        )
        self.write_at(
            store,
            "docs/validation/workflow.md",
            "See docs/guides/contributing.md.\n",
        )
        self.write_at(
            store,
            "docs/guides/contributing.md",
            "See docs/architecture/overview.md.\n",
        )

        output = self.run_detector(target, xdg_data)

        self.assertEqual(
            set(output),
            {
                "version",
                "repo_root",
                "scoring_enabled",
                "languages",
                "package_managers",
                "monorepo",
                "candidates",
                "selected_commands",
                "additional_scans",
                "categories",
                "ai_validation",
                "scores",
                "recommended_actions",
            },
        )
        self.assertTrue(output["categories"]["1"]["signals"]["spec_system_dir"])
        cat1_scores = {
            item["id"]: item["score"]
            for item in output["scores"]["sub_metrics"]
            if item["id"].startswith("1.")
        }
        self.assertEqual(cat1_scores["1.system_and_artifacts"], 4)
        self.assertEqual(output["categories"]["1"]["signals"]["changes_count"], 1)
        self.assertEqual(output["categories"]["3"]["signals"]["total_skills"], 3)
        self.assertEqual(output["categories"]["3"]["signals"]["security_skills"], 1)
        self.assertTrue(output["categories"]["4"]["signals"]["agents_md"]["exists"])
        self.assertGreater(output["categories"]["5"]["signals"]["ide_count"], 0)
        self.assertTrue(output["categories"]["6"]["signals"]["repo_map"])
        self.assertTrue(
            any(
                "OpenSpec store 'shared-platform'" in item
                for item in output["categories"]["3"]["evidence"]
            )
        )
        self.assertNotIn(str(store), json.dumps(output))

    def test_store_pointer_resolves_registered_store(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\nstore: shared-platform\n",
        )
        xdg_data = self.register_store("shared-platform", store)
        self.write_at(store, ".agents/skills/shared-workflow/SKILL.md")

        output = self.run_detector(target, xdg_data)

        self.assertEqual(output["categories"]["3"]["signals"]["total_skills"], 1)

    def test_configured_store_validation_result_and_error_are_propagated(
        self,
    ) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\nstore: shared-platform\n",
        )
        xdg_data = self.register_store("shared-platform", store)
        commands: list[list[str]] = []

        def run_json_command(
            command: list[str],
            cwd: Path,
            env: dict[str, str],
        ) -> tuple[Optional[dict], Optional[str]]:
            del cwd, env
            commands.append(command)
            if "doctor" in command:
                return {"root": {"healthy": True}}, None
            if "validate" in command:
                return None, f"{store}/openspec/changes/broken is invalid"
            return None, None

        with (
            mock.patch.object(
                detect,
                "_find_openspec_cli",
                return_value="/fake/openspec",
            ),
            mock.patch.object(
                detect,
                "_run_json_command",
                side_effect=run_json_command,
            ),
        ):
            evidence_roots, notes = detect.resolve_openspec_evidence_roots(
                target,
                {
                    "XDG_DATA_HOME": str(xdg_data),
                    "PATH": "",
                },
            )

        self.assertEqual(len(evidence_roots), 1)
        self.assertFalse(evidence_roots[0].cli_validation_passed)
        self.assertIn("<configured-store>", evidence_roots[0].cli_validation_error or "")
        self.assertNotIn(str(store), evidence_roots[0].cli_validation_error or "")
        self.assertTrue(any("validation did not pass" in note for note in notes))
        self.assertTrue(
            any(
                command[-2:] == ["--store", "shared-platform"]
                for command in commands
                if "validate" in command
            )
        )

    def test_store_tree_excludes_untracked_files_when_git_is_available(self) -> None:
        store = self.root / "shared-store"
        self.register_store("shared-platform", store)
        self.write_at(store, ".agents/skills/tracked/SKILL.md")
        git_path = self.track_store_files()
        self.write_at(store, ".agents/skills/untracked/SKILL.md")

        with mock.patch.dict(
            os.environ, {"PATH": str(self.install_isolated_git(git_path))}
        ):
            tree = detect.build_store_tree(store)

        self.assertIn(".agents/skills/tracked/SKILL.md", tree)
        self.assertNotIn(".agents/skills/untracked/SKILL.md", tree)

    def test_unrelated_registered_store_is_ignored(self) -> None:
        target = self.root / "target"
        store = self.root / "unrelated-store"
        self.write_at(target, "README.md", "# Target\n")
        xdg_data = self.register_store("unrelated", store)
        self.write_at(store, ".agents/skills/unrelated/SKILL.md")
        self.write_at(store, "AGENTS.md", "# Unrelated repository guidance\n")
        self.write_openspec_item(
            store,
            "unrelated-active-change",
            archived=False,
            tasks_checked=False,
        )

        output = self.run_detector(target, xdg_data)

        cat1_score = next(
            item["score"]
            for item in output["scores"]["sub_metrics"]
            if item["id"] == "1.system_and_artifacts"
        )
        self.assertEqual(cat1_score, 0)
        self.assertEqual(output["categories"]["3"]["signals"]["total_skills"], 0)
        self.assertEqual(output["categories"]["5"]["signals"]["ide_count"], 0)

    def test_unhealthy_configured_store_is_not_scored(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\nreferences:\n  - id: shared-platform\n",
        )
        xdg_data = self.register_store(
            "shared-platform", store, metadata_id="different-store"
        )
        self.write_at(store, ".agents/skills/shared-workflow/SKILL.md")

        output = self.run_detector(target, xdg_data)

        self.assertEqual(output["categories"]["3"]["signals"]["total_skills"], 0)
        self.assertTrue(
            any("unhealthy" in item for item in output["categories"]["1"]["evidence"])
        )

    def test_duplicate_store_skill_is_counted_once(self) -> None:
        target = self.root / "target"
        store = self.root / "shared-store"
        self.write_at(
            target,
            "openspec/config.yaml",
            "schema: spec-driven\nreferences:\n  - id: shared-platform\n",
        )
        self.write_at(target, ".agents/skills/shared-workflow/SKILL.md")
        xdg_data = self.register_store("shared-platform", store)
        self.write_at(store, ".agents/skills/shared-workflow/SKILL.md")

        output = self.run_detector(target, xdg_data)

        self.assertEqual(output["categories"]["3"]["signals"]["total_skills"], 1)


if __name__ == "__main__":
    unittest.main()
