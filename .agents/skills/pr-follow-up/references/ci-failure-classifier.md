# CI Failure Classifier

Maps failed PR checks and merge state to fix strategies for `pr-follow-up` auto-fix mode.

## Repo CI Profiles

Detect profile before classifying. Use repo `apm.yml` `prFollowUp.ciProfile` when set; otherwise infer:

| Profile | Signals |
| --- | --- |
| `harness-app` | Standard lint/test/build CI; no skill-scanner or registry jobs |
| `harness-skills` | Skill paths in PR diff + skill-scanner or `agentskills validate` in CI |
| `awesome-cisco-registry` | `scripts/generate-registry.py`, `docs/skills.json`, `.github/workflows/ci.yml` skill jobs |

## Classification Output

Each failure resolves to:

```json
{
  "classification": "auto-fixable|needs-human",
  "fix_tier": "tool|agent",
  "strategy": "<strategy-id>",
  "confidence": "high|low"
}
```

Optional helper:

```bash
python3 skills/pr-follow-up/scripts/classify_ci_failure.py \
  --check-name "Skill Spec Compliance" \
  --log-file /tmp/ci.log \
  --repo-profile awesome-cisco-registry
```

## Harness App (default)

| Check / log signal | Tier | Strategy |
| --- | --- | --- |
| ruff, eslint, prettier, lint, format | tool | `lint-fix` |
| pytest, jest, vitest, junit, test failed | agent | `test-fix` |
| build, compile, typecheck (non-lint) | agent | `test-fix` or needs-human if no clear fix |
| Semgrep, SAST with file+rule+line | agent | `security-fix` |

## Harness + Skills

All harness-app rows, plus:

| Check / log signal | Tier | Strategy |
| --- | --- | --- |
| Skill Scanner, skill-scanner, Cisco AI Defense | agent | `security-fix` |
| agentskills validate, Skill Spec Compliance | agent | `skill-spec-fix` |

Skill Scanner runs only when CI is wired **and** skill paths changed. Application-only PRs skip it.

## Awesome-Cisco Registry Profile

All harness-skills rows, plus:

| Check / log signal | Tier | Strategy |
| --- | --- | --- |
| `docs/skills.json`, generate-registry, not found in registry | tool | `registry-regen` |
| validate-packages, marketplace.json, apm pack | tool | `marketplace-regen` |
| scan-external-skills, external-skills.json | agent | `external-skills-fix` |

Reference workflows:

| Workflow | Job |
| --- | --- |
| `.github/workflows/ci.yml` | `validate-skills`, `validate-registry`, `skill-scanner`, `scan-external-skills` |
| `.github/workflows/validate-packages.yml` | `validate` (marketplace artifact) |

## Merge State (all profiles)

Use `gh pr view <N> --json mergeable,mergeStateStatus,baseRefName,headRefName`:

| Signal | Field | Tier | Strategy |
| --- | --- | --- | --- |
| Branch behind base | `mergeStateStatus=BEHIND`, mergeable | tool | `rebase` |
| Merge cannot be cleanly created | `mergeStateStatus=DIRTY` | agent | `conflict-resolve` |
| Merge conflicts | `mergeable=CONFLICTING` | agent | `conflict-resolve` |
| Push non-fast-forward | push rejected | tool → agent | `rebase` then `conflict-resolve` |

## Needs-Human (all profiles)

| Signal | Why |
| --- | --- |
| Unknown check name + no log match | Cannot infer safe fix |
| Fix loop stall | No progress after inner iterations |
| Test fix invalid | See `test-fix-validity.md` |
| Security fix invalid | See `security-fix-validity.md` |
| CI green, merge blocked | Required reviews, branch protection, merge queue |
| No remediation after N security attempts | Cannot determine safe path |

## Fetching Failure Details

```bash
gh pr checks <PR_NUMBER>
gh run list --branch "$(git branch --show-current)" --limit 5
gh run view <RUN_ID> --log-failed
```

For Code Scanning annotations, also inspect SARIF or PR Checks API output for rule ID and remediation text.
