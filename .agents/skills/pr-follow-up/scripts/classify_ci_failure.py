#!/usr/bin/env python3
"""Classify CI failure check names and log excerpts for pr-follow-up auto-fix."""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import namedtuple
from pathlib import Path
from typing import Optional

ClassificationResult = namedtuple(
    "ClassificationResult",
    [
        "classification",
        "fix_tier",
        "strategy",
        "confidence",
        "reason",
    ],
)

LINT_PATTERNS = (
    r"\blint\b",
    r"\bruff\b",
    r"\beslint\b",
    r"\bprettier\b",
    r"\bformat\b",
    r"\bblack\b",
)
TEST_PATTERNS = (
    r"\bpytest\b",
    r"\bjest\b",
    r"\bvitest\b",
    r"\bjunit\b",
    r"\btest failed\b",
    r"\btests failed\b",
    r"FAILED ",
)
SECURITY_PATTERNS = (
    r"skill[- ]scanner",
    r"cisco ai defense",
    r"\bsemgrep\b",
    r"\bsast\b",
    r"rule_id",
    r"remediation",
)
SKILL_SPEC_PATTERNS = (
    r"agentskills validate",
    r"skill spec compliance",
    r"failed validation",
)
REGISTRY_PATTERNS = (
    r"skills\.json",
    r"generate-registry",
    r"not found in registry",
)
MARKETPLACE_PATTERNS = (
    r"marketplace\.json",
    r"apm pack",
    r"validate-packages",
    r"package validation",
)
EXTERNAL_SKILLS_PATTERNS = (
    r"scan external skills",
    r"external-skills\.json",
)
REBASE_PATTERNS = (
    r"\bbehind\b",
    r"non-fast-forward",
    r"fetch first",
)
CONFLICT_PATTERNS = (
    r"\bconflict",
    r"<<<<<<<",
    r"mergeable.*conflicting",
)


def _matches(text: str, patterns: tuple[str, ...]) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def classify_merge_state(
    mergeable: Optional[str],
    merge_state_status: Optional[str],
) -> Optional[ClassificationResult]:
    """Classify branch drift from GitHub PR merge fields."""
    if mergeable and mergeable.upper() == "CONFLICTING":
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="agent",
            strategy="conflict-resolve",
            confidence="high",
            reason="PR mergeable is CONFLICTING",
        )
        return result

    if merge_state_status:
        status = merge_state_status.upper()
        if status == "BEHIND":
            result = ClassificationResult(
                classification="auto-fixable",
                fix_tier="tool",
                strategy="rebase",
                confidence="high",
                reason="mergeStateStatus is BEHIND",
            )
            return result
        if status == "DIRTY":
            result = ClassificationResult(
                classification="auto-fixable",
                fix_tier="agent",
                strategy="conflict-resolve",
                confidence="high",
                reason="mergeStateStatus is DIRTY (merge cannot be cleanly created)",
            )
            return result

    return None


def classify_check(
    check_name: str,
    log_text: str,
    repo_profile: str,
) -> ClassificationResult:
    """Classify a failed CI check name and optional log excerpt."""
    combined = f"{check_name}\n{log_text}"

    if _matches(combined, CONFLICT_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="agent",
            strategy="conflict-resolve",
            confidence="high",
            reason="Conflict markers or merge conflict detected",
        )
        return result

    if _matches(combined, REBASE_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="tool",
            strategy="rebase",
            confidence="high",
            reason="Rebase or non-fast-forward signal detected",
        )
        return result

    if repo_profile == "awesome-cisco-registry":
        if _matches(combined, REGISTRY_PATTERNS):
            result = ClassificationResult(
                classification="auto-fixable",
                fix_tier="tool",
                strategy="registry-regen",
                confidence="high",
                reason="Registry freshness failure",
            )
            return result
        if _matches(combined, MARKETPLACE_PATTERNS):
            result = ClassificationResult(
                classification="auto-fixable",
                fix_tier="tool",
                strategy="marketplace-regen",
                confidence="high",
                reason="Marketplace artifact stale",
            )
            return result
        if _matches(combined, EXTERNAL_SKILLS_PATTERNS):
            result = ClassificationResult(
                classification="auto-fixable",
                fix_tier="agent",
                strategy="external-skills-fix",
                confidence="high",
                reason="External skills scan failure",
            )
            return result

    if _matches(combined, SKILL_SPEC_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="agent",
            strategy="skill-spec-fix",
            confidence="high",
            reason="Skill spec validation failure",
        )
        return result

    if _matches(combined, SECURITY_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="agent",
            strategy="security-fix",
            confidence="high",
            reason="Security scanner finding with actionable output",
        )
        return result

    if _matches(combined, LINT_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="tool",
            strategy="lint-fix",
            confidence="high",
            reason="Lint or format failure",
        )
        return result

    if _matches(combined, TEST_PATTERNS):
        result = ClassificationResult(
            classification="auto-fixable",
            fix_tier="agent",
            strategy="test-fix",
            confidence="high",
            reason="Test failure detected",
        )
        return result

    result = ClassificationResult(
        classification="needs-human",
        fix_tier="agent",
        strategy="unknown",
        confidence="low",
        reason="No matching auto-fix pattern",
    )
    return result


def _read_log_text(log_file: Optional[str], log_text: Optional[str]) -> str:
    if log_text:
        return log_text
    if log_file:
        path = Path(log_file)
        return path.read_text(encoding="utf-8", errors="replace")
    return ""


def result_to_dict(result: ClassificationResult) -> dict[str, str]:
    """Convert a classification result to a JSON-serializable dict."""
    payload = {
        "classification": result.classification,
        "fix_tier": result.fix_tier,
        "strategy": result.strategy,
        "confidence": result.confidence,
        "reason": result.reason,
    }
    return payload


def parse_args(argv: Optional[list[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Classify CI failures for pr-follow-up auto-fix mode.",
    )
    parser.add_argument("--check-name", required=True, help="Failed check name")
    parser.add_argument("--log-file", help="Path to CI log excerpt")
    parser.add_argument("--log-text", help="Inline CI log excerpt")
    parser.add_argument(
        "--repo-profile",
        default="harness-app",
        choices=(
            "harness-app",
            "harness-skills",
            "awesome-cisco-registry",
        ),
        help="Repo CI profile override",
    )
    parser.add_argument("--mergeable", help="GitHub mergeable field value")
    parser.add_argument(
        "--merge-state-status",
        help="GitHub mergeStateStatus field value",
    )
    return parser.parse_args(argv)


def main(argv: Optional[list[str]] = None) -> int:
    """Entry point."""
    args = parse_args(argv)
    log_text = _read_log_text(args.log_file, args.log_text)

    merge_result = classify_merge_state(args.mergeable, args.merge_state_status)
    if merge_result is not None and (args.mergeable or args.merge_state_status):
        output = result_to_dict(merge_result)
        json.dump(output, sys.stdout, indent=2)
        sys.stdout.write("\n")
        return 0

    classification = classify_check(args.check_name, log_text, args.repo_profile)
    output = result_to_dict(classification)
    json.dump(output, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
