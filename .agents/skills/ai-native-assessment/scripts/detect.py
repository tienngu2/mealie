#!/usr/bin/env python3
"""Deterministic AI-native assessment scanner.

Scans a repository and outputs JSON for language probes, command synthesis,
monorepo detection, additional scans, and evidence-rich category signals.
Deterministic category scoring is available as an opt-in mode.

Usage: python scripts/detect.py [repo_root] [--with-scoring]
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Set, Tuple

VERSION = "1.2.0"
RECENT_SPEC_ACTIVITY_DAYS = 180

SKIP_DIRS = frozenset(
    [
        "node_modules",
        ".git",
        "dist",
        "build",
        "__pycache__",
        ".venv",
        "vendor",
        "target",
        ".next",
        ".worktrees",
    ]
)

PRIORITY_ORDER = {
    "user_override": 0,
    "explicit_script": 1,
    "framework_target": 2,
    "config_file": 3,
    "workflow": 4,
    "dependency_fallback": 5,
    "language_default": 6,
    "ai_inferred": 7,
}

SOURCE_TYPE_BY_PRIORITY = {
    "user_override": "user_override",
    "explicit_script": "script_entry",
    "framework_target": "framework_target",
    "config_file": "config",
    "workflow": "workflow",
    "dependency_fallback": "dependency",
    "language_default": "manifest_default",
    "ai_inferred": "ai_inferred",
}

CATEGORY_WEIGHTS = {
    1: 0.20,
    2: 0.25,
    3: 0.15,
    4: 0.15,
    5: 0.10,
    6: 0.15,
}

LOCAL_SKILL_PREFIXES = (
    "skills/",
    ".agents/skills/",
    ".codex/skills/",
    ".opencode/skills/",
    ".cursor/skills/",
    ".github/skills/",
    ".claude/skills/",
    ".windsurf/skills/",
)


# ---------------------------------------------------------------------------
# Infrastructure
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceRoot:
    """An explicitly configured OpenSpec store that contributes assessment evidence."""

    path: Path
    store_id: str
    cli_validation_passed: Optional[bool] = None
    cli_validation_error: Optional[str] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic AI-native assessment scanner"
    )
    parser.add_argument(
        "repo_root", nargs="?", default=".", help="Path to repository root"
    )
    parser.add_argument(
        "--with-scoring",
        action="store_true",
        help="Include deterministic category scores and recommended actions",
    )
    args = parser.parse_args()
    root = Path(args.repo_root).resolve()
    if not root.is_dir():
        error_exit(f"Not a directory: {root}")
    args.repo_root = root
    return args


def error_exit(msg: str, code: int = 1) -> None:
    json.dump({"error": msg}, sys.stderr)
    sys.stderr.write("\n")
    sys.exit(code)


def read_text(path: Path) -> Optional[str]:
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        try:
            return path.read_text(encoding="latin-1")
        except Exception:
            return None
    except Exception:
        return None


def _yaml_scalar(raw_value: str) -> str:
    """Parse the simple string scalars used by OpenSpec config and registry files."""
    value = raw_value.strip()
    if not value:
        return ""
    if value[0] in {"'", '"'} and value[-1:] == value[0]:
        return value[1:-1]
    return value.split(" #", 1)[0].strip()


def configured_openspec_store_ids(root: Path) -> List[str]:
    """Return store ids explicitly selected or referenced by the target repo."""
    config_path = next(
        (
            root / relative
            for relative in ("openspec/config.yaml", "openspec/config.yml")
            if (root / relative).is_file()
        ),
        None,
    )
    if config_path is None:
        return []

    content = read_text(config_path)
    if not content:
        return []

    store_ids: List[str] = []
    in_references = False
    references_indent = 0
    for raw_line in content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))

        store_match = re.match(r"^store\s*:\s*(.+)$", raw_line)
        if store_match:
            store_id = _yaml_scalar(store_match.group(1))
            if store_id:
                store_ids.append(store_id)
            in_references = False
            continue

        if re.match(r"^references\s*:\s*$", raw_line):
            in_references = True
            references_indent = indent
            continue

        if in_references and indent <= references_indent:
            in_references = False

        if in_references:
            reference_match = re.match(r"^\s*(?:-\s*)?id\s*:\s*(.+)$", raw_line)
            if reference_match:
                store_id = _yaml_scalar(reference_match.group(1))
                if store_id:
                    store_ids.append(store_id)

    return list(dict.fromkeys(store_ids))


def _openspec_registry_path(env: Mapping[str, str]) -> Path:
    if env.get("XDG_DATA_HOME"):
        data_home = Path(env["XDG_DATA_HOME"]).expanduser()
    elif sys.platform == "win32" and env.get("LOCALAPPDATA"):
        data_home = Path(env["LOCALAPPDATA"]).expanduser()
    elif sys.platform == "win32":
        data_home = Path.home() / "AppData" / "Local"
    else:
        data_home = Path.home() / ".local" / "share"
    return data_home / "openspec" / "stores" / "registry.yaml"


def _registered_store_paths(
    store_ids: List[str], env: Mapping[str, str]
) -> Dict[str, Path]:
    """Read the first-party OpenSpec registry without requiring a CLI on PATH."""
    registry_content = read_text(_openspec_registry_path(env))
    if not registry_content:
        return {}

    requested = set(store_ids)
    result: Dict[str, Path] = {}
    in_stores = False
    current_id: Optional[str] = None
    for raw_line in registry_content.splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        if raw_line == "stores:":
            in_stores = True
            current_id = None
            continue
        if not in_stores:
            continue
        if indent == 0:
            break

        store_match = (
            re.match(r"^  ([^:#][^:]*):\s*$", raw_line) if indent == 2 else None
        )
        if store_match is not None:
            current_id = _yaml_scalar(store_match.group(1))
            continue

        path_match = re.match(r"^\s+local_path\s*:\s*(.+)$", raw_line)
        if current_id in requested and path_match:
            local_path = _yaml_scalar(path_match.group(1))
            if local_path:
                result[current_id] = Path(local_path).expanduser().resolve()

    return result


def _store_metadata_id(store_root: Path) -> Optional[str]:
    content = read_text(store_root / ".openspec-store" / "store.yaml")
    if not content:
        return None
    for raw_line in content.splitlines():
        match = re.match(r"^id\s*:\s*(.+)$", raw_line)
        if match:
            return _yaml_scalar(match.group(1))
    return None


def _store_is_structurally_healthy(store_id: str, store_root: Path) -> bool:
    return (
        store_root.is_dir()
        and _store_metadata_id(store_root) == store_id
        and any(
            (store_root / relative).is_file()
            for relative in ("openspec/config.yaml", "openspec/config.yml")
        )
    )


def _find_openspec_cli(root: Path, registered_paths: Dict[str, Path]) -> Optional[str]:
    def local_cli(bin_dir: Path) -> Optional[Path]:
        names = (
            ("openspec.cmd", "openspec.exe", "openspec.bat", "openspec")
            if sys.platform == "win32"
            else ("openspec",)
        )
        for name in names:
            candidate = bin_dir / name
            if candidate.is_file() and (
                sys.platform == "win32" or os.access(candidate, os.X_OK)
            ):
                return candidate
        return None

    candidates: List[Path] = []
    target_cli = local_cli(root / "node_modules" / ".bin")
    if target_cli:
        candidates.append(target_cli)
    path_cli = shutil.which("openspec")
    if path_cli:
        candidates.append(Path(path_cli))
    for store_root in registered_paths.values():
        store_cli = local_cli(store_root / "node_modules" / ".bin")
        if store_cli:
            candidates.append(store_cli)
    for candidate in candidates:
        if candidate.is_file() and (
            sys.platform == "win32" or os.access(candidate, os.X_OK)
        ):
            return str(candidate)
    return None


def _find_local_cli(root: Path, names: Tuple[str, ...]) -> Optional[str]:
    """Find a repository-local or PATH-installed CLI without executing it."""
    suffixes = (".cmd", ".exe", ".bat", "") if sys.platform == "win32" else ("",)
    for name in names:
        for suffix in suffixes:
            candidate = root / "node_modules" / ".bin" / f"{name}{suffix}"
            if candidate.is_file() and (
                sys.platform == "win32" or os.access(candidate, os.X_OK)
            ):
                return str(candidate)
        path_cli = shutil.which(name)
        if path_cli:
            return path_cli
    return None


def _run_json_command(
    command: List[str], cwd: Path, env: Mapping[str, str]
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=dict(env),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return None, str(exc)
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip()
        return None, detail or f"command exited {completed.returncode}"
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        return None, f"invalid JSON: {exc}"
    if not isinstance(payload, dict):
        return None, "JSON response was not an object"
    return payload, None


def _run_status_command(
    command: List[str], cwd: Path, env: Mapping[str, str]
) -> Optional[str]:
    """Run a read-only status/check command and return its failure detail."""
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=dict(env),
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        return str(exc)
    if completed.returncode == 0:
        return None
    detail = completed.stderr.strip() or completed.stdout.strip()
    return detail or f"command exited {completed.returncode}"


def _sanitize_cli_detail(detail: Optional[str], paths: Set[Path]) -> Optional[str]:
    """Keep local filesystem paths out of reportable CLI failure evidence."""
    if detail is None:
        return None
    sanitized = detail
    aliases: Set[str] = set()
    for item in paths:
        aliases.update((str(item), str(item.absolute()), str(item.resolve())))
    aliases.update(
        path.removeprefix("/private")
        for path in tuple(aliases)
        if path.startswith("/private/")
    )
    for path in sorted(aliases, key=len, reverse=True):
        sanitized = sanitized.replace(path, "<configured-store>")
    return sanitized


def resolve_openspec_evidence_roots(
    root: Path, env: Optional[Mapping[str, str]] = None
) -> Tuple[List[EvidenceRoot], List[str]]:
    """Resolve only OpenSpec stores explicitly configured by the target repo."""
    store_ids = configured_openspec_store_ids(root)
    if not store_ids:
        return [], []

    command_env: Mapping[str, str] = env or os.environ
    registered_paths = _registered_store_paths(store_ids, command_env)
    openspec_cli = _find_openspec_cli(root, registered_paths)
    notes: List[str] = []
    resolved_paths: Dict[str, Path] = {}

    if openspec_cli:
        context, context_error = _run_json_command(
            [openspec_cli, "context", "--json"], root, command_env
        )
        if context:
            candidates = [context.get("root", {})]
            members = context.get("members", [])
            if isinstance(members, list):
                candidates.extend(item for item in members if isinstance(item, dict))
            for candidate in candidates:
                store_id = candidate.get("store_id") or candidate.get("id")
                path_value = candidate.get("path")
                if store_id not in store_ids or not isinstance(path_value, str):
                    continue
                store_path = Path(path_value).expanduser().resolve()
                if store_path != root:
                    resolved_paths[store_id] = store_path
        elif context_error:
            notes.append(f"OpenSpec context resolution failed: {context_error}")

    for store_id, store_path in registered_paths.items():
        resolved_paths.setdefault(store_id, store_path)

    evidence_roots: List[EvidenceRoot] = []
    for store_id in store_ids:
        store_root = resolved_paths.get(store_id)
        if store_root is None:
            notes.append(f"Configured OpenSpec store '{store_id}' is not registered")
            continue

        healthy = _store_is_structurally_healthy(store_id, store_root)
        if openspec_cli:
            doctor, doctor_error = _run_json_command(
                [openspec_cli, "doctor", "--json", "--store", store_id],
                root,
                command_env,
            )
            if doctor is not None:
                doctor_root = doctor.get("root", {})
                healthy = (
                    isinstance(doctor_root, dict) and doctor_root.get("healthy") is True
                )
            elif doctor_error:
                healthy = False
                notes.append(
                    f"OpenSpec doctor failed for store '{store_id}': {doctor_error}"
                )

        if not healthy:
            notes.append(f"Configured OpenSpec store '{store_id}' is unhealthy")
            continue
        cli_validation_passed: Optional[bool] = None
        cli_validation_error: Optional[str] = None
        if openspec_cli:
            validation, validation_error = _run_json_command(
                [
                    openspec_cli,
                    "validate",
                    "--all",
                    "--json",
                    "--store",
                    store_id,
                ],
                root,
                command_env,
            )
            cli_validation_passed = validation is not None
            cli_validation_error = _sanitize_cli_detail(
                validation_error,
                {root, store_root},
            )
            if cli_validation_error:
                notes.append(
                    f"Configured OpenSpec store '{store_id}' validation did not pass: "
                    f"{cli_validation_error}"
                )
        evidence_roots.append(
            EvidenceRoot(
                path=store_root,
                store_id=store_id,
                cli_validation_passed=cli_validation_passed,
                cli_validation_error=cli_validation_error,
            )
        )

    return evidence_roots, notes


def validate_local_openspec_cli(
    root: Path,
    tree: Set[str],
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[Optional[bool], Optional[str]]:
    """Run the local OpenSpec validation when an OpenSpec CLI is available."""
    if not tree_has_dir(tree, "openspec"):
        return None, None

    command_env: Mapping[str, str] = env or os.environ
    openspec_cli = _find_openspec_cli(root, {})
    if not openspec_cli:
        return None, None

    status, status_error = _run_json_command(
        [openspec_cli, "validate", "--all", "--json"],
        root,
        command_env,
    )
    if status is not None:
        return True, None
    return False, status_error or "OpenSpec validation failed"


def validate_local_spec_cli(
    root: Path,
    tree: Set[str],
    env: Optional[Mapping[str, str]] = None,
) -> Tuple[Optional[bool], Optional[str]]:
    """Validate each installed CLI for a recognized local SDD system.

    OpenSpec and SpecKit expose safe read-only validation/check commands. BMAD
    and GSD currently expose installation/runtime entry points but no stable
    repository status/check command that this detector can invoke safely. An
    installed CLI without a supported check is therefore unverified rather than
    silently treated as healthy.
    """
    command_env: Mapping[str, str] = env or os.environ
    validation_seen = False
    problems: List[str] = []

    openspec_result, openspec_error = validate_local_openspec_cli(
        root, tree, command_env
    )
    if openspec_result is not None:
        validation_seen = True
        if not openspec_result:
            problems.append(openspec_error or "OpenSpec validation failed")

    if tree_has_dir(tree, ".specify"):
        specify_cli = _find_local_cli(root, ("specify", "specify-cli"))
        if specify_cli:
            validation_seen = True
            specify_error = _run_status_command(
                [specify_cli, "check"], root, command_env
            )
            if specify_error:
                problems.append(f"SpecKit check failed: {specify_error}")

    unsupported_installed: List[str] = []
    if any(
        tree_has_dir(tree, name)
        for name in ("_bmad", ".bmad-core", "bmad-core", ".bmad-method")
    ) and _find_local_cli(root, ("bmad", "bmad-method")):
        unsupported_installed.append("BMAD")
    if tree_has_dir(tree, ".planning") and _find_local_cli(
        root, ("gsd-core", "gsd-tools", "gsd_run")
    ):
        unsupported_installed.append("GSD")
    if unsupported_installed:
        validation_seen = True
        problems.append(
            f"{' and '.join(unsupported_installed)} CLI validation is unverified: "
            "no supported read-only repository status/check command"
        )

    if problems:
        return False, "; ".join(problems)
    if validation_seen:
        return True, None
    return None, None


def parse_apm_manifest(root: Path, tree: Set[str]) -> Dict[str, Any]:
    """Parse simple APM manifest structure for remote skills and MCP entries."""
    result = {
        "present": False,
        "skills": [],
        "security_skills": [],
        "mcp_entries": 0,
        "scripts": set(),
    }
    apm_path: Optional[str] = None
    if tree_has(tree, "apm.yml"):
        apm_path = "apm.yml"
    elif tree_has(tree, "apm.yaml"):
        apm_path = "apm.yaml"
    if not apm_path:
        return result

    content = read_text(root / apm_path)
    if not content:
        return result

    result["present"] = True
    in_scripts = False
    in_apm_deps = False
    in_mcp_deps = False
    script_indent: Optional[int] = None
    dep_indent: Optional[int] = None

    for raw_line in content.split("\n"):
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if stripped == "scripts:" or stripped.startswith("scripts:"):
            in_scripts = True
            in_apm_deps = False
            in_mcp_deps = False
            script_indent = indent
            dep_indent = None
            continue
        if stripped == "dependencies:" or stripped.startswith("dependencies:"):
            in_scripts = False
            in_apm_deps = False
            in_mcp_deps = False
            script_indent = None
            dep_indent = None
            continue
        if stripped == "apm:" or stripped.startswith("apm:"):
            in_apm_deps = True
            in_mcp_deps = False
            in_scripts = False
            dep_indent = indent
            continue
        if stripped == "mcp:" or stripped.startswith("mcp:"):
            in_mcp_deps = True
            in_apm_deps = False
            in_scripts = False
            dep_indent = indent
            continue

        if (
            in_scripts
            and script_indent is not None
            and indent <= script_indent
            and not stripped.startswith("- ")
        ):
            in_scripts = False
        if (
            (in_apm_deps or in_mcp_deps)
            and dep_indent is not None
            and indent <= dep_indent
            and not stripped.startswith("- ")
        ):
            in_apm_deps = False
            in_mcp_deps = False

        if in_scripts and ":" in stripped and not stripped.startswith("- "):
            key = stripped.split(":", 1)[0].strip()
            if key:
                result["scripts"].add(key)
            continue

        if in_apm_deps and stripped.startswith("- "):
            dep = stripped[2:].strip().strip("'\"")
            if dep and not dep.startswith("#"):
                result["skills"].append(dep)
                dep_lower = dep.lower()
                if any(
                    kw in dep_lower
                    for kw in ["security", "codeguard", "vulnerability", "sast"]
                ):
                    result["security_skills"].append(dep)
            continue

        if in_mcp_deps and stripped.startswith("- "):
            result["mcp_entries"] += 1

    return result


def build_tree(root: Path) -> Set[str]:
    """Build set of relative paths from root, skipping SKIP_DIRS."""
    paths: Set[str] = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        rel_dir = os.path.relpath(dirpath, root)
        if rel_dir == ".":
            rel_dir = ""
        for f in filenames:
            if rel_dir:
                paths.add(f"{rel_dir}/{f}")
            else:
                paths.add(f)
        for d in dirnames:
            if rel_dir:
                paths.add(f"{rel_dir}/{d}/")
            else:
                paths.add(f"{d}/")
    return paths


def build_store_tree(root: Path) -> Set[str]:
    """Build a store tree from tracked files so nested worktrees are not inherited."""
    try:
        completed = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            check=False,
            capture_output=True,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return build_tree(root)
    if completed.returncode != 0:
        return build_tree(root)

    paths: Set[str] = set()
    for raw_path in completed.stdout.split(b"\0"):
        if not raw_path:
            continue
        try:
            path = raw_path.decode("utf-8")
        except UnicodeDecodeError:
            continue
        if any(part in SKIP_DIRS for part in Path(path).parts):
            continue
        paths.add(path)
        parent = Path(path).parent
        while str(parent) not in {"", "."}:
            paths.add(f"{parent.as_posix()}/")
            parent = parent.parent
    return paths


def tree_has(tree: Set[str], path: str) -> bool:
    return path in tree


def tree_has_dir(tree: Set[str], path: str) -> bool:
    if not path.endswith("/"):
        path = path + "/"
    return path in tree or any(p.startswith(path) for p in tree)


def tree_glob(tree: Set[str], pattern: str) -> List[str]:
    """Simple glob matching against tree paths."""
    import fnmatch

    return sorted(p for p in tree if fnmatch.fnmatch(p, pattern))


def find_local_skills(tree: Set[str]) -> Dict[str, str]:
    """Return de-duplicated repo-local skill names and their SKILL.md paths."""
    skills: Dict[str, str] = {}
    skill_priorities: Dict[str, int] = {}
    for path in sorted(tree):
        if not path.endswith("SKILL.md"):
            continue
        for priority, prefix in enumerate(LOCAL_SKILL_PREFIXES):
            if not path.startswith(prefix):
                continue
            remainder = path[len(prefix) :]
            if "/" not in remainder:
                break
            name = remainder.split("/", 1)[0]
            if name and (
                name not in skill_priorities or priority < skill_priorities[name]
            ):
                skill_priorities[name] = priority
                skills[name] = path
            break
    return skills


# Word-boundary match for spec-driven-development references. Matches words
# that start with "spec" (spec, specs, specify, specification, speckit,
# openspec) but not unrelated words such as "inspect", "respect", or
# "especially".
_SPEC_WORD_RE = re.compile(r"\b(?:open)?spec", re.IGNORECASE)
_SDD_SYSTEM_RE = re.compile(
    r"\b(?:openspec|spec(?:ification)?[ -]?kit|speckit|"
    r"bmad(?:-method)?|gsd|git[ .-]*ship[ .-]*done|"
    r"spec[- ]driven(?: development)?)\b",
    re.IGNORECASE,
)
_SPECIFY_COMMAND_RE = re.compile(
    r"(?:^|[\s`$/])specify\s+(?:check|init|version|self|extension|preset|workflow)\b",
    re.IGNORECASE,
)
_GENERIC_SPEC_RE = re.compile(
    r"\bspec(?:s|ification|ifications)?\b",
    re.IGNORECASE,
)
_GENERIC_SDD_GUIDANCE_RE = re.compile(
    r"(?:"
    r"\b(?:use|follow|write|create|update|review|validate|archive)\b"
    r"[^.!?\n]{0,80}\bspec(?:s|ification|ifications)?\b"
    r"|"
    r"\bspec(?:s|ification|ifications)?\b[^.!?\n]{0,80}"
    r"\b(?:must|should|before|after|then|workflow|process)\b"
    r")",
    re.IGNORECASE,
)
_SDD_ACTION_RE = re.compile(
    r"\b(?:use|using|follow\w*|run\w*|write|writing|creat\w*|updat\w*|"
    r"review\w*|propos\w*|validat\w*|archiv\w*|apply|applying|"
    r"implement\w*)\b",
    re.IGNORECASE,
)
_NEGATED_SPEC_ACTION_RE = re.compile(
    r"\b(?:(?:do|must|should|shall|may|can)\s+not|"
    r"don't|mustn't|shouldn't|cannot|can't|never)\s+(?:\w+\s+){0,3}"
    r"(?:use|follow|run|write|create|update|review|plan|validate|archive)?"
    r"\s*(?:openspec|spec(?:ification)?[ -]?kit|speckit|bmad(?:-method)?|gsd|"
    r"spec(?:s|ification|ifications)?)\b",
    re.IGNORECASE,
)
_AGENT_INSTRUCTION_FILES = frozenset(
    {
        "AGENTS.md",
        "CLAUDE.md",
        "CONTRIBUTING.md",
        ".cursorrules",
        ".windsurfrules",
        ".github/copilot-instructions.md",
    }
)
_AGENT_INSTRUCTION_PREFIXES = (
    ".github/instructions/",
    ".cursor/rules/",
    ".windsurf/rules/",
)


def mentions_spec(text: str) -> bool:
    """True when text references spec-driven development by word boundary."""
    return bool(_SPEC_WORD_RE.search(text))


def documents_sdd_workflow(text: str) -> bool:
    """True when text gives actionable, affirmative SDD workflow guidance."""
    for segment in re.split(r"(?<=[.!?])\s+|\n+", text):
        if not segment.strip():
            continue
        if _NEGATED_SPEC_ACTION_RE.search(segment):
            continue
        if (
            _SDD_SYSTEM_RE.search(segment) or _SPECIFY_COMMAND_RE.search(segment)
        ) and _SDD_ACTION_RE.search(segment):
            return True
        if _GENERIC_SPEC_RE.search(segment) and _GENERIC_SDD_GUIDANCE_RE.search(
            segment
        ):
            return True
    return False


def find_sdd_workflow_instruction_paths(root: Path, tree: Set[str]) -> Set[str]:
    """Find supported contributor and agent docs with actionable SDD guidance."""
    candidates = {
        path
        for path in tree
        if path in _AGENT_INSTRUCTION_FILES
        or re.match(r"^\.github/copilot-.*\.md$", path)
        or path.startswith(_AGENT_INSTRUCTION_PREFIXES)
    }
    return {
        path
        for path in candidates
        if documents_sdd_workflow(read_text(root / path) or "")
    }


def specs_dir_has_planning_artifacts(tree: Set[str]) -> bool:
    """Heuristic: a bare `specs/` directory is a spec-driven system only when
    it holds planning artifacts -- per-item subdirectories or markdown/text
    planning docs -- rather than just OpenAPI/test spec files at the top level.
    """
    for p in tree:
        if not p.startswith("specs/"):
            continue
        rest = p[len("specs/") :]
        if not rest:
            continue
        # Per-item subdirectory (e.g., specs/001-feature/spec.md) is strong
        # evidence of spec-driven planning.
        if "/" in rest:
            return True
        # Top-level markdown/text planning doc directly under specs/.
        if rest.lower().endswith((".md", ".markdown", ".txt", ".rst")):
            return True
    return False


def planning_dir_is_gsd(tree: Set[str]) -> bool:
    """Heuristic: a `.planning/` directory is GSD (Git. Ship. Done.) only when
    it carries GSD's confirmed fingerprint files (`STATE.md`, `ROADMAP.md`, or
    `config.json`) or a `phases/` subtree. `.planning/` is a generic-sounding
    name, so require these markers to avoid false positives.
    """
    if tree_has(tree, ".planning/STATE.md"):
        return True
    if tree_has(tree, ".planning/ROADMAP.md"):
        return True
    if tree_has(tree, ".planning/config.json"):
        return True
    if tree_has_dir(tree, ".planning/phases"):
        return True
    return False


# ---------------------------------------------------------------------------
# Inline TOML parser (minimal, enough for pyproject.toml)
# ---------------------------------------------------------------------------


def parse_toml(content: str) -> Dict[str, Any]:
    """Minimal TOML parser for pyproject.toml files."""
    try:
        import tomllib

        return tomllib.loads(content)
    except ImportError:
        pass
    # Fallback inline parser for Python 3.9-3.10
    return _parse_toml_fallback(content)


def _parse_toml_fallback(content: str) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    current_section: Optional[List[str]] = None
    lines = content.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#"):
            continue
        # Section header
        m = re.match(r"^\[([^\]]+)\]$", line)
        if m:
            current_section = m.group(1).split(".")
            _ensure_section(result, current_section)
            continue
        # Array of tables
        m = re.match(r"^\[\[([^\]]+)\]\]$", line)
        if m:
            current_section = m.group(1).split(".")
            parent = (
                _ensure_section(result, current_section[:-1])
                if len(current_section) > 1
                else result
            )
            key = current_section[-1]
            if key not in parent:
                parent[key] = []
            parent[key].append({})
            continue
        # Key-value
        m = re.match(r"^([A-Za-z0-9_\-]+)\s*=\s*(.+)$", line)
        if m:
            key = m.group(1)
            val_str = m.group(2).strip()
            # Handle multiline arrays
            if val_str.startswith("[") and "]" not in val_str:
                while i < len(lines) and "]" not in val_str:
                    val_str += " " + lines[i].strip()
                    i += 1
            # Handle multiline strings
            if val_str.startswith('"""') or val_str.startswith("'''"):
                quote = val_str[:3]
                if val_str.count(quote) >= 2:
                    pass  # single line
                else:
                    while i < len(lines) and quote not in lines[i]:
                        val_str += "\n" + lines[i]
                        i += 1
                    if i < len(lines):
                        val_str += "\n" + lines[i]
                        i += 1
            value = _parse_toml_value(val_str)
            section = (
                _get_section(result, current_section) if current_section else result
            )
            if isinstance(section, list):
                section[-1][key] = value
            else:
                section[key] = value
    return result


def _ensure_section(d: Dict[str, Any], keys: List[str]) -> Dict[str, Any]:
    current = d
    for k in keys:
        if k not in current:
            current[k] = {}
        val = current[k]
        if isinstance(val, list):
            current = val[-1]
        else:
            current = val
    return current


def _get_section(d: Dict[str, Any], keys: Optional[List[str]]) -> Any:
    if not keys:
        return d
    current: Any = d
    for k in keys:
        if isinstance(current, dict):
            if k not in current:
                current[k] = {}
            current = current[k]
        elif isinstance(current, list):
            current = current[-1].get(k, {})
    return current


def _parse_toml_value(s: str) -> Any:
    s = s.strip()
    if s.startswith('"') and s.endswith('"'):
        return s[1:-1].replace('\\"', '"')
    if s.startswith("'") and s.endswith("'"):
        return s[1:-1]
    if s.startswith('"""') and s.endswith('"""'):
        return s[3:-3]
    if s.startswith("'''") and s.endswith("'''"):
        return s[3:-3]
    if s == "true":
        return True
    if s == "false":
        return False
    if s.startswith("["):
        return _parse_toml_array(s)
    if s.startswith("{"):
        return _parse_toml_inline_table(s)
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_toml_array(s: str) -> List[Any]:
    s = s.strip()
    if s == "[]":
        return []
    inner = s[1:-1].strip()
    items: List[Any] = []
    current = ""
    depth = 0
    in_str = False
    str_char = ""
    for ch in inner:
        if in_str:
            current += ch
            if ch == str_char:
                in_str = False
            continue
        if ch in ('"', "'"):
            in_str = True
            str_char = ch
            current += ch
        elif ch == "[":
            depth += 1
            current += ch
        elif ch == "]":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            val = current.strip()
            if val:
                items.append(_parse_toml_value(val))
            current = ""
        else:
            current += ch
    val = current.strip()
    if val:
        items.append(_parse_toml_value(val))
    return items


def _parse_toml_inline_table(s: str) -> Dict[str, Any]:
    s = s.strip()
    if s == "{}":
        return {}
    inner = s[1:-1].strip()
    result: Dict[str, Any] = {}
    for part in inner.split(","):
        part = part.strip()
        if "=" in part:
            k, v = part.split("=", 1)
            result[k.strip()] = _parse_toml_value(v.strip())
    return result


# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------


@dataclass
class ToolCandidate:
    command: str
    kind: str  # lint/test/build/format/typecheck
    priority: str
    source: str
    language: str

    def priority_num(self) -> int:
        return PRIORITY_ORDER.get(self.priority, 99)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "command": self.command,
            "priority": self.priority,
            "source": self.source,
            "language": self.language,
        }


@dataclass
class ScanCandidate:
    command: str
    source: str
    label: str
    kind: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Language & Package Manager Detection
# ---------------------------------------------------------------------------


def detect_languages(root: Path, tree: Set[str]) -> List[str]:
    langs: List[str] = []
    if tree_has(tree, "package.json"):
        langs.append("node")
    if (
        tree_has(tree, "pyproject.toml")
        or tree_has(tree, "setup.py")
        or tree_has(tree, "requirements.txt")
    ):
        langs.append("python")
    if tree_has(tree, "Cargo.toml"):
        langs.append("rust")
    if tree_has(tree, "go.mod"):
        langs.append("go")
    if (
        tree_has(tree, "pom.xml")
        or tree_has(tree, "build.gradle")
        or tree_has(tree, "build.gradle.kts")
    ):
        langs.append("java_kotlin")
    if any(p.endswith(".csproj") for p in tree) or any(
        p.endswith(".sln") for p in tree
    ):
        langs.append("dotnet")
    return langs


def detect_node_pkg_mgr(tree: Set[str]) -> str:
    if tree_has(tree, "pnpm-lock.yaml"):
        return "pnpm"
    if tree_has(tree, "yarn.lock"):
        return "yarn"
    if tree_has(tree, "bun.lockb") or tree_has(tree, "bun.lock"):
        return "bun"
    return "npm"


def detect_python_pkg_mgr(tree: Set[str]) -> str:
    if tree_has(tree, "poetry.lock"):
        return "poetry"
    if tree_has(tree, "pdm.lock"):
        return "pdm"
    if tree_has(tree, "uv.lock"):
        return "uv"
    return "pip"


def detect_package_managers(langs: List[str], tree: Set[str]) -> Dict[str, str]:
    mgrs: Dict[str, str] = {}
    if "node" in langs:
        mgrs["node"] = detect_node_pkg_mgr(tree)
    if "python" in langs:
        mgrs["python"] = detect_python_pkg_mgr(tree)
    return mgrs


def detect_monorepo(root: Path, tree: Set[str]) -> Optional[Dict[str, Any]]:
    if tree_has(tree, "nx.json"):
        projects = []
        for p in tree:
            if p.endswith("project.json") and p.count("/") <= 4:
                proj_dir = os.path.dirname(p)
                if proj_dir:
                    projects.append(proj_dir)
        return {"framework": "nx", "projects": sorted(projects)}
    if tree_has(tree, "turbo.json"):
        return {"framework": "turbo", "projects": []}
    if any(
        p == ".moon/workspace.yml" or p.startswith(".moon/workspace.yml") for p in tree
    ):
        return {"framework": "moon", "projects": []}
    return None


# ---------------------------------------------------------------------------
# Per-Language Probes
# ---------------------------------------------------------------------------


def node_exec_command(pkg_mgr: str) -> str:
    if pkg_mgr == "pnpm":
        return "pnpm exec"
    if pkg_mgr == "yarn":
        return "yarn"
    if pkg_mgr == "bun":
        return "bun x"
    return "npx"


def probe_node(root: Path, tree: Set[str], pkg_mgr: str) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    pkg_path = root / "package.json"
    content = read_text(pkg_path)
    if not content:
        return candidates
    try:
        pkg = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return candidates

    scripts = pkg.get("scripts", {})
    exec_cmd = node_exec_command(pkg_mgr)

    # Explicit scripts
    script_map = {
        "lint": "lint",
        "test": "test",
        "build": "build",
        "format": "format",
        "typecheck": "typecheck",
        "type-check": "typecheck",
    }
    for script_name, kind in script_map.items():
        if script_name in scripts:
            run_cmd = (
                f"{pkg_mgr} run {script_name}"
                if pkg_mgr != "npm"
                else f"npm run {script_name}"
            )
            candidates.append(
                ToolCandidate(
                    command=run_cmd,
                    kind=kind,
                    priority="explicit_script",
                    source=f"package.json scripts.{script_name}",
                    language="node",
                )
            )

    # Dependencies
    deps = set()
    for dep_key in ("dependencies", "devDependencies"):
        deps.update(pkg.get(dep_key, {}).keys())

    dep_probes = [
        ("eslint", [("lint", f"{exec_cmd} eslint .")]),
        (
            "@biomejs/biome",
            [
                ("lint", f"{exec_cmd} biome check ."),
                ("format", f"{exec_cmd} biome format ."),
            ],
        ),
        (
            "biome",
            [
                ("lint", f"{exec_cmd} biome check ."),
                ("format", f"{exec_cmd} biome format ."),
            ],
        ),
        ("prettier", [("format", f"{exec_cmd} prettier --check .")]),
        ("typescript", [("typecheck", f"{exec_cmd} tsc --noEmit")]),
        ("vitest", [("test", f"{exec_cmd} vitest run")]),
        ("jest", [("test", f"{exec_cmd} jest")]),
    ]
    for dep_name, mappings in dep_probes:
        if dep_name in deps:
            for kind, cmd in mappings:
                candidates.append(
                    ToolCandidate(
                        command=cmd,
                        kind=kind,
                        priority="dependency_fallback",
                        source=f"package.json dependency {dep_name}",
                        language="node",
                    )
                )

    # Framework targets
    if "nx" in deps and tree_has(tree, "nx.json"):
        for p in tree:
            if p.endswith("project.json") and p.count("/") <= 4:
                proj_content = read_text(root / p)
                if proj_content:
                    try:
                        proj = json.loads(proj_content)
                        targets = proj.get("targets", {})
                        for target_name in targets:
                            kind_map = {
                                "lint": "lint",
                                "test": "test",
                                "build": "build",
                                "format": "format",
                                "typecheck": "typecheck",
                            }
                            if target_name in kind_map:
                                proj_name = proj.get("name", os.path.dirname(p))
                                candidates.append(
                                    ToolCandidate(
                                        command=f"nx run {proj_name}:{target_name}",
                                        kind=kind_map[target_name],
                                        priority="framework_target",
                                        source=f"{p} targets.{target_name}",
                                        language="node",
                                    )
                                )
                    except (json.JSONDecodeError, ValueError):
                        pass

    if "turbo" in deps and tree_has(tree, "turbo.json"):
        for kind in ["lint", "test", "build", "format", "typecheck"]:
            candidates.append(
                ToolCandidate(
                    command=f"turbo run {kind}",
                    kind=kind,
                    priority="framework_target",
                    source="turbo.json",
                    language="node",
                )
            )

    if "@moonrepo/cli" in deps or "moon" in deps:
        for kind in ["lint", "test", "build", "format", "typecheck"]:
            candidates.append(
                ToolCandidate(
                    command=f"moon run {kind}",
                    kind=kind,
                    priority="framework_target",
                    source="moon workspace",
                    language="node",
                )
            )

    return candidates


def probe_python(root: Path, tree: Set[str], pkg_mgr: str) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    toml_path = root / "pyproject.toml"
    toml_data: Dict[str, Any] = {}
    if tree_has(tree, "pyproject.toml"):
        content = read_text(toml_path)
        if content:
            try:
                toml_data = parse_toml(content)
            except Exception:
                pass

    tool = toml_data.get("tool", {})

    # Tool sections
    if "ruff" in tool:
        candidates.append(
            ToolCandidate(
                "ruff check .",
                "lint",
                "dependency_fallback",
                "pyproject.toml [tool.ruff]",
                "python",
            )
        )
        candidates.append(
            ToolCandidate(
                "ruff format .",
                "format",
                "dependency_fallback",
                "pyproject.toml [tool.ruff]",
                "python",
            )
        )
    if "flake8" in tool:
        candidates.append(
            ToolCandidate(
                "flake8",
                "lint",
                "dependency_fallback",
                "pyproject.toml [tool.flake8]",
                "python",
            )
        )
    if "pytest" in tool or "pytest.ini_options" in tool:
        candidates.append(
            ToolCandidate(
                "pytest",
                "test",
                "dependency_fallback",
                "pyproject.toml [tool.pytest]",
                "python",
            )
        )
    if "mypy" in tool:
        candidates.append(
            ToolCandidate(
                "mypy .",
                "typecheck",
                "dependency_fallback",
                "pyproject.toml [tool.mypy]",
                "python",
            )
        )
    if "black" in tool:
        candidates.append(
            ToolCandidate(
                "black .",
                "format",
                "dependency_fallback",
                "pyproject.toml [tool.black]",
                "python",
            )
        )
    if "pyright" in tool or "basedpyright" in tool:
        candidates.append(
            ToolCandidate(
                "pyright",
                "typecheck",
                "dependency_fallback",
                "pyproject.toml [tool.pyright]",
                "python",
            )
        )

    # Project scripts
    project = toml_data.get("project", {})
    project_scripts = project.get("scripts", {})
    for script_name, script_val in project_scripts.items():
        lower = script_name.lower()
        for keyword, kind in [
            ("lint", "lint"),
            ("test", "test"),
            ("format", "format"),
            ("build", "build"),
        ]:
            if keyword in lower:
                candidates.append(
                    ToolCandidate(
                        script_name,
                        kind,
                        "explicit_script",
                        f"pyproject.toml [project.scripts].{script_name}",
                        "python",
                    )
                )
                break

    # Check requirements.txt for deps
    if tree_has(tree, "requirements.txt"):
        req_content = read_text(root / "requirements.txt")
        if req_content:
            req_lower = req_content.lower()
            if "ruff" in req_lower and "ruff" not in tool:
                candidates.append(
                    ToolCandidate(
                        "ruff check .",
                        "lint",
                        "dependency_fallback",
                        "requirements.txt ruff",
                        "python",
                    )
                )
                candidates.append(
                    ToolCandidate(
                        "ruff format .",
                        "format",
                        "dependency_fallback",
                        "requirements.txt ruff",
                        "python",
                    )
                )
            if "pytest" in req_lower and "pytest" not in tool:
                candidates.append(
                    ToolCandidate(
                        "pytest",
                        "test",
                        "dependency_fallback",
                        "requirements.txt pytest",
                        "python",
                    )
                )
            if "mypy" in req_lower and "mypy" not in tool:
                candidates.append(
                    ToolCandidate(
                        "mypy .",
                        "typecheck",
                        "dependency_fallback",
                        "requirements.txt mypy",
                        "python",
                    )
                )

    # Build
    build_system = toml_data.get("build-system", {})
    if build_system:
        candidates.append(
            ToolCandidate(
                "python -m build",
                "build",
                "language_default",
                "pyproject.toml [build-system]",
                "python",
            )
        )

    return candidates


def probe_rust(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    return [
        ToolCandidate("cargo clippy", "lint", "language_default", "Cargo.toml", "rust"),
        ToolCandidate("cargo test", "test", "language_default", "Cargo.toml", "rust"),
        ToolCandidate("cargo build", "build", "language_default", "Cargo.toml", "rust"),
        ToolCandidate(
            "cargo fmt --check", "format", "language_default", "Cargo.toml", "rust"
        ),
        ToolCandidate(
            "cargo check", "typecheck", "language_default", "Cargo.toml", "rust"
        ),
    ]


def probe_go(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    if tree_has(tree, ".golangci.yml") or tree_has(tree, ".golangci.yaml"):
        config_file = (
            ".golangci.yml" if tree_has(tree, ".golangci.yml") else ".golangci.yaml"
        )
        candidates.append(
            ToolCandidate("golangci-lint run", "lint", "config_file", config_file, "go")
        )
    candidates.append(
        ToolCandidate("go test ./...", "test", "language_default", "go.mod", "go")
    )
    candidates.append(
        ToolCandidate("go build ./...", "build", "language_default", "go.mod", "go")
    )
    candidates.append(
        ToolCandidate("gofmt -l .", "format", "language_default", "go.mod", "go")
    )
    return candidates


def probe_java_kotlin(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    is_maven = tree_has(tree, "pom.xml")
    is_gradle = tree_has(tree, "build.gradle") or tree_has(tree, "build.gradle.kts")

    if is_maven:
        mvn = "./mvnw" if tree_has(tree, "mvnw") else "mvn"
        candidates.append(
            ToolCandidate(
                f"{mvn} verify", "test", "language_default", "pom.xml", "java_kotlin"
            )
        )
        candidates.append(
            ToolCandidate(
                f"{mvn} package", "build", "language_default", "pom.xml", "java_kotlin"
            )
        )
    if is_gradle:
        gradle = "./gradlew" if tree_has(tree, "gradlew") else "gradle"
        candidates.append(
            ToolCandidate(
                f"{gradle} test",
                "test",
                "language_default",
                "build.gradle",
                "java_kotlin",
            )
        )
        candidates.append(
            ToolCandidate(
                f"{gradle} build",
                "build",
                "language_default",
                "build.gradle",
                "java_kotlin",
            )
        )

    return candidates


def probe_dotnet(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    return [
        ToolCandidate("dotnet test", "test", "language_default", "*.csproj", "dotnet"),
        ToolCandidate(
            "dotnet build", "build", "language_default", "*.csproj", "dotnet"
        ),
        ToolCandidate(
            "dotnet format --verify-no-changes",
            "format",
            "language_default",
            "*.csproj",
            "dotnet",
        ),
    ]


def probe_justfile(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    if not tree_has(tree, "Justfile") and not tree_has(tree, "justfile"):
        return candidates
    just_path = root / "Justfile" if tree_has(tree, "Justfile") else root / "justfile"
    content = read_text(just_path)
    if not content:
        return candidates
    kind_keywords = ["lint", "test", "build", "format", "typecheck", "check"]
    for line in content.split("\n"):
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):", line)
        if m:
            recipe = m.group(1)
            recipe_lower = recipe.lower()
            for kw in kind_keywords:
                if kw in recipe_lower:
                    kind = "typecheck" if kw == "check" else kw
                    candidates.append(
                        ToolCandidate(
                            f"just {recipe}",
                            kind,
                            "config_file",
                            f"Justfile recipe {recipe}",
                            "unknown",
                        )
                    )
                    break
    return candidates


def probe_makefile(root: Path, tree: Set[str]) -> List[ToolCandidate]:
    candidates: List[ToolCandidate] = []
    if not tree_has(tree, "Makefile") and not tree_has(tree, "makefile"):
        return candidates
    make_path = root / "Makefile" if tree_has(tree, "Makefile") else root / "makefile"
    content = read_text(make_path)
    if not content:
        return candidates
    kind_keywords = ["lint", "test", "build", "format", "typecheck", "check"]
    for line in content.split("\n"):
        m = re.match(r"^([a-zA-Z_][a-zA-Z0-9_-]*):", line)
        if m:
            target = m.group(1)
            target_lower = target.lower()
            for kw in kind_keywords:
                if kw in target_lower:
                    kind = "typecheck" if kw == "check" else kw
                    candidates.append(
                        ToolCandidate(
                            f"make {target}",
                            kind,
                            "config_file",
                            f"Makefile target {target}",
                            "unknown",
                        )
                    )
                    break
    return candidates


# ---------------------------------------------------------------------------
# Command Selection
# ---------------------------------------------------------------------------


def select_best_commands(
    candidates: List[ToolCandidate],
) -> Dict[str, List[ToolCandidate]]:
    """Group by kind, for each kind pick all at highest (lowest numeric) priority."""
    groups = group_candidates_by_kind(candidates)

    selected: Dict[str, List[ToolCandidate]] = {}
    for kind, group in groups.items():
        min_priority = min(c.priority_num() for c in group)
        selected[kind] = [c for c in group if c.priority_num() == min_priority]
    return selected


def group_candidates_by_kind(
    candidates: List[ToolCandidate],
) -> Dict[str, List[ToolCandidate]]:
    """Group all discovered candidates by command kind."""
    groups: Dict[str, List[ToolCandidate]] = {}
    for c in candidates:
        groups.setdefault(c.kind, []).append(c)
    return groups


# ---------------------------------------------------------------------------
# Additional Scan Discovery
# ---------------------------------------------------------------------------


def discover_additional_scans(
    root: Path, tree: Set[str]
) -> Dict[str, List[Dict[str, Any]]]:
    scans: Dict[str, List[Dict[str, Any]]] = {
        "security": [],
        "boundary": [],
        "duplication": [],
        "dead_code": [],
        "api_contract": [],
        "infra": [],
        "container": [],
        "coverage": [],
    }

    # From package.json
    pkg_content = (
        read_text(root / "package.json") if tree_has(tree, "package.json") else None
    )
    pkg: Dict[str, Any] = {}
    if pkg_content:
        try:
            pkg = json.loads(pkg_content)
        except (json.JSONDecodeError, ValueError):
            pass

    scripts = pkg.get("scripts", {})
    deps = set()
    for dk in ("dependencies", "devDependencies"):
        deps.update(pkg.get(dk, {}).keys())

    # Boundary
    for s in ("check:project-tags", "check:generated-boundaries"):
        if s in scripts:
            scans["boundary"].append(
                ScanCandidate(
                    scripts[s], f"package.json scripts.{s}", s, "boundary"
                ).to_dict()
            )

    # Security
    if "audit" in scripts:
        scans["security"].append(
            ScanCandidate(
                scripts["audit"], "package.json scripts.audit", "audit", "security"
            ).to_dict()
        )
    if "semgrep" in deps:
        scans["security"].append(
            ScanCandidate(
                "semgrep scan", "package.json dependency semgrep", "semgrep", "security"
            ).to_dict()
        )
    for s_name, s_val in scripts.items():
        if "semgrep" in s_name.lower() or "semgrep" in str(s_val).lower():
            scans["security"].append(
                ScanCandidate(
                    s_val, f"package.json scripts.{s_name}", "semgrep", "security"
                ).to_dict()
            )
            break

    # Duplication
    for s_name in scripts:
        if "duplication" in s_name.lower():
            scans["duplication"].append(
                ScanCandidate(
                    scripts[s_name],
                    f"package.json scripts.{s_name}",
                    s_name,
                    "duplication",
                ).to_dict()
            )
    if "jscpd" in deps:
        scans["duplication"].append(
            ScanCandidate(
                "jscpd", "package.json dependency jscpd", "jscpd", "duplication"
            ).to_dict()
        )

    # Dead code
    if "knip" in deps:
        scans["dead_code"].append(
            ScanCandidate(
                "knip", "package.json dependency knip", "knip", "dead_code"
            ).to_dict()
        )
    for s_name in scripts:
        if "knip" in s_name.lower():
            scans["dead_code"].append(
                ScanCandidate(
                    scripts[s_name],
                    f"package.json scripts.{s_name}",
                    "knip",
                    "dead_code",
                ).to_dict()
            )
            break

    # API contract
    for s_name in scripts:
        if "validate:api" in s_name.lower() or "schemathesis" in s_name.lower():
            scans["api_contract"].append(
                ScanCandidate(
                    scripts[s_name],
                    f"package.json scripts.{s_name}",
                    s_name,
                    "api_contract",
                ).to_dict()
            )
    if "schemathesis" in deps:
        scans["api_contract"].append(
            ScanCandidate(
                "schemathesis",
                "package.json dependency schemathesis",
                "schemathesis",
                "api_contract",
            ).to_dict()
        )

    # Infra
    for s_name in scripts:
        if "infra:validate" in s_name.lower():
            scans["infra"].append(
                ScanCandidate(
                    scripts[s_name], f"package.json scripts.{s_name}", s_name, "infra"
                ).to_dict()
            )

    # Container
    for s_name in scripts:
        if "lint:docker" in s_name.lower():
            scans["container"].append(
                ScanCandidate(
                    scripts[s_name],
                    f"package.json scripts.{s_name}",
                    s_name,
                    "container",
                ).to_dict()
            )

    # Coverage
    for s_name in scripts:
        if "coverage" in s_name.lower():
            scans["coverage"].append(
                ScanCandidate(
                    scripts[s_name],
                    f"package.json scripts.{s_name}",
                    s_name,
                    "coverage",
                ).to_dict()
            )

    # From config files
    if tree_has(tree, ".semgrep.yml") or tree_has_dir(tree, ".semgrep"):
        src = ".semgrep.yml" if tree_has(tree, ".semgrep.yml") else ".semgrep/"
        scans["security"].append(
            ScanCandidate("semgrep scan", src, "semgrep", "security").to_dict()
        )
    if tree_has(tree, "bandit.yaml") or tree_has(tree, ".bandit"):
        scans["security"].append(
            ScanCandidate(
                "bandit -r .", "bandit config", "bandit", "security"
            ).to_dict()
        )
    if tree_has(tree, ".spotbugs.xml"):
        scans["security"].append(
            ScanCandidate("spotbugs", ".spotbugs.xml", "spotbugs", "security").to_dict()
        )

    # Dependency audit from config
    if tree_has(tree, ".github/dependabot.yml"):
        scans.setdefault("dependency_audit", []).append(
            ScanCandidate(
                "dependabot", ".github/dependabot.yml", "dependabot", "dependency_audit"
            ).to_dict()
        )
    for reno in ("renovate.json", ".renovate.json", "renovate.json5"):
        if tree_has(tree, reno):
            scans.setdefault("dependency_audit", []).append(
                ScanCandidate(
                    "renovate", reno, "renovate", "dependency_audit"
                ).to_dict()
            )
            break

    # Remove empty categories
    return {k: v for k, v in scans.items() if v}


# ---------------------------------------------------------------------------
# CI Workflow Scanning
# ---------------------------------------------------------------------------


def make_source(
    file: str, source_type: str, detail: Optional[str] = None
) -> Dict[str, str]:
    source = {"file": file, "type": source_type}
    if detail:
        source["detail"] = detail
    return source


def parse_source_reference(source: str, source_type: str) -> Dict[str, str]:
    special_sources = {
        "moon workspace": (".moon/workspace.yml", "workspace"),
        "bandit config": ("bandit.yaml", "config"),
    }
    if source in special_sources:
        file, detail = special_sources[source]
        return make_source(file, source_type, detail)

    source_parts = source.split(" ", 1)
    file = source_parts[0]
    detail = source_parts[1] if len(source_parts) > 1 else None
    return make_source(file, source_type, detail)


def candidate_to_source(candidate: ToolCandidate) -> Dict[str, str]:
    return parse_source_reference(
        candidate.source,
        SOURCE_TYPE_BY_PRIORITY.get(candidate.priority, "detected"),
    )


def scan_to_source(
    scan: Dict[str, Any], source_type: str = "scan_config"
) -> Dict[str, str]:
    source = parse_source_reference(scan["source"], source_type)
    if scan.get("label"):
        existing_detail = source.get("detail")
        label_detail = f"label={scan['label']}"
        source["detail"] = (
            f"{existing_detail}; {label_detail}" if existing_detail else label_detail
        )
    return source


def advisory_patterns(text: str) -> List[str]:
    patterns = [
        ("continue-on-error: true", "continue-on-error: true"),
        ("continue_on_error: true", "continue_on_error: true"),
        ("|| true", "|| true"),
        ("--exit-zero", "--exit-zero"),
        ("<failonviolation>false</failonviolation>", "failOnViolation=false"),
        ("<failonviolation>false", "failOnViolation=false"),
        ("allow_failure: true", "allow_failure: true"),
    ]
    return [label for needle, label in patterns if needle in text]


def read_ci_workflows(root: Path, tree: Set[str]) -> List[Dict[str, str]]:
    """Load GitHub Actions and Jenkins workflow files with their paths."""
    workflow_files = [
        p
        for p in tree
        if p.startswith(".github/workflows/")
        and (p.endswith(".yml") or p.endswith(".yaml"))
    ]
    contents: List[Dict[str, str]] = []
    for wf in workflow_files:
        content = read_text(root / wf)
        if content:
            contents.append({"file": wf, "content": content})
    # Also check Jenkinsfile
    for jf in ["Jenkinsfile", "jenkinsfile", "Jenkinsfile.groovy"]:
        if tree_has(tree, jf):
            content = read_text(root / jf)
            if content:
                contents.append({"file": jf, "content": content})
    return contents


def match_ci_sources(
    ci_workflows: List[Dict[str, str]], keywords: List[str]
) -> Dict[str, Any]:
    sources: List[Dict[str, str]] = []
    ci_enforced = False
    advisory_signals: List[str] = []

    for workflow in ci_workflows:
        content_lower = workflow["content"].lower()
        matched_keywords = [kw for kw in keywords if kw in content_lower]
        if not matched_keywords:
            continue

        advisory_hits = advisory_patterns(content_lower)
        detail_parts = [f"keywords={','.join(sorted(set(matched_keywords)))}"]
        if advisory_hits:
            detail_parts.append(f"advisory={','.join(sorted(set(advisory_hits)))}")
            advisory_signals.extend(
                f"{workflow['file']}: {advisory_hit}" for advisory_hit in advisory_hits
            )
        else:
            ci_enforced = True

        sources.append(
            make_source(
                workflow["file"],
                "ci_enforcement",
                "; ".join(detail_parts),
            )
        )

    return {
        "sources": sources,
        "ci_enforced": ci_enforced,
        "advisory_signals": advisory_signals,
    }


# ---------------------------------------------------------------------------
# Category Signal Detection
# ---------------------------------------------------------------------------


def _spec_artifact_roles(relative_path: str) -> Set[str]:
    """Map each supported system's artifacts to unified maturity roles."""
    normalized = relative_path.replace("\\", "/").lower()
    name = Path(relative_path).name.lower()
    roles: Set[str] = set()
    if name in {
        "proposal.md",
        "requirements.md",
        "requirement.md",
        "prd.md",
        "spec.md",
    } or name.endswith("-spec.md"):
        roles.add("intent")
    if name in {
        "design.md",
        "plan.md",
        "architecture.md",
        "roadmap.md",
    } or name.endswith("-plan.md"):
        roles.add("plan")
    if (
        name in {"tasks.md", "task.md", "checklist.md"}
        or "tasks" in name
        or "checklist" in name
    ):
        roles.add("tasks")

    # GSD phase plans combine the phase goal, implementation approach, and
    # executable task breakdown in one PLAN artifact. VERIFICATION provides the
    # separate completion marker rather than another planning role.
    if (
        normalized.startswith(".planning/phases/")
        or normalized.startswith(".planning/milestones/")
    ) and name.endswith("-plan.md"):
        roles.update({"intent", "plan", "tasks"})

    # BMAD epics are self-contained planning work items: an epic document
    # carries the intent plus its story-level plan and task breakdown.
    if normalized.startswith("_bmad-output/planning-artifacts/epics/"):
        epic_child = normalized[len("_bmad-output/planning-artifacts/epics/") :].split(
            "/", 1
        )[0]
        if re.match(r"^epic[-_ ]?\d", epic_child) and name.endswith(".md"):
            roles.update({"intent", "plan", "tasks"})

    return roles


def _has_substantive_spec_content(root: Path, relative_path: str) -> bool:
    content = read_text(root / relative_path)
    if not content:
        return False
    words = re.findall(r"[A-Za-z0-9][A-Za-z0-9_-]*", content)
    return len(words) >= 4


def _work_item_has_complete_artifacts(root: Path, artifact_paths: Set[str]) -> bool:
    roles: Set[str] = set()
    for relative_path in artifact_paths:
        if _has_substantive_spec_content(root, relative_path):
            roles.update(_spec_artifact_roles(relative_path))
    return {"intent", "plan", "tasks"}.issubset(roles)


def _work_item_has_completion_marker(root: Path, artifact_paths: Set[str]) -> bool:
    task_lines: List[str] = []
    for relative_path in artifact_paths:
        content = read_text(root / relative_path)
        if not content:
            continue
        lowered = content.lower()
        if re.search(
            r"(?m)^\s*status\s*:\s*(?:complete|completed|done|passed)\s*$", lowered
        ):
            return True
        if "tasks" in _spec_artifact_roles(relative_path):
            task_lines.extend(
                line.strip()
                for line in content.splitlines()
                if re.match(r"^\s*[-*]\s+\[[ xX]\]", line)
            )
    return bool(task_lines) and all(
        re.match(r"^[-*]\s+\[[xX]\]", line) for line in task_lines
    )


def _bmad_completion_evidence(
    root: Path,
    tree: Set[str],
    work_item_ids: Set[str],
) -> Tuple[Set[str], Set[str]]:
    """Return completed BMAD epic ids and their sprint-status evidence paths."""
    bmad_item_ids = {
        item_id
        for item_id in work_item_ids
        if "_bmad-output/planning-artifacts/epics/" in item_id
    }
    if not bmad_item_ids:
        return set(), set()
    status_paths = {
        path
        for path in tree
        if path == "sprint-status.yaml" or path.endswith("/sprint-status.yaml")
    }
    statuses: Dict[str, str] = {}
    for status_path in status_paths:
        in_development_status = False
        for raw_line in (read_text(root / status_path) or "").splitlines():
            if re.match(r"^\s*development_status\s*:\s*$", raw_line):
                in_development_status = True
                continue
            if not in_development_status:
                continue
            if raw_line.strip() and not raw_line.startswith((" ", "\t")):
                break
            match = re.match(r"^\s+([^:#][^:]*?)\s*:\s*([^#]+?)\s*$", raw_line)
            if match:
                key = _yaml_scalar(match.group(1)).lower()
                value = _yaml_scalar(match.group(2)).lower()
                statuses[key] = value

    terminal = {"complete", "completed", "done", "passed"}
    completed: Set[str] = set()
    for item_id in bmad_item_ids:
        match = re.search(r"(?:^|/)epic[-_ ]?(\d+)", item_id, re.IGNORECASE)
        if not match:
            continue
        epic_number = match.group(1)
        epic_key = f"epic-{epic_number}"
        if statuses.get(epic_key) in terminal:
            completed.add(item_id)
            continue
        story_statuses = [
            value
            for key, value in statuses.items()
            if re.match(rf"^{re.escape(epic_number)}-\d", key)
        ]
        if story_statuses and all(value in terminal for value in story_statuses):
            completed.add(item_id)
    return completed, status_paths


def _has_recent_spec_activity(
    root: Path,
    artifact_paths: Set[str],
    now: Optional[datetime] = None,
) -> bool:
    """Return whether spec or workflow files show activity in the scoring window."""
    threshold = (now or datetime.now(timezone.utc)) - timedelta(
        days=RECENT_SPEC_ACTIVITY_DAYS
    )
    for relative_path in artifact_paths:
        for raw_date in re.findall(r"\b20\d{2}-\d{2}-\d{2}\b", relative_path):
            try:
                if (
                    datetime.strptime(raw_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                    >= threshold
                ):
                    return True
            except ValueError:
                continue

    try:
        completed = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "log",
                "-1",
                "--format=%ct",
                "--",
                *sorted(artifact_paths),
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=15,
        )
        committed_timestamp = int(completed.stdout.strip())
    except (OSError, subprocess.SubprocessError, ValueError):
        committed_timestamp = None
    if committed_timestamp is not None:
        return datetime.fromtimestamp(committed_timestamp, tz=timezone.utc) >= threshold

    for relative_path in artifact_paths:
        try:
            modified = datetime.fromtimestamp(
                (root / relative_path).stat().st_mtime,
                tz=timezone.utc,
            )
        except OSError:
            continue
        if modified >= threshold:
            return True
    return False


def detect_cat1(
    root: Path,
    tree: Set[str],
    cli_validation_passed: Optional[bool] = None,
) -> Dict[str, Any]:
    """Cat 1: Spec-Driven"""
    signals: Dict[str, Any] = {}
    evidence: List[str] = []

    # Spec directories. All recognized spec-driven systems are treated as
    # equal signals -- no system is favored over another. `spec_system_dir`
    # is the tool-agnostic signal used for scoring. Different tools use
    # different roots: OpenSpec uses `openspec/`, SpecKit uses `.specify/`
    # (config/memory/templates) plus `specs/` (per-feature artifacts), BMAD
    # uses `_bmad/` + `_bmad-output/` (V6) or `.bmad-core/`/`bmad-core/`/
    # `.bmad-method/` (V4), GSD uses `.planning/` (STATE.md/ROADMAP.md/
    # config.json + phases/), and other workflows may use a bare `specs/`
    # directory. A bare `specs/` directory only counts when it holds real
    # planning artifacts (per-item subdirectories or planning docs); a `specs/`
    # that merely holds OpenAPI or test spec files does not qualify. A
    # `.planning/` directory only counts with GSD's fingerprint files.
    detected_spec_dirs: List[str] = []
    for name in (
        "openspec",
        ".specify",
        "_bmad",
        ".bmad-core",
        "bmad-core",
        ".bmad-method",
    ):
        if tree_has_dir(tree, name):
            detected_spec_dirs.append(name)
    if tree_has_dir(tree, "specs") and specs_dir_has_planning_artifacts(tree):
        detected_spec_dirs.append("specs")
    if tree_has_dir(tree, ".planning") and planning_dir_is_gsd(tree):
        detected_spec_dirs.append(".planning")
    signals["spec_dir_names"] = detected_spec_dirs
    signals["spec_system_dir"] = bool(detected_spec_dirs)
    for name in detected_spec_dirs:
        evidence.append(f"{name}/ directory found")

    # CLI deps. Recognize spec-driven CLIs across ecosystems without favoring
    # one tool: OpenSpec, BMAD, and GSD ship npm packages
    # (`@fission-ai/openspec`, `bmad-method`, `@opengsd/gsd-core`); SpecKit
    # ships a Python CLI (`specify-cli`, installed via uv/pipx and often pinned
    # in pyproject.toml or a requirements file).
    has_cli_dep = False
    pkg_content = (
        read_text(root / "package.json") if tree_has(tree, "package.json") else None
    )
    if pkg_content:
        try:
            pkg = json.loads(pkg_content)
            all_deps = set()
            for dk in ("dependencies", "devDependencies"):
                all_deps.update(pkg.get(dk, {}).keys())
            if (
                "@fission-ai/openspec" in all_deps
                or "@openspec/cli" in all_deps
                or "specify-cli" in all_deps
                or "bmad-method" in all_deps
                or "@opengsd/gsd-core" in all_deps
            ):
                has_cli_dep = True
                evidence.append("Spec CLI dependency found")
        except (json.JSONDecodeError, ValueError):
            pass
    if not has_cli_dep:
        for dep_file in ("pyproject.toml", "requirements.txt", "requirements-dev.txt"):
            if not tree_has(tree, dep_file):
                continue
            dep_content = read_text(root / dep_file)
            if dep_content and "specify-cli" in dep_content:
                has_cli_dep = True
                evidence.append(f"Spec CLI dependency found in {dep_file}")
                break
    signals["cli_dep"] = has_cli_dep

    apm_manifest = parse_apm_manifest(root, tree)

    # Workflow skills. Count repo-local skills whose name indicates a
    # spec-driven workflow, regardless of which spec system produced them.
    # Use a word-boundary match so unrelated names (e.g., "inspect") are not
    # counted.
    local_spec_skills = [
        path for name, path in find_local_skills(tree).items() if mentions_spec(name)
    ]
    apm_workflow_skills = [s for s in apm_manifest["skills"] if mentions_spec(s)]
    signals["workflow_skills"] = len(local_spec_skills) + len(apm_workflow_skills)
    if local_spec_skills:
        evidence.append(f"{len(local_spec_skills)} repo-local spec workflow skills")
    if apm_workflow_skills:
        evidence.append(
            f"{len(apm_workflow_skills)} remote spec workflow skills in apm.yml"
        )

    # Workflow commands
    opencode_commands = [
        p
        for p in tree
        if p.startswith(".opencode/command/") or p.startswith(".opencode/commands/")
    ]
    signals["workflow_commands"] = len(opencode_commands)
    if opencode_commands:
        evidence.append(f"{len(opencode_commands)} workflow commands")

    # GitHub prompts
    has_prompts = tree_has_dir(tree, ".github/prompts")
    signals["github_prompts"] = has_prompts
    if has_prompts:
        evidence.append(".github/prompts/ found")

    # CONTRIBUTING.md mentions. Word-boundary match so unrelated words (e.g.,
    # "especially") do not register as a spec-driven reference.
    contrib_content = (
        read_text(root / "CONTRIBUTING.md")
        if tree_has(tree, "CONTRIBUTING.md")
        else None
    )
    contrib_mentions_spec = bool(contrib_content) and mentions_spec(contrib_content)
    signals["contributing_mentions_spec"] = contrib_mentions_spec
    if contrib_mentions_spec:
        evidence.append("CONTRIBUTING.md mentions specs")

    # AGENTS.md mentions
    agents_content = (
        read_text(root / "AGENTS.md") if tree_has(tree, "AGENTS.md") else None
    )
    agents_mentions_spec = bool(agents_content) and mentions_spec(agents_content)
    signals["agents_mentions_spec"] = agents_mentions_spec
    if agents_mentions_spec:
        evidence.append("AGENTS.md mentions specs")
    workflow_instruction_paths = find_sdd_workflow_instruction_paths(root, tree)

    # Work-item lifecycle. Detect planned work items in a tool-agnostic way so
    # that no single spec system can reach a higher score than another.
    #   - OpenSpec stores work items under `openspec/changes/<item>/...` and
    #     moves completed work into `openspec/changes/archive/...`.
    #   - SpecKit stores per-feature work under `specs/<NNN>-<name>/...` and
    #     does not use an archive directory.
    #   - BMAD stores work items (epics/stories) under
    #     `_bmad-output/planning-artifacts/epics/...` and tracks status in
    #     `_bmad-output/implementation-artifacts/sprint-status.yaml`; it does
    #     not use an archive directory.
    #   - GSD stores phases under `.planning/phases/<NN-slug>/...` and relocates
    #     finished milestones to `.planning/milestones/v{X.Y}-phases/...`.
    # Completion is inferred from an archive-style directory when present or an
    # on-disk completion marker. Artifact completeness, recency, CLI health, and
    # workflow documentation are recorded separately so scoring can distinguish
    # an observable mature lifecycle from a merely populated spec directory.
    active_items: Set[str] = set()
    archived_items: Set[str] = set()
    work_item_files: Dict[str, Set[str]] = {}

    def record_work_item(item_id: str, relative_path: str, archived: bool) -> None:
        if relative_path.endswith("/"):
            return
        work_item_files.setdefault(item_id, set()).add(relative_path)
        if archived:
            archived_items.add(item_id)
        else:
            active_items.add(item_id)

    # OpenSpec-style: items under a `changes/` container, archived under
    # `changes/archive/`.
    for base in detected_spec_dirs:
        changes_prefix = f"{base}/changes/"
        archive_prefix = f"{base}/changes/archive/"
        for p in tree:
            if not p.startswith(changes_prefix):
                continue
            rest = p[len(changes_prefix) :]
            if "/" not in rest:
                continue
            if p.startswith(archive_prefix):
                archived = p[len(archive_prefix) :]
                if "/" in archived:
                    record_work_item(
                        f"{base}/changes/archive/{archived.split('/', 1)[0]}",
                        p,
                        archived=True,
                    )
            else:
                record_work_item(
                    f"{base}/changes/{rest.split('/', 1)[0]}",
                    p,
                    archived=False,
                )

    # SpecKit-style: feature directories directly under a top-level `specs/`
    # (e.g., `specs/001-create-taskify/`). Only applies when `specs/` is the
    # spec system root, not when it is OpenSpec's `openspec/specs/` capability
    # directory.
    if "specs" in detected_spec_dirs:
        for p in tree:
            if not p.startswith("specs/"):
                continue
            rest = p[len("specs/") :]
            if "/" not in rest:
                continue
            record_work_item(
                f"specs/{rest.split('/', 1)[0]}",
                p,
                archived=False,
            )

    # BMAD-style: epic/story files under the planning-artifacts epics folder.
    # Each epic file (or epic subdirectory) is one planned work item.
    bmad_epics_prefix = "_bmad-output/planning-artifacts/epics/"
    for p in tree:
        if not p.startswith(bmad_epics_prefix):
            continue
        rest = p[len(bmad_epics_prefix) :]
        if not rest:
            continue
        # Use the immediate child (epic file or epic subdirectory) as the id.
        record_work_item(
            f"{bmad_epics_prefix}{rest.split('/', 1)[0]}",
            p,
            archived=False,
        )

    # GSD-style: phase directories under `.planning/phases/<NN-slug>/`. Finished
    # milestones are relocated to `.planning/milestones/v{X.Y}-phases/<NN-slug>/`,
    # so those count as archived/completed work items.
    if ".planning" in detected_spec_dirs:
        gsd_phases_prefix = ".planning/phases/"
        gsd_milestones_prefix = ".planning/milestones/"
        for p in tree:
            if p.startswith(gsd_phases_prefix):
                rest = p[len(gsd_phases_prefix) :]
                if "/" in rest:
                    record_work_item(
                        f"{gsd_phases_prefix}{rest.split('/', 1)[0]}",
                        p,
                        archived=False,
                    )
            elif p.startswith(gsd_milestones_prefix):
                rest = p[len(gsd_milestones_prefix) :]
                # Path shape: <vX.Y-phases>/<NN-slug>/...  -> archived phase id.
                parts = rest.split("/")
                if len(parts) >= 3:
                    record_work_item(
                        f"{gsd_milestones_prefix}{parts[0]}/{parts[1]}",
                        p,
                        archived=True,
                    )

    complete_items = {
        item_id
        for item_id, artifact_paths in work_item_files.items()
        if _work_item_has_complete_artifacts(root, artifact_paths)
    }
    substantive_items = {
        item_id
        for item_id, artifact_paths in work_item_files.items()
        if any(
            _spec_artifact_roles(relative_path)
            and _has_substantive_spec_content(root, relative_path)
            for relative_path in artifact_paths
        )
    }
    completion_evidence_items = set(archived_items)
    completion_evidence_items.update(
        item_id
        for item_id, artifact_paths in work_item_files.items()
        if _work_item_has_completion_marker(root, artifact_paths)
    )
    bmad_completed_items, bmad_status_paths = _bmad_completion_evidence(
        root, tree, set(work_item_files)
    )
    completion_evidence_items.update(bmad_completed_items)
    completed_items = completion_evidence_items.intersection(complete_items)
    all_artifact_paths = {
        relative_path
        for artifact_paths in work_item_files.values()
        for relative_path in artifact_paths
    }
    all_artifact_paths.update(bmad_status_paths)
    activity_paths = set(all_artifact_paths)
    activity_paths.update(workflow_instruction_paths)
    signals["changes_count"] = len(active_items)
    signals["archived_count"] = len(archived_items)
    signals["work_items_count"] = len(active_items) + len(archived_items)
    signals["has_spec_activity"] = bool(active_items or archived_items)
    signals["substantive_work_items_count"] = len(substantive_items)
    signals["has_substantive_spec_activity"] = bool(substantive_items)
    signals["complete_work_items_count"] = len(complete_items)
    signals["completed_work_items_count"] = len(completed_items)
    signals["has_completed_cycle"] = bool(completed_items)
    signals["has_recent_spec_activity"] = _has_recent_spec_activity(
        root, activity_paths
    )
    signals["workflow_integration_paths"] = sorted(workflow_instruction_paths)
    signals["workflow_integration_documented"] = bool(workflow_instruction_paths)
    signals["cli_validation_available"] = cli_validation_passed is not None
    signals["cli_validation_passed"] = cli_validation_passed is True
    if active_items:
        evidence.append(f"{len(active_items)} active work items")
    if archived_items:
        evidence.append(f"{len(archived_items)} completed/archived work items")
    if substantive_items:
        evidence.append(f"{len(substantive_items)} substantive work items")
    if complete_items:
        evidence.append(f"{len(complete_items)} work items with complete artifacts")
    if signals["has_recent_spec_activity"]:
        evidence.append(
            f"Spec activity found within the past {RECENT_SPEC_ACTIVITY_DAYS} days"
        )
    if signals["workflow_integration_documented"]:
        evidence.append(
            "Spec workflow integration documented in "
            + ", ".join(signals["workflow_integration_paths"])
        )
    if cli_validation_passed is True:
        evidence.append("Spec CLI status/check validation passed")
    elif cli_validation_passed is False:
        evidence.append("Spec CLI status/check validation failed")

    return {"signals": signals, "evidence": evidence}


def _detect_enforcement_locus(
    kind: str,
    candidates_by_kind: Dict[str, List[ToolCandidate]],
    ci_workflows: List[Dict[str, str]],
    ci_keywords: List[str],
    pkg_scripts: Dict[str, Any],
    tree: Set[str],
) -> Dict[str, Any]:
    """Detect WHERE a check is enforced: local_script, precommit, validate_command, ci.

    Returns a dict with detected, ci_enforced, enforcement metadata, locus list,
    and structured sources.
    """
    detected = kind in candidates_by_kind
    ci_matches = match_ci_sources(ci_workflows, ci_keywords)
    ci_enforced = ci_matches["ci_enforced"]

    sources: List[Dict[str, str]] = []
    locus: List[str] = []
    enforced_anywhere = False
    advisory_signals = list(ci_matches["advisory_signals"])

    if detected:
        sources.extend(
            candidate_to_source(candidate) for candidate in candidates_by_kind[kind]
        )
        locus.append("local_script")

    # Check if wired into precommit
    has_precommit_config = tree_has(tree, ".pre-commit-config.yaml")
    has_husky = tree_has_dir(tree, ".husky")
    precommit_script_body = pkg_scripts.get("precommit", "")
    if isinstance(precommit_script_body, str) and kind in precommit_script_body.lower():
        locus.append("precommit")
        advisory_hits = advisory_patterns(precommit_script_body.lower())
        detail = f"scripts.precommit ({kind})"
        if advisory_hits:
            advisory_signals.extend(
                f"package.json scripts.precommit: {advisory_hit}"
                for advisory_hit in advisory_hits
            )
            detail = f"{detail}; advisory={','.join(sorted(set(advisory_hits)))}"
        else:
            enforced_anywhere = True
        sources.append(make_source("package.json", "script_entry", detail))
    elif has_husky or has_precommit_config:
        # If hooks exist, the kind is likely wired through them
        if detected:
            locus.append("precommit")
            enforced_anywhere = True
            if has_precommit_config:
                sources.append(
                    make_source(".pre-commit-config.yaml", "hook_config", kind)
                )
            if has_husky:
                sources.append(make_source(".husky/", "hook_config", kind))

    # Check if wired into validate/check command
    for script_name in ("validate", "check"):
        body = pkg_scripts.get(script_name, "")
        if isinstance(body, str) and kind in body.lower():
            locus.append("validate_command")
            advisory_hits = advisory_patterns(body.lower())
            detail = f"scripts.{script_name} ({kind})"
            if advisory_hits:
                advisory_signals.extend(
                    f"package.json scripts.{script_name}: {advisory_hit}"
                    for advisory_hit in advisory_hits
                )
                detail = f"{detail}; advisory={','.join(sorted(set(advisory_hits)))}"
            else:
                enforced_anywhere = True
            sources.append(make_source("package.json", "script_entry", detail))
            break

    if ci_matches["sources"]:
        sources.extend(ci_matches["sources"])
        locus.append("ci")
    if ci_enforced:
        enforced_anywhere = True

    enforcement_mode = "none"
    if advisory_signals and not enforced_anywhere:
        enforcement_mode = "advisory"
    elif enforced_anywhere:
        enforcement_mode = "enforced"

    return {
        "detected": detected,
        "ci_enforced": ci_enforced,
        "enforcement_mode": enforcement_mode,
        "advisory_signals": sorted(set(advisory_signals)),
        "locus": sorted(set(locus)),
        "sources": sources,
    }


def detect_cat2(
    root: Path,
    tree: Set[str],
    candidates_by_kind: Dict[str, List[ToolCandidate]],
    scans: Dict[str, List[Dict[str, Any]]],
) -> Dict[str, Any]:
    """Cat 2: Deterministic Checks"""
    ci_workflows = read_ci_workflows(root, tree)
    ci_lower = "\n".join(workflow["content"] for workflow in ci_workflows).lower()

    pkg_content = (
        read_text(root / "package.json") if tree_has(tree, "package.json") else None
    )
    pkg_scripts: Dict[str, Any] = {}
    if pkg_content:
        try:
            pkg_scripts = json.loads(pkg_content).get("scripts", {})
        except (json.JSONDecodeError, ValueError):
            pkg_scripts = {}

    signals: Dict[str, Any] = {}
    evidence: List[str] = []
    # Core checks with enforcement locus tracking
    signals["lint"] = _detect_enforcement_locus(
        "lint",
        candidates_by_kind,
        ci_workflows,
        ["eslint", "ruff", "flake8", "lint", "clippy", "golangci"],
        pkg_scripts,
        tree,
    )
    signals["typecheck"] = _detect_enforcement_locus(
        "typecheck",
        candidates_by_kind,
        ci_workflows,
        ["tsc", "mypy", "pyright", "typecheck", "type-check"],
        pkg_scripts,
        tree,
    )
    signals["test"] = _detect_enforcement_locus(
        "test",
        candidates_by_kind,
        ci_workflows,
        ["test", "pytest", "vitest", "jest", "cargo test", "go test"],
        pkg_scripts,
        tree,
    )
    signals["build"] = _detect_enforcement_locus(
        "build",
        candidates_by_kind,
        ci_workflows,
        ["build", "docker", "cargo build", "dotnet build"],
        pkg_scripts,
        tree,
    )

    # Lint strictness: check for --max-warnings=0 or equivalent
    lint_strict = False
    lint_strict_evidence: List[Dict[str, str]] = []
    # Check package.json lint script for --max-warnings=0
    lint_script_body = pkg_scripts.get("lint", "")
    if (
        isinstance(lint_script_body, str)
        and "--max-warnings" in lint_script_body
        and "=0" in lint_script_body
    ):
        lint_strict = True
        lint_strict_evidence.append(
            make_source(
                "package.json", "script_entry", "scripts.lint; --max-warnings=0"
            )
        )
    # Check CI content for --max-warnings=0
    if "--max-warnings" in ci_lower and "=0" in ci_lower:
        lint_strict = True
        for workflow in ci_workflows:
            workflow_lower = workflow["content"].lower()
            if "--max-warnings" in workflow_lower and "=0" in workflow_lower:
                lint_strict_evidence.append(
                    make_source(
                        workflow["file"],
                        "ci_enforcement",
                        "--max-warnings=0",
                    )
                )
    # Check .eslintrc* or eslint.config.* for error-only (shallow check)
    for eslint_conf in tree_glob(tree, "eslint.config.*") + tree_glob(
        tree, ".eslintrc*"
    ):
        content = read_text(root / eslint_conf)
        if content and "--max-warnings" in content and "0" in content:
            lint_strict = True
            lint_strict_evidence.append(
                make_source(eslint_conf, "config", "references max-warnings 0")
            )
    # Check for biome strict (biome uses "error" severity by default)
    if tree_has(tree, "biome.json") or tree_has(tree, "biome.jsonc"):
        lint_strict = True
        lint_strict_evidence.append(
            make_source(
                "biome.json" if tree_has(tree, "biome.json") else "biome.jsonc",
                "config",
                "error severity by default",
            )
        )
    signals["lint"]["strict"] = lint_strict
    signals["lint"]["strict_evidence"] = lint_strict_evidence

    # Test lanes
    test_lanes: List[str] = []
    for name in pkg_scripts.keys():
        lowered = name.lower()
        if lowered == "test" or lowered.startswith("test:"):
            test_lanes.append(name)
        elif "integration" in lowered or "e2e" in lowered:
            test_lanes.append(name)
    if (
        re.search(r"(:|\b)test:integration\b", ci_lower)
        or "integration tests" in ci_lower
    ):
        test_lanes.append("integration")
    if (
        re.search(r"(:|\b)e2e\b", ci_lower)
        or "playwright" in ci_lower
        or "frontend-e2e" in ci_lower
    ):
        test_lanes.append("e2e")
    for project_file in tree_glob(tree, "**/project.json")[:200]:
        content = read_text(root / project_file)
        if not content:
            continue
        lower = content.lower()
        if '"test:integration"' in lower or '"integration"' in lower:
            test_lanes.append("integration")
        if '"e2e"' in lower:
            test_lanes.append("e2e")
    has_integration_lane = any("integration" in lane.lower() for lane in test_lanes)
    has_e2e_lane = any("e2e" in lane.lower() for lane in test_lanes)
    signals["test"]["lanes"] = sorted(set(test_lanes))
    signals["test"]["has_integration_lane"] = has_integration_lane
    signals["test"]["has_e2e_lane"] = has_e2e_lane

    # Changed-line coverage detection
    coverage_signals: Dict[str, Any] = {
        "detected": False,
        "ci_enforced": False,
        "changed_line": False,
        "sources": [],
        "locus": [],
        "enforcement_mode": "none",
        "advisory_signals": [],
    }
    coverage_scripts = [name for name in pkg_scripts if "coverage" in name.lower()]
    if coverage_scripts:
        coverage_signals["detected"] = True
        coverage_signals["locus"].append("local_script")
        coverage_signals["sources"].extend(
            make_source("package.json", "script_entry", f"scripts.{script_name}")
            for script_name in coverage_scripts
        )
        # Check if it's changed-line coverage (diff-based)
        for cs in coverage_scripts:
            body = pkg_scripts.get(cs, "")
            if isinstance(body, str):
                lower_body = body.lower()
                if any(
                    kw in lower_body
                    for kw in [
                        "--changed",
                        "diff",
                        "new-code",
                        "changed-line",
                        "affected",
                    ]
                ):
                    coverage_signals["changed_line"] = True
                    coverage_signals["sources"].append(
                        make_source(
                            "package.json",
                            "script_entry",
                            f"scripts.{cs}; changed-line coverage",
                        )
                    )
    # Check if coverage:new or similar is in precommit/validate
    precommit_body = pkg_scripts.get("precommit", "")
    if isinstance(precommit_body, str) and "coverage" in precommit_body.lower():
        coverage_signals["locus"].append("precommit")
    for validate_key in ("validate", "check"):
        validate_body = pkg_scripts.get(validate_key, "")
        if isinstance(validate_body, str) and "coverage" in validate_body.lower():
            coverage_signals["locus"].append("validate_command")
            break
    coverage_ci_matches = match_ci_sources(
        ci_workflows, ["coverage", "codecov", "coveralls"]
    )
    if coverage_ci_matches["sources"]:
        coverage_signals["locus"].append("ci")
        coverage_signals["sources"].extend(coverage_ci_matches["sources"])
        coverage_signals["advisory_signals"] = coverage_ci_matches["advisory_signals"]
        if coverage_ci_matches["ci_enforced"]:
            coverage_signals["ci_enforced"] = True
    if coverage_signals["advisory_signals"] and not coverage_signals["ci_enforced"]:
        coverage_signals["enforcement_mode"] = "advisory"
    elif coverage_signals["ci_enforced"] or any(
        coverage_locus in coverage_signals["locus"]
        for coverage_locus in ["precommit", "validate_command"]
    ):
        coverage_signals["enforcement_mode"] = "enforced"
    coverage_signals["locus"] = sorted(set(coverage_signals["locus"]))
    signals["coverage"] = coverage_signals

    # SAST
    sast_detected = bool(scans.get("security"))
    sast_ci_matches = match_ci_sources(
        ci_workflows, ["semgrep", "bandit", "sast", "codeql", "spotbugs"]
    )
    sast_ci = sast_ci_matches["ci_enforced"]
    sast_locus = []
    if sast_detected:
        sast_locus.append("local_script")
    if sast_ci_matches["sources"]:
        sast_locus.append("ci")
    sast_enforcement_mode = "none"
    if sast_ci_matches["advisory_signals"] and not sast_ci:
        sast_enforcement_mode = "advisory"
    elif sast_detected or sast_ci:
        sast_enforcement_mode = "enforced"
    signals["sast"] = {
        "detected": sast_detected,
        "ci_enforced": sast_ci,
        "locus": sast_locus,
        "sources": [scan_to_source(scan) for scan in scans.get("security", [])]
        + sast_ci_matches["sources"],
        "enforcement_mode": sast_enforcement_mode,
        "advisory_signals": sast_ci_matches["advisory_signals"],
    }

    # Dependency audit
    dep_audit_detected = bool(scans.get("dependency_audit"))
    dep_audit_ci_matches = match_ci_sources(
        ci_workflows, ["audit", "dependabot", "renovate", "snyk"]
    )
    dep_audit_ci = dep_audit_ci_matches["ci_enforced"]
    dep_locus = []
    if dep_audit_detected:
        dep_locus.append("local_script")
    if dep_audit_ci_matches["sources"]:
        dep_locus.append("ci")
    # Check for dependabot config file
    if tree_has(tree, ".github/dependabot.yml") or tree_has(
        tree, ".github/dependabot.yaml"
    ):
        if not dep_audit_detected:
            dep_audit_detected = True
        dep_locus.append("config_file")
    # Check for renovate
    if (
        tree_has(tree, "renovate.json")
        or tree_has(tree, ".renovaterc")
        or tree_has(tree, ".renovaterc.json")
    ):
        if not dep_audit_detected:
            dep_audit_detected = True
        dep_locus.append("config_file")
    dep_locus = sorted(set(dep_locus))
    signals["dependency_audit"] = {
        "detected": dep_audit_detected,
        "ci_enforced": dep_audit_ci,
        "locus": dep_locus,
        "sources": [scan_to_source(scan) for scan in scans.get("dependency_audit", [])]
        + dep_audit_ci_matches["sources"],
        "enforcement_mode": (
            "advisory"
            if dep_audit_ci_matches["advisory_signals"] and not dep_audit_ci
            else "enforced" if dep_audit_detected or dep_audit_ci else "none"
        ),
        "advisory_signals": dep_audit_ci_matches["advisory_signals"],
    }

    # Local validation
    has_precommit = tree_has(tree, ".pre-commit-config.yaml")
    has_husky = tree_has_dir(tree, ".husky")
    has_validate_script = False
    has_precommit_script = False
    if pkg_scripts:
        has_validate_script = any(
            k in pkg_scripts for k in ["validate", "check", "precommit"]
        )
        has_precommit_script = "precommit" in pkg_scripts
    lv_locus = []
    if has_precommit or has_husky:
        lv_locus.append("precommit")
    if has_validate_script:
        lv_locus.append("validate_command")
    signals["local_validation"] = {
        "detected": has_precommit or has_husky or has_validate_script,
        "ci_enforced": False,
        "enforcement_mode": (
            "enforced" if has_precommit or has_husky or has_validate_script else "none"
        ),
        "locus": lv_locus,
        "sources": (
            [make_source(".pre-commit-config.yaml", "hook_config")]
            if has_precommit
            else []
        )
        + ([make_source(".husky/", "hook_config")] if has_husky else [])
        + (
            [make_source("package.json", "script_entry", "scripts.validate/check")]
            if has_validate_script
            else []
        )
        + (
            [make_source("package.json", "script_entry", "scripts.precommit")]
            if has_precommit_script
            else []
        ),
        "advisory_signals": [],
    }

    for key, val in signals.items():
        if val.get("detected"):
            locus_str = ", ".join(val.get("locus", [])) or "detected"
            enforcement_mode = val.get("enforcement_mode")
            ci_str = ""
            if enforcement_mode == "advisory":
                ci_str = " (advisory)"
            elif val.get("ci_enforced"):
                ci_str = " (CI enforced)"
            extra = ""
            if key == "lint" and val.get("strict"):
                extra = " [strict]"
            if key == "coverage" and val.get("changed_line"):
                extra = " [changed-line]"
            evidence.append(f"{key}: {locus_str}{ci_str}{extra}")

    return {"signals": signals, "evidence": evidence}


def detect_cat3(root: Path, tree: Set[str]) -> Dict[str, Any]:
    """Cat 3: AI Skills"""
    signals: Dict[str, Any] = {}
    evidence: List[str] = []

    # Find SKILL.md files (local skills)
    skill_paths = find_local_skills(tree)

    # Check apm.yml for skill manifest and remote skill dependencies
    apm_manifest = parse_apm_manifest(root, tree)
    signals["has_apm"] = apm_manifest["present"]
    apm_skills = apm_manifest["skills"]
    apm_security_skills = apm_manifest["security_skills"]
    apm_mcp_count = apm_manifest["mcp_entries"]
    if apm_manifest["present"]:
        evidence.append("apm.yml skill manifest found")

    total_local = len(skill_paths)
    total_apm = len(apm_skills)
    total_all = total_local + total_apm
    signals["total_skills"] = total_all
    signals["local_skills"] = total_local
    signals["apm_skills"] = total_apm
    signals["apm_mcp_count"] = apm_mcp_count
    if total_all:
        evidence.append(f"{total_all} skills ({total_local} local, {total_apm} apm)")

    # All skills count as workflow skills
    signals["core_workflow_skills"] = total_all

    # Security skills: check local SKILL.md content + apm paths
    security_keywords_content = [
        "security review",
        "security scan",
        "vulnerability",
        "sast",
        "cve",
        "supply chain",
        "threat model",
        "codeguard",
        "security audit",
    ]
    security_skills: List[str] = []
    for name, path in skill_paths.items():
        content = read_text(root / path)
        if content:
            lower = content.lower()
            if any(kw in lower for kw in security_keywords_content):
                security_skills.append(name)
    # Add apm security skills (path-based)
    for dep in apm_security_skills:
        skill_name = dep.split("/")[-1] if "/" in dep else dep
        if skill_name not in security_skills:
            security_skills.append(skill_name)
    signals["security_skills"] = len(security_skills)
    if security_skills:
        evidence.append(f"Security skills: {', '.join(sorted(security_skills))}")

    # Check for skills CLI dep
    pkg_content = (
        read_text(root / "package.json") if tree_has(tree, "package.json") else None
    )
    has_skills_cli = False
    if pkg_content:
        try:
            pkg = json.loads(pkg_content)
            all_deps = set()
            for dk in ("dependencies", "devDependencies"):
                all_deps.update(pkg.get(dk, {}).keys())
            has_skills_cli = any("skills" in d.lower() for d in all_deps)
        except (json.JSONDecodeError, ValueError):
            pass
    signals["skills_cli"] = has_skills_cli

    return {
        "signals": signals,
        "evidence": evidence,
        "_skill_names": set(skill_paths) | set(apm_skills),
        "_local_skill_names": set(skill_paths),
        "_apm_skill_names": set(apm_skills),
        "_security_skill_names": set(security_skills),
    }


def detect_cat4(root: Path, tree: Set[str]) -> Dict[str, Any]:
    """Cat 4: Documentation Tree"""
    signals: Dict[str, Any] = {}
    evidence: List[str] = []

    # AGENTS.md
    agents_exists = tree_has(tree, "AGENTS.md")
    agents_content = read_text(root / "AGENTS.md") if agents_exists else None
    agents_lines = len(agents_content.split("\n")) if agents_content else 0
    agents_has_routing = bool(agents_content and "docs/" in agents_content)
    agents_has_tree = False
    if agents_content:
        # Tree characters
        if any(c in agents_content for c in ["├", "└", "│"]):
            agents_has_tree = True
        # Explicit map language
        elif any(
            phrase in agents_content.lower()
            for phrase in [
                "this file is a map",
                "documentation map",
                "repo map",
                "repository map",
                "codebase map",
                "project map",
            ]
        ):
            agents_has_tree = True
        # Table-of-contents style with 5+ local links
        elif len(re.findall(r"\[.*?\]\(((?!http)[^)]+)\)", agents_content)) >= 5:
            agents_has_tree = True
    signals["agents_md"] = {
        "exists": agents_exists,
        "lines": agents_lines,
        "has_routing": agents_has_routing,
        "has_tree": agents_has_tree,
    }
    if agents_exists:
        evidence.append(f"AGENTS.md: {agents_lines} lines")

    # CONTRIBUTING.md
    contrib_exists = tree_has(tree, "CONTRIBUTING.md")
    contrib_content = read_text(root / "CONTRIBUTING.md") if contrib_exists else None
    contrib_mentions_validation = bool(
        contrib_content
        and any(w in contrib_content.lower() for w in ["validation", "testing"])
    )
    contrib_mentions_docs_tree = bool(
        contrib_content and "docs/" in contrib_content.lower()
    )
    contrib_mentions_specs = bool(contrib_content) and mentions_spec(contrib_content)
    signals["contributing"] = {
        "exists": contrib_exists,
        "mentions_validation": contrib_mentions_validation,
        "mentions_docs_tree": contrib_mentions_docs_tree,
        "mentions_specs": contrib_mentions_specs,
    }
    if contrib_exists:
        evidence.append("CONTRIBUTING.md exists")

    # docs/
    docs_exists = tree_has_dir(tree, "docs")
    docs_subdirs: List[str] = []
    if docs_exists:
        for p in tree:
            if p.startswith("docs/") and p.endswith("/") and p.count("/") == 2:
                docs_subdirs.append(p.rstrip("/").split("/")[1])
    signals["docs_structure"] = {
        "exists": docs_exists,
        "subdirs": sorted(set(docs_subdirs)),
        "subdir_count": len(set(docs_subdirs)),
        "has_architecture": "architecture" in docs_subdirs,
        "has_validation": "validation" in docs_subdirs,
        "has_guides": "guides" in docs_subdirs,
        "has_api": "api" in docs_subdirs,
    }
    if docs_exists:
        evidence.append(f"docs/ with {len(set(docs_subdirs))} subdirs")

    # Cross-links
    docs_files = [p for p in tree if p.startswith("docs/") and not p.endswith("/")]
    cross_links = 0
    for df in docs_files[:20]:  # limit reads
        content = read_text(root / df)
        if content and "docs/" in content:
            cross_links += 1
    signals["cross_links"] = cross_links

    return {"signals": signals, "evidence": evidence}


def detect_cat5(root: Path, tree: Set[str]) -> Dict[str, Any]:
    """Cat 5: AI IDE or coding-agent configuration."""
    signals: Dict[str, Any] = {}
    evidence: List[str] = []

    ides: Dict[str, Dict[str, Any]] = {}
    apm_manifest = parse_apm_manifest(root, tree)

    # Cursor
    cursor: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
    }
    if tree_has(tree, ".cursorrules"):
        cursor["has_config"] = True
        content = read_text(root / ".cursorrules")
        if content and len(content) > 200:
            cursor["has_repo_specific"] = True
    if tree_has_dir(tree, ".cursor/rules"):
        cursor["has_config"] = True
        cursor["has_multiple_contexts"] = True
    if tree_has(tree, ".cursor/mcp.json"):
        cursor["has_mcp"] = True
    if any(v for v in cursor.values()):
        ides["cursor"] = cursor
        evidence.append("Cursor configured")

    # Copilot
    copilot: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
    }
    if tree_has(tree, ".github/copilot-instructions.md"):
        copilot["has_config"] = True
        content = read_text(root / ".github/copilot-instructions.md")
        if content and len(content) > 200:
            copilot["has_repo_specific"] = True
    if tree_has(tree, ".copilotignore"):
        copilot["has_ignore"] = True
        copilot["has_config"] = True
    if any(v for v in copilot.values()):
        ides["copilot"] = copilot
        evidence.append("Copilot configured")

    # Windsurf
    windsurf: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
    }
    if tree_has(tree, ".windsurfrules"):
        windsurf["has_config"] = True
        content = read_text(root / ".windsurfrules")
        if content and len(content) > 200:
            windsurf["has_repo_specific"] = True
    if tree_has_dir(tree, ".windsurf/rules"):
        windsurf["has_config"] = True
        windsurf["has_multiple_contexts"] = True
    if any(v for v in windsurf.values()):
        ides["windsurf"] = windsurf
        evidence.append("Windsurf configured")

    # Claude
    claude: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
    }
    if tree_has(tree, "CLAUDE.md"):
        claude["has_config"] = True
        content = read_text(root / "CLAUDE.md")
        if content and len(content) > 200:
            claude["has_repo_specific"] = True
    if tree_has_dir(tree, ".claude/commands"):
        claude["has_config"] = True
        claude["has_multiple_contexts"] = True
    if tree_has(tree, ".claude/mcp.json"):
        claude["has_mcp"] = True
    if any(v for v in claude.values()):
        ides["claude"] = claude
        evidence.append("Claude configured")

    # Vendor-neutral agent configuration
    agent_agnostic: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
        "has_commands": False,
        "has_skills": False,
        "has_apm": False,
    }
    agents_content = (
        read_text(root / "AGENTS.md") if tree_has(tree, "AGENTS.md") else None
    )
    cross_agent_skills = [
        path
        for path in tree
        if path.startswith(".agents/skills/") and path.endswith("SKILL.md")
    ]
    if agents_content is not None:
        agent_agnostic["has_config"] = True
        if len(agents_content) > 200:
            agent_agnostic["has_repo_specific"] = True
    if cross_agent_skills:
        agent_agnostic["has_config"] = True
        agent_agnostic["has_skills"] = True
    if len(cross_agent_skills) > 1:
        agent_agnostic["has_multiple_contexts"] = True
    if any(v for v in agent_agnostic.values()):
        ides["agent_agnostic"] = agent_agnostic
        evidence.append("Vendor-neutral agent configuration found")
        if cross_agent_skills:
            evidence.append(f"{len(cross_agent_skills)} vendor-neutral agent skills")

    # Codex
    codex: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
        "has_commands": False,
        "has_skills": False,
        "has_apm": False,
    }
    codex_specific_skills = [
        path
        for path in tree
        if path.startswith(".codex/skills/") and path.endswith("SKILL.md")
    ]
    has_codex_config = tree_has(tree, ".codex/config.toml")
    has_codex_mcp = tree_has(tree, ".codex/mcp.json")
    codex_confirmed = bool(has_codex_config or has_codex_mcp or codex_specific_skills)
    if codex_confirmed:
        codex["has_config"] = True
        if codex_specific_skills:
            codex["has_skills"] = True
        if len(codex_specific_skills) > 1:
            codex["has_multiple_contexts"] = True
        if has_codex_mcp:
            codex["has_mcp"] = True
        elif has_codex_config:
            config_content = read_text(root / ".codex/config.toml")
            if config_content and "mcp_servers" in config_content:
                codex["has_mcp"] = True
        ides["codex"] = codex
        evidence.append("Codex configured")
        if codex_specific_skills:
            evidence.append(f"{len(codex_specific_skills)} Codex-specific skills")

    # OpenCode
    opencode: Dict[str, Any] = {
        "has_config": False,
        "has_mcp": False,
        "has_ignore": False,
        "has_repo_specific": False,
        "has_multiple_contexts": False,
        "has_commands": False,
        "has_skills": False,
        "has_apm": False,
    }
    if tree_has_dir(tree, ".opencode"):
        opencode["has_config"] = True
    if tree_has(tree, "opencode.json") or tree_has(tree, "opencode.jsonc"):
        opencode["has_config"] = True
        cfg_file = (
            "opencode.json" if tree_has(tree, "opencode.json") else "opencode.jsonc"
        )
        content = read_text(root / cfg_file)
        if content and (
            '"mcp"' in content or '"plugin"' in content or len(content) > 200
        ):
            opencode["has_repo_specific"] = True
    if tree_has(tree, ".opencode/mcp.json"):
        opencode["has_mcp"] = True
    # Also check opencode.json/opencode.jsonc for "mcp" key
    if not opencode["has_mcp"]:
        for cfg_name in ["opencode.json", "opencode.jsonc"]:
            if tree_has(tree, cfg_name):
                cfg_content = read_text(root / cfg_name)
                if cfg_content and '"mcp"' in cfg_content:
                    opencode["has_mcp"] = True
                    break
    # Multiple contexts from skills
    opencode_skills = [
        p for p in tree if p.startswith(".opencode/skills/") and p.endswith("SKILL.md")
    ]
    opencode_commands = [
        p
        for p in tree
        if p.startswith(".opencode/command/") or p.startswith(".opencode/commands/")
    ]
    if opencode_skills:
        opencode["has_skills"] = True
    if opencode_commands:
        opencode["has_commands"] = True
    if len(opencode_skills) + len(opencode_commands) > 1:
        opencode["has_multiple_contexts"] = True
    if apm_manifest["present"]:
        opencode["has_apm"] = True
        opencode["has_config"] = True
    if apm_manifest["mcp_entries"] > 0:
        opencode["has_mcp"] = True
    if any(v for v in opencode.values()):
        ides["opencode"] = opencode
        evidence.append("OpenCode configured")
        if opencode_commands:
            evidence.append(f"{len(opencode_commands)} OpenCode commands")
        if opencode_skills:
            evidence.append(f"{len(opencode_skills)} OpenCode skills")
        if apm_manifest["present"]:
            evidence.append("apm.yml extends cross-agent OpenCode config")

    signals["ides"] = ides
    signals["ide_count"] = len(ides)

    return {"signals": signals, "evidence": evidence}


def detect_cat6(root: Path, tree: Set[str]) -> Dict[str, Any]:
    """Cat 6: Agentic Legibility — 8 deterministic sub-metrics"""
    signals: Dict[str, Any] = {}
    evidence: List[str] = []

    # 1.1 Static entry points
    has_entry = tree_has(tree, "AGENTS.md") or tree_has(tree, "README.md")
    signals["static_entry_points"] = has_entry
    if has_entry:
        evidence.append("Static entry point (AGENTS.md or README.md)")

    # 4.1 Repo map
    has_repo_map = False
    for f in ["AGENTS.md", "README.md"]:
        if tree_has(tree, f):
            content = read_text(root / f)
            if content:
                # Tree characters
                if any(c in content for c in ["├", "└"]):
                    has_repo_map = True
                    break
                # Explicit map language
                lower = content.lower()
                if any(
                    phrase in lower
                    for phrase in [
                        "this file is a map",
                        "documentation map",
                        "repo map",
                        "repository map",
                        "codebase map",
                        "project map",
                    ]
                ):
                    has_repo_map = True
                    break
                # Table-of-contents style with multiple doc links (3+ markdown links to local paths)
                local_links = re.findall(r"\[.*?\]\(((?!http)[^)]+)\)", content)
                if len(local_links) >= 5:
                    has_repo_map = True
                    break
    signals["repo_map"] = has_repo_map
    if has_repo_map:
        evidence.append("Repo map found")

    # 4.2 Contributing routes to docs
    contrib_routes = False
    if tree_has(tree, "CONTRIBUTING.md"):
        content = read_text(root / "CONTRIBUTING.md")
        if content and (
            "docs/" in content.lower() or re.search(r"\[.*\]\(.*docs", content.lower())
        ):
            contrib_routes = True
    signals["contributing_routes_docs"] = contrib_routes
    if contrib_routes:
        evidence.append("CONTRIBUTING.md routes to docs")

    # 5.1 Validation command discoverable
    validation_discoverable = False
    if tree_has(tree, "package.json"):
        pkg_content = read_text(root / "package.json")
        if pkg_content:
            try:
                scripts = json.loads(pkg_content).get("scripts", {})
                validation_discoverable = any(
                    k in scripts for k in ["validate", "check", "verify"]
                )
            except (json.JSONDecodeError, ValueError):
                pass
    if not validation_discoverable and (
        tree_has(tree, "Makefile") or tree_has(tree, "makefile")
    ):
        make_path = (
            root / "Makefile" if tree_has(tree, "Makefile") else root / "makefile"
        )
        content = read_text(make_path)
        if content:
            validation_discoverable = bool(
                re.search(r"^(check|validate):", content, re.MULTILINE)
            )
    signals["validation_discoverable"] = validation_discoverable
    if validation_discoverable:
        evidence.append("Validation command discoverable")

    # 5.2 Test command discoverable
    signals["test_discoverable"] = False  # Will be set after candidates are known
    # This gets patched later

    # 8.1 CODEOWNERS
    has_codeowners = tree_has(tree, "CODEOWNERS") or tree_has(
        tree, ".github/CODEOWNERS"
    )
    signals["codeowners"] = has_codeowners
    if has_codeowners:
        evidence.append("CODEOWNERS found")

    # 8.2 LICENSE
    has_license = any(
        tree_has(tree, f) for f in ["LICENSE", "LICENSE.md", "LICENCE", "LICENSE.txt"]
    )
    if not has_license and tree_has(tree, "package.json"):
        pkg_content = read_text(root / "package.json")
        if pkg_content:
            try:
                pkg = json.loads(pkg_content)
                has_license = bool(pkg.get("license"))
            except (json.JSONDecodeError, ValueError):
                pass
    signals["license"] = has_license
    if has_license:
        evidence.append(
            "LICENSE found"
            if any(
                tree_has(tree, f)
                for f in ["LICENSE", "LICENSE.md", "LICENCE", "LICENSE.txt"]
            )
            else "package.json license metadata found"
        )

    # 9.1 CHANGELOG or ADR or spec-driven planning records (decision records).
    # Require stronger evidence than a bare directory: OpenSpec change records,
    # SpecKit's planning memory, BMAD's planning artifacts, GSD's phase history
    # or milestone archive, or a `specs/` directory holding real planning
    # artifacts. A `.specify/` with only templates/config, a `_bmad/` with only
    # config, or `specs/` with only OpenAPI/test files, does not count as
    # decision-record history.
    has_changelog = tree_has(tree, "CHANGELOG.md") or tree_has(tree, "CHANGELOG")
    has_adr = (
        tree_has_dir(tree, "docs/adr")
        or tree_has_dir(tree, "docs/decisions")
        or tree_has_dir(tree, "adr")
    )
    has_spec_changes = (
        tree_has_dir(tree, "openspec/changes")
        or tree_has_dir(tree, ".specify/memory")
        or tree_has_dir(tree, "_bmad-output/planning-artifacts")
        or tree_has_dir(tree, ".planning/phases")
        or tree_has(tree, ".planning/MILESTONES.md")
        or (tree_has_dir(tree, "specs") and specs_dir_has_planning_artifacts(tree))
    )
    signals["changelog_or_adr"] = has_changelog or has_adr or has_spec_changes
    if has_changelog:
        evidence.append("CHANGELOG found")
    if has_adr:
        evidence.append("ADR directory found")
    if has_spec_changes:
        evidence.append("Spec-driven planning records (decision records) found")

    return {"signals": signals, "evidence": evidence}


def _store_evidence(store_root: EvidenceRoot, category: Dict[str, Any]) -> List[str]:
    prefix = f"OpenSpec store '{store_root.store_id}'"
    evidence = category.get("evidence", [])
    if not evidence:
        return [f"{prefix}: scanned as configured assessment context"]
    return [f"{prefix}: {item}" for item in evidence]


def _scores_by_id(scores: List[Dict[str, Any]]) -> Dict[str, int]:
    return {
        item["id"]: int(item["score"])
        for item in scores
        if item.get("score") is not None
    }


def score_category(
    category: Dict[str, Any],
    scorer: Callable[[Dict[str, Any]], List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    scores = scorer(category["signals"])
    overrides = category.get("_sub_metric_scores", {})
    for item in scores:
        if item["id"] in overrides:
            item["score"] = overrides[item["id"]]
    return scores


def merge_cat1_store_evidence(
    primary: Dict[str, Any],
    store_categories: List[Tuple[EvidenceRoot, Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(primary)
    signals = merged["signals"]
    categories = [primary] + [category for _, category in store_categories]
    scored_categories = [
        (category, _scores_by_id(score_cat1(category["signals"])))
        for category in categories
    ]

    def strongest(metric_id: str) -> Dict[str, Any]:
        return max(
            scored_categories,
            key=lambda item: item[1].get(metric_id, 0),
        )[0]

    system_keys = (
        "spec_dir_names",
        "spec_system_dir",
        "cli_dep",
        "has_spec_activity",
        "changes_count",
        "archived_count",
        "work_items_count",
        "complete_work_items_count",
        "substantive_work_items_count",
        "has_substantive_spec_activity",
        "completed_work_items_count",
        "has_completed_cycle",
        "has_recent_spec_activity",
        "workflow_integration_paths",
        "workflow_integration_documented",
        "cli_validation_available",
        "cli_validation_passed",
    )
    workflow_keys = (
        "github_prompts",
        "workflow_skills",
        "workflow_commands",
    )
    documentation_keys = (
        "contributing_mentions_spec",
        "agents_mentions_spec",
    )

    for keys, metric_id in (
        (system_keys, "1.system_and_artifacts"),
        (workflow_keys, "1.workflow_commands"),
        (documentation_keys, "1.documentation"),
    ):
        source_signals = strongest(metric_id)["signals"]
        for key in keys:
            signals[key] = copy.deepcopy(source_signals.get(key))

    merged["_sub_metric_scores"] = {
        metric_id: max(scores.get(metric_id, 0) for _, scores in scored_categories)
        for metric_id in (
            "1.system_and_artifacts",
            "1.workflow_commands",
            "1.documentation",
        )
    }
    for store_root, category in store_categories:
        merged["evidence"].extend(_store_evidence(store_root, category))
    return merged


def merge_cat3_store_evidence(
    primary: Dict[str, Any],
    store_categories: List[Tuple[EvidenceRoot, Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(primary)
    skill_names = set(primary.get("_skill_names", set()))
    local_names = set(primary.get("_local_skill_names", set()))
    apm_names = set(primary.get("_apm_skill_names", set()))
    security_names = set(primary.get("_security_skill_names", set()))

    for store_root, category in store_categories:
        skill_names.update(category.get("_skill_names", set()))
        local_names.update(category.get("_local_skill_names", set()))
        apm_names.update(category.get("_apm_skill_names", set()))
        security_names.update(category.get("_security_skill_names", set()))
        merged["signals"]["has_apm"] = bool(
            merged["signals"].get("has_apm") or category["signals"].get("has_apm")
        )
        merged["signals"]["skills_cli"] = bool(
            merged["signals"].get("skills_cli") or category["signals"].get("skills_cli")
        )
        merged["signals"]["apm_mcp_count"] = max(
            int(merged["signals"].get("apm_mcp_count", 0)),
            int(category["signals"].get("apm_mcp_count", 0)),
        )
        merged["evidence"].extend(_store_evidence(store_root, category))

    # A skill available in more than one configured root is still one capability.
    apm_only_names = apm_names - local_names
    merged["signals"]["total_skills"] = len(skill_names)
    merged["signals"]["local_skills"] = len(local_names)
    merged["signals"]["apm_skills"] = len(apm_only_names)
    merged["signals"]["core_workflow_skills"] = len(skill_names)
    merged["signals"]["security_skills"] = len(security_names)
    merged["_skill_names"] = skill_names
    merged["_local_skill_names"] = local_names
    merged["_apm_skill_names"] = apm_names
    merged["_security_skill_names"] = security_names
    return merged


def merge_cat4_store_evidence(
    primary: Dict[str, Any],
    store_categories: List[Tuple[EvidenceRoot, Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(primary)
    signals = merged["signals"]
    categories = [primary] + [category for _, category in store_categories]
    scored_categories = [
        (category, _scores_by_id(score_cat4(category["signals"])))
        for category in categories
    ]

    def strongest(metric_id: str) -> Dict[str, Any]:
        return max(
            scored_categories,
            key=lambda item: item[1].get(metric_id, 0),
        )[0]

    signals["agents_md"] = copy.deepcopy(
        strongest("4.agents_md")["signals"]["agents_md"]
    )
    signals["contributing"] = copy.deepcopy(
        strongest("4.contributing")["signals"]["contributing"]
    )
    signals["docs_structure"] = copy.deepcopy(
        strongest("4.docs_structure")["signals"]["docs_structure"]
    )
    signals["cross_links"] = int(
        strongest("4.content_quality")["signals"].get("cross_links", 0)
    )
    merged["_sub_metric_scores"] = {
        metric_id: max(scores.get(metric_id, 0) for _, scores in scored_categories)
        for metric_id in (
            "4.agents_md",
            "4.contributing",
            "4.docs_structure",
            "4.content_quality",
        )
    }

    for store_root, category in store_categories:
        merged["evidence"].extend(_store_evidence(store_root, category))

    return merged


def merge_cat5_store_evidence(
    primary: Dict[str, Any],
    store_categories: List[Tuple[EvidenceRoot, Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(primary)
    ides = merged["signals"].setdefault("ides", {})
    for store_root, category in store_categories:
        for ide_name, store_ide in category["signals"].get("ides", {}).items():
            if ide_name not in ides:
                ides[ide_name] = copy.deepcopy(store_ide)
                continue
            for key, value in store_ide.items():
                if isinstance(value, bool):
                    ides[ide_name][key] = bool(ides[ide_name].get(key) or value)
        merged["evidence"].extend(_store_evidence(store_root, category))
    merged["signals"]["ide_count"] = len(ides)
    return merged


def merge_cat6_store_evidence(
    primary: Dict[str, Any],
    store_categories: List[Tuple[EvidenceRoot, Dict[str, Any]]],
) -> Dict[str, Any]:
    merged = copy.deepcopy(primary)
    # These signals can be satisfied by delegated context. Code ownership,
    # licensing, test discovery, and source layout remain properties of the
    # assessed repository unless the deep review proves a shared command applies.
    delegated_keys = (
        "static_entry_points",
        "repo_map",
        "contributing_routes_docs",
        "validation_discoverable",
        "changelog_or_adr",
    )
    for store_root, category in store_categories:
        for key in delegated_keys:
            merged["signals"][key] = bool(
                merged["signals"].get(key) or category["signals"].get(key)
            )
        merged["evidence"].extend(_store_evidence(store_root, category))
    return merged


# ---------------------------------------------------------------------------
# Scoring Engine
# ---------------------------------------------------------------------------


def score_cat1(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []

    # system_and_artifacts. A score of 4 reflects observable lifecycle maturity
    # in one evidence root. An active work item is optional: archive-before-merge
    # repositories can qualify from complete archived work, recency, validation,
    # and documented workflow integration.
    score = 0
    if signals.get("spec_system_dir"):
        score = 1
        if signals.get("has_substantive_spec_activity"):
            score = 2
        if signals.get("complete_work_items_count", 0) >= 2:
            score = 3
        cli_is_healthy = not signals.get("cli_validation_available") or signals.get(
            "cli_validation_passed"
        )
        if (
            score == 3
            and signals.get("has_completed_cycle")
            and signals.get("has_recent_spec_activity")
            and signals.get("workflow_integration_documented")
            and cli_is_healthy
        ):
            score = 4
    sub_metrics.append(
        {
            "id": "1.system_and_artifacts",
            "name": "Spec system and artifacts",
            "score": score,
            "max": 4,
        }
    )

    # workflow_commands
    score = 0
    if signals.get("github_prompts"):
        score = 1
    if signals.get("workflow_commands", 0) > 0 or signals.get("workflow_skills", 0) > 0:
        score = max(score, 2)
    if (
        signals.get("workflow_commands", 0) > 0
        and signals.get("workflow_skills", 0) > 0
    ):
        score = 3
    if score == 3 and signals.get("workflow_skills", 0) > 3:
        score = 4
    sub_metrics.append(
        {
            "id": "1.workflow_commands",
            "name": "Workflow commands and skills",
            "score": score,
            "max": 4,
        }
    )

    # documentation
    score = 0
    if signals.get("contributing_mentions_spec") or signals.get("agents_mentions_spec"):
        score = 2
    if signals.get("contributing_mentions_spec") and signals.get(
        "agents_mentions_spec"
    ):
        score = 3
    if (
        score == 3
        and signals.get("spec_system_dir")
        and signals.get("has_spec_activity")
    ):
        score = 4
    sub_metrics.append(
        {
            "id": "1.documentation",
            "name": "Spec documentation",
            "score": score,
            "max": 4,
        }
    )

    return sub_metrics


def score_cat2(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []
    checks = [
        "lint",
        "typecheck",
        "test",
        "sast",
        "dependency_audit",
        "build",
        "local_validation",
    ]
    for check in checks:
        data = signals.get(check, {})
        detected = data.get("detected", False)
        ci_enforced = data.get("ci_enforced", False)
        locus = data.get("locus", [])
        enforcement_mode = data.get("enforcement_mode", "none")
        enforced_anywhere = enforcement_mode != "advisory" and (
            ci_enforced or "precommit" in locus or "validate_command" in locus
        )

        score = 0
        strictness_proven = False

        if detected:
            score = 2
        if detected and enforced_anywhere:
            score = 3

        # Score 4 rules per check type
        if score >= 3 and check == "lint":
            if data.get("strict"):
                score = 4
                strictness_proven = True
        elif score >= 3 and check == "test":
            # Multi-lane testing or changed-line coverage = 4
            cov = signals.get("coverage", {})
            if data.get("has_integration_lane") or data.get("has_e2e_lane"):
                score = 4
                strictness_proven = True
            if cov.get("changed_line") and any(
                coverage_locus in cov.get("locus", [])
                for coverage_locus in ["precommit", "validate_command", "ci"]
            ):
                score = 4
                strictness_proven = True
        elif score >= 3 and check not in ("local_validation",):
            # Generic: if enforced in 2+ loci (local_script counts as enforcement locus for
            # checks that are intentionally separate from validate, e.g. SAST)
            enforcement_loci = [
                enforcement_locus
                for enforcement_locus in locus
                if enforcement_locus
                in ("local_script", "precommit", "validate_command", "ci")
            ]
            if len(enforcement_loci) >= 2:
                score = 4
                strictness_proven = True
        elif check == "local_validation" and detected:
            sources = data.get("sources", [])
            has_hooks = any(
                source.get("file") in [".husky/", ".pre-commit-config.yaml"]
                for source in sources
            )
            has_script = any("script" in source.get("type", "") for source in sources)
            has_precommit = any(
                "precommit" in source.get("detail", "").lower() for source in sources
            )
            if has_hooks and has_script:
                score = 4
                strictness_proven = True
            elif has_hooks or has_script or has_precommit:
                score = 3

        sub_metrics.append(
            {
                "id": f"2.{check}",
                "name": check,
                "score": score,
                "max": 4,
                "capability": detected,
                "strictness_proven": strictness_proven,
                "locus": locus,
            }
        )

    # Add coverage as informational sub-metric (not scored separately, feeds into test)
    cov = signals.get("coverage", {})
    if cov.get("detected"):
        sub_metrics.append(
            {
                "id": "2.coverage",
                "name": "coverage",
                "score": None,  # informational — feeds into test score
                "max": 4,
                "capability": True,
                "changed_line": cov.get("changed_line", False),
                "locus": cov.get("locus", []),
                "note": "Coverage signals feed into test scoring; not scored independently",
            }
        )

    return sub_metrics


def score_cat3(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []

    # workflow_skills (all skills count)
    total = signals.get("total_skills", 0)
    score = 0
    if total >= 1:
        score = 1
    if total >= 3:
        score = 2
    if total >= 5:
        score = 3
    if total >= 8:
        score = 4
    sub_metrics.append(
        {"id": "3.workflow_skills", "name": "Workflow skills", "score": score, "max": 4}
    )

    # security_skills
    sec = signals.get("security_skills", 0)
    score = 0
    if sec >= 1:
        score = 2
    if sec >= 2:
        score = 3
    if sec >= 3:
        score = 4
    sub_metrics.append(
        {"id": "3.security_skills", "name": "Security skills", "score": score, "max": 4}
    )

    # relevance
    score = 0
    if total > 0:
        score = 2
    if total >= 3:
        score = 3
    if total >= 3 and sec >= 1:
        score = 4
    sub_metrics.append(
        {"id": "3.relevance", "name": "Skill relevance", "score": score, "max": 4}
    )

    return sub_metrics

    return sub_metrics


def score_cat4(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []

    # agents_md
    am = signals.get("agents_md", {})
    score = 0
    if am.get("exists"):
        score = 1
        if am.get("lines", 0) >= 20:
            score = 2
        if am.get("has_routing"):
            score = 3
        if am.get("has_routing") and am.get("has_tree"):
            score = 4
    sub_metrics.append(
        {"id": "4.agents_md", "name": "AGENTS.md", "score": score, "max": 4}
    )

    # contributing
    c = signals.get("contributing", {})
    score = 0
    if c.get("exists"):
        score = 1
        if c.get("mentions_validation"):
            score = 2
        if c.get("mentions_docs_tree"):
            score = 3
        if (
            c.get("mentions_specs")
            and c.get("mentions_validation")
            and c.get("mentions_docs_tree")
        ):
            score = 4
    sub_metrics.append(
        {"id": "4.contributing", "name": "CONTRIBUTING.md", "score": score, "max": 4}
    )

    # docs_structure
    ds = signals.get("docs_structure", {})
    score = 0
    if ds.get("exists"):
        score = 1
        if ds.get("subdir_count", 0) >= 2:
            score = 2
        if ds.get("subdir_count", 0) >= 4:
            score = 3
        if (
            ds.get("has_architecture")
            and ds.get("has_validation")
            and ds.get("has_guides")
        ):
            score = 4
    sub_metrics.append(
        {"id": "4.docs_structure", "name": "Docs structure", "score": score, "max": 4}
    )

    # content_quality
    cross_links = signals.get("cross_links", 0)
    ds_exists = signals.get("docs_structure", {}).get("exists", False)
    score = 0
    if ds_exists:
        score = 1
        if cross_links >= 2:
            score = 2
        if cross_links >= 5:
            score = 3
        if cross_links >= 10:
            score = 4
    sub_metrics.append(
        {"id": "4.content_quality", "name": "Content quality", "score": score, "max": 4}
    )

    return sub_metrics


def score_cat5(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []
    ides = signals.get("ides", {})
    surface_keys = (
        "has_config",
        "has_commands",
        "has_skills",
        "has_apm",
        "has_mcp",
    )

    # Find the strongest configured surface
    best_ide: Optional[Dict[str, Any]] = None
    best_score = -1
    for ide_name, ide_data in ides.items():
        ide_score = sum(1 for v in ide_data.values() if v is True)
        if ide_score > best_score:
            best_score = ide_score
            best_ide = ide_data

    if not best_ide:
        best_ide = {}

    # Score each sub-metric against the strongest relevant operating surface.
    # A repository may configure multiple agents, so the most complete workflow
    # surface can differ from the most complete general agent configuration.
    operating_surface = max(
        ides.values(),
        key=lambda ide: sum(1 for key in surface_keys if ide.get(key)),
        default={},
    )
    surface_breadth = sum(1 for key in surface_keys if operating_surface.get(key))
    mcp_surface = max(
        (ide for ide in ides.values() if ide.get("has_mcp")),
        key=lambda ide: (
            bool(ide.get("has_repo_specific")),
            sum(1 for key in surface_keys if ide.get(key)),
        ),
        default={},
    )

    # config_exists — evaluates whether the agent surface is repo-specific
    ide_count = signals.get("ide_count", 0)
    score = 0
    if ide_count >= 1:
        score = 2
    if best_ide.get("has_repo_specific") or surface_breadth >= 3:
        score = 3
    if (
        best_ide.get("has_multiple_contexts")
        or best_ide.get("has_apm")
        or surface_breadth >= 4
    ):
        score = 4
    sub_metrics.append(
        {
            "id": "5.config_exists",
            "name": "AI coding config exists",
            "score": score,
            "max": 4,
        }
    )

    # commands_and_skills — evaluates the agent workflow surface
    score = 0
    if (
        best_ide.get("has_multiple_contexts")
        or operating_surface.get("has_commands")
        or operating_surface.get("has_skills")
    ):
        score = 2
    if operating_surface.get("has_commands") and operating_surface.get("has_skills"):
        score = 3
    if score >= 3 and operating_surface.get("has_apm"):
        score = 4
    elif operating_surface.get("has_apm") and (
        operating_surface.get("has_commands") or operating_surface.get("has_skills")
    ):
        score = max(score, 3)
        if surface_breadth >= 4:
            score = 4
    sub_metrics.append(
        {
            "id": "5.commands_and_skills",
            "name": "Commands and skills",
            "score": score,
            "max": 4,
        }
    )

    # mcp_integration
    score = 0
    if mcp_surface:
        score = 3
    if mcp_surface and (
        mcp_surface.get("has_repo_specific")
        or sum(1 for key in surface_keys if mcp_surface.get(key)) >= 3
    ):
        score = 4
    sub_metrics.append(
        {"id": "5.mcp_integration", "name": "MCP integration", "score": score, "max": 4}
    )

    return sub_metrics


def score_cat6(signals: Dict[str, Any]) -> List[Dict[str, Any]]:
    sub_metrics: List[Dict[str, Any]] = []
    deterministic = [
        ("6.static_entry_points", "Static entry points", "static_entry_points"),
        ("6.repo_map", "Repo map", "repo_map"),
        (
            "6.contributing_routes_docs",
            "Contributing routes to docs",
            "contributing_routes_docs",
        ),
        (
            "6.validation_discoverable",
            "Validation command discoverable",
            "validation_discoverable",
        ),
        ("6.test_discoverable", "Test command discoverable", "test_discoverable"),
        ("6.codeowners", "CODEOWNERS", "codeowners"),
        ("6.license", "LICENSE", "license"),
        ("6.changelog_or_adr", "CHANGELOG or ADR", "changelog_or_adr"),
    ]
    for metric_id, name, key in deterministic:
        val = signals.get(key, False)
        score = 4 if val else 0
        sub_metrics.append({"id": metric_id, "name": name, "score": score, "max": 4})

    # 10 N/A sub-metrics (require content reasoning)
    na_metrics = [
        "6.semantic_naming",
        "6.api_docs_quality",
        "6.error_handling_patterns",
        "6.code_comments_quality",
        "6.type_coverage_depth",
        "6.dependency_docs",
        "6.architecture_clarity",
        "6.onboarding_path",
        "6.debug_affordances",
        "6.change_impact_clarity",
    ]
    for metric_id in na_metrics:
        name = metric_id.split(".", 1)[1].replace("_", " ").title()
        sub_metrics.append({"id": metric_id, "name": name, "score": None, "max": 4})

    return sub_metrics


def compute_scores(all_sub_metrics: Dict[int, List[Dict[str, Any]]]) -> Dict[str, Any]:
    category_scores: List[Dict[str, Any]] = []
    cat_means: Dict[int, Optional[float]] = {}

    for cat_num in range(1, 7):
        metrics = all_sub_metrics.get(cat_num, [])
        scored = [m for m in metrics if m["score"] is not None]
        if scored:
            mean = sum(m["score"] for m in scored) / len(scored)
            cat_means[cat_num] = mean
        else:
            cat_means[cat_num] = None
        category_scores.append(
            {
                "category": cat_num,
                "mean": cat_means[cat_num],
                "sub_metric_count": len(metrics),
                "scored_count": len(scored),
            }
        )

    # Weighted composite
    total_weight = 0.0
    weighted_sum = 0.0
    for cat_num, mean in cat_means.items():
        if mean is not None:
            w = CATEGORY_WEIGHTS[cat_num]
            weighted_sum += mean * w
            total_weight += w

    composite = weighted_sum / total_weight if total_weight > 0 else 0.0
    composite = round(composite, 2)

    # Tier
    if composite <= 0.9:
        tier = "Unaware"
    elif composite <= 1.9:
        tier = "Nascent"
    elif composite <= 2.9:
        tier = "Structured"
    elif composite <= 3.5:
        tier = "Established"
    else:
        tier = "Exemplary"

    # Flatten sub_metrics
    flat_sub_metrics: List[Dict[str, Any]] = []
    for cat_num in range(1, 7):
        flat_sub_metrics.extend(all_sub_metrics.get(cat_num, []))

    has_partial_cat6 = any(m["score"] is None for m in all_sub_metrics.get(6, []))

    return {
        "sub_metrics": flat_sub_metrics,
        "categories": category_scores,
        "composite": composite,
        "tier": tier,
        "provisional": has_partial_cat6,
    }


def compute_recommended_actions(
    all_sub_metrics: Dict[int, List[Dict[str, Any]]],
) -> List[Dict[str, Any]]:
    actions: List[Dict[str, Any]] = []
    cat_num_for_metric: Dict[str, int] = {}
    for cat_num in range(1, 7):
        for m in all_sub_metrics.get(cat_num, []):
            cat_num_for_metric[m["id"]] = cat_num

    for cat_num in range(1, 7):
        weight = CATEGORY_WEIGHTS[cat_num]
        for m in all_sub_metrics.get(cat_num, []):
            if m["score"] is None:
                continue
            if m["score"] < 3:
                impact = (3 - m["score"]) / 4.0 * weight
                actions.append(
                    {
                        "sub_metric_id": m["id"],
                        "name": m["name"],
                        "current_score": m["score"],
                        "target_score": 3,
                        "impact": round(impact, 4),
                        "category": cat_num,
                    }
                )

    actions.sort(key=lambda a: -a["impact"])
    return actions


# ---------------------------------------------------------------------------
# AI Validation
# ---------------------------------------------------------------------------


def build_ai_validation(
    selected: Dict[str, List[ToolCandidate]],
    cat2_signals: Dict[str, Any],
    all_sub_metrics: Optional[Dict[int, List[Dict[str, Any]]]] = None,
) -> Dict[str, Any]:
    ambiguous: List[str] = []
    for kind, candidates in selected.items():
        if len(candidates) > 1:
            ambiguous.append(kind)

    suggestions: List[str] = []
    if all_sub_metrics is not None:
        # Cat 6 N/A sub-metrics
        cat6_na = [m for m in all_sub_metrics.get(6, []) if m["score"] is None]
        if cat6_na:
            suggestions.append(
                "Review 10 Cat 6 deep sub-metrics requiring content reasoning"
            )

    # Contradictory signals
    for check_name, check_data in cat2_signals.items():
        if isinstance(check_data, dict):
            if check_data.get("ci_enforced") and not check_data.get("detected"):
                suggestions.append(
                    f"CI has {check_name} but no local config detected — verify setup"
                )

    evidence_gaps: List[Dict[str, Any]] = []
    if all_sub_metrics is not None:
        # Evidence-missing hints: capability present but strictness not proven
        for m in all_sub_metrics.get(2, []):
            if (
                m.get("capability")
                and not m.get("strictness_proven")
                and (m.get("score") or 0) >= 3
            ):
                evidence_gaps.append(
                    {
                        "sub_metric": m["id"],
                        "capability": True,
                        "strictness_proven": False,
                        "current_score": m["score"],
                        "hint": f"{m['name']} is enforced but strictness not mechanically proven - LLM should verify",
                    }
                )
                suggestions.append(
                    f"Verify {m['name']} strictness (capability present, enforcement proof incomplete)"
                )

    return {
        "ambiguous_commands": ambiguous,
        "review_suggestions": suggestions,
        "evidence_gaps": evidence_gaps,
        "status": "not_run",
        "scoring_enabled": all_sub_metrics is not None,
    }


# ---------------------------------------------------------------------------
# Main Assembly
# ---------------------------------------------------------------------------


def main() -> None:
    args = parse_args()
    root = args.repo_root
    tree = build_tree(root)
    evidence_roots, openspec_context_notes = resolve_openspec_evidence_roots(root)

    # Detect languages, pkg managers, monorepo
    languages = detect_languages(root, tree)
    pkg_mgrs = detect_package_managers(languages, tree)
    monorepo = detect_monorepo(root, tree)

    # Run probes
    all_candidates: List[ToolCandidate] = []
    if "node" in languages:
        all_candidates.extend(probe_node(root, tree, pkg_mgrs.get("node", "npm")))
    if "python" in languages:
        all_candidates.extend(probe_python(root, tree, pkg_mgrs.get("python", "pip")))
    if "rust" in languages:
        all_candidates.extend(probe_rust(root, tree))
    if "go" in languages:
        all_candidates.extend(probe_go(root, tree))
    if "java_kotlin" in languages:
        all_candidates.extend(probe_java_kotlin(root, tree))
    if "dotnet" in languages:
        all_candidates.extend(probe_dotnet(root, tree))

    # Justfile/Makefile wrappers
    all_candidates.extend(probe_justfile(root, tree))
    all_candidates.extend(probe_makefile(root, tree))

    # Select best commands
    candidates_by_kind = group_candidates_by_kind(all_candidates)
    selected = select_best_commands(all_candidates)

    # Discover additional scans
    additional_scans = discover_additional_scans(root, tree)

    # Detect categories
    local_cli_validation, local_cli_error = validate_local_spec_cli(root, tree)
    cat1 = detect_cat1(root, tree, local_cli_validation)
    if local_cli_error:
        cat1["evidence"].append(
            f"Local spec CLI status/check validation did not pass: {local_cli_error}"
        )
    cat2 = detect_cat2(root, tree, candidates_by_kind, additional_scans)
    cat3 = detect_cat3(root, tree)
    cat4 = detect_cat4(root, tree)
    cat5 = detect_cat5(root, tree)
    cat6 = detect_cat6(root, tree)

    # Patch cat6 test_discoverable
    cat6["signals"]["test_discoverable"] = "test" in candidates_by_kind

    store_cat1: List[Tuple[EvidenceRoot, Dict[str, Any]]] = []
    store_cat3: List[Tuple[EvidenceRoot, Dict[str, Any]]] = []
    store_cat4: List[Tuple[EvidenceRoot, Dict[str, Any]]] = []
    store_cat5: List[Tuple[EvidenceRoot, Dict[str, Any]]] = []
    store_cat6: List[Tuple[EvidenceRoot, Dict[str, Any]]] = []
    for evidence_root in evidence_roots:
        store_tree = build_store_tree(evidence_root.path)
        store_cat1.append(
            (
                evidence_root,
                detect_cat1(
                    evidence_root.path,
                    store_tree,
                    evidence_root.cli_validation_passed,
                ),
            )
        )
        store_cat3.append((evidence_root, detect_cat3(evidence_root.path, store_tree)))
        store_cat4.append((evidence_root, detect_cat4(evidence_root.path, store_tree)))
        store_cat5.append((evidence_root, detect_cat5(evidence_root.path, store_tree)))
        store_cat6.append((evidence_root, detect_cat6(evidence_root.path, store_tree)))

    if evidence_roots:
        cat1 = merge_cat1_store_evidence(cat1, store_cat1)
        cat3 = merge_cat3_store_evidence(cat3, store_cat3)
        cat4 = merge_cat4_store_evidence(cat4, store_cat4)
        cat5 = merge_cat5_store_evidence(cat5, store_cat5)
        cat6 = merge_cat6_store_evidence(cat6, store_cat6)
        configured_stores = ", ".join(item.store_id for item in evidence_roots)
        cat2["evidence"].append(
            "Configured OpenSpec stores available for shared validation review: "
            f"{configured_stores}"
        )
    for note in openspec_context_notes:
        cat1["evidence"].append(f"OpenSpec context: {note}")

    all_sub_metrics: Optional[Dict[int, List[Dict[str, Any]]]] = None
    scores: Optional[Dict[str, Any]] = None
    recommended_actions: Optional[List[Dict[str, Any]]] = None
    if args.with_scoring:
        all_sub_metrics = {
            1: score_category(cat1, score_cat1),
            2: score_cat2(cat2["signals"]),
            3: score_cat3(cat3["signals"]),
            4: score_category(cat4, score_cat4),
            5: score_cat5(cat5["signals"]),
            6: score_cat6(cat6["signals"]),
        }
        scores = compute_scores(all_sub_metrics)
        recommended_actions = compute_recommended_actions(all_sub_metrics)

    ai_validation = build_ai_validation(selected, cat2["signals"], all_sub_metrics)
    if evidence_roots:
        ai_validation["review_suggestions"].append(
            "Review configured OpenSpec store commands and validation documentation; "
            "count them only when they execute against the assessed repository"
        )

    # Build candidates output
    commands_output: Dict[str, List[Dict[str, Any]]] = {}
    for c in all_candidates:
        commands_output.setdefault(c.kind, []).append(c.to_dict())

    selected_output: Dict[str, List[Dict[str, Any]]] = {}
    for kind, cands in selected.items():
        if cands:
            selected_output[kind] = [candidate.to_dict() for candidate in cands]

    # Additional scans flat list for top-level
    additional_scans_flat: List[Dict[str, Any]] = []
    for kind, scan_list in additional_scans.items():
        for s in scan_list:
            additional_scans_flat.append(s)

    # Assemble output
    output = {
        "version": VERSION,
        "repo_root": str(root),
        "scoring_enabled": args.with_scoring,
        "languages": languages,
        "package_managers": pkg_mgrs,
        "monorepo": monorepo,
        "candidates": {
            "commands": commands_output,
            "additional_scans": additional_scans,
        },
        "selected_commands": selected_output,
        "additional_scans": additional_scans_flat,
        "categories": {
            "1": {"signals": cat1["signals"], "evidence": cat1["evidence"]},
            "2": {"signals": cat2["signals"], "evidence": cat2["evidence"]},
            "3": {"signals": cat3["signals"], "evidence": cat3["evidence"]},
            "4": {"signals": cat4["signals"], "evidence": cat4["evidence"]},
            "5": {"signals": cat5["signals"], "evidence": cat5["evidence"]},
            "6": {"signals": cat6["signals"], "evidence": cat6["evidence"]},
        },
        "ai_validation": ai_validation,
    }

    if scores is not None:
        output["scores"] = scores
    if recommended_actions is not None:
        output["recommended_actions"] = recommended_actions

    json.dump(output, sys.stdout, indent=2, sort_keys=False)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
