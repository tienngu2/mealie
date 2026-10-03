---
name: pr-follow-up
description: Monitor a GitHub pull request after creation, auto-fix mechanical CI failures by default, handle review comments, and report CI success or escalation. Use after a PR is opened in harness repos where agents should keep the PR green without human handoff.
compatibility: Requires gh CLI to be installed and authenticated
metadata:
  version: "1.1.0"
---

# PR Follow-up

Use this skill after a PR already exists. Primary deployment: **downstream AI harness projects** using the `core` APM bundle (`commit-and-push → pr-readiness-gate → create-pull-request → pr-follow-up`).

Default behavior is **auto-fix**: classify CI failures, apply fixes, commit, push, and re-poll until green or escalation. Passive monitoring requires explicit **watch-only** mode.

## Modes

| Mode | Trigger phrases | On CI failure |
| --- | --- | --- |
| `auto-fix` | default; "follow up on the PR", "keep the PR green" | Classify, fix, push, re-poll |
| `watch-only` | "watch the PR", "monitor CI only", "don't fix CI" | Report and stop |

**Default behavior changed:** Auto-fix is now the default. For passive monitoring only (report CI failure and stop), use the watch-only phrases above.

## When To Use

- After `create-pull-request-with-reviewers` in an agent-driven workflow
- "follow up on the PR" / "keep the PR green"
- "watch the PR" (watch-only)
- A PR exists on the current branch

## Inputs

- PR number, PR URL, or current branch with an existing PR

```bash
gh pr view --json number,url,title,headRefName,baseRefName,mergeable,mergeStateStatus
```

## Optional Configuration

Read from repo-root `apm.yml` when present:

```yaml
prFollowUp:
  ciProfile: harness-app | harness-skills | awesome-cisco-registry
  maxAutoFixCommits: 5
  outerCycleLimit: 3
  innerIterationLimit: 6
```

When absent, infer profile from CI workflows and changed paths. See `references/ci-failure-classifier.md`.

## Reference Files

| File | Purpose |
| --- | --- |
| `references/ci-failure-classifier.md` | Check → strategy mapping by repo profile |
| `references/ci-fix-loop-protocol.md` | Loop limits, push protocol, termination |
| `references/test-fix-validity.md` | Valid vs invalid test fixes |
| `references/security-fix-validity.md` | Valid vs invalid security fixes |
| `scripts/classify_ci_failure.py` | Optional JSON classifier helper |

## Workflow Overview

### 1. Identify the PR and mode

```bash
gh pr view --json number,url,title,headRefName,baseRefName,mergeable,mergeStateStatus,statusCheckRollup,reviewThreads
gh pr checks <PR_NUMBER>
```

Load limits from `apm.yml` or defaults: inner 6, outer 3, max 5 `[pr-follow-up]` commits.

### 2. Baseline snapshot

Track:

- unresolved review thread ids
- failing/pending checks
- merge state (`BEHIND`, `DIRTY`, `CONFLICTING` on `mergeable`)
- auto-fix commit count

### 3. Poll loop

Poll every 60–120 seconds (default timeout 30 minutes).

Each cycle:

1. Check merge state — fix drift before waiting on CI (see `references/ci-fix-loop-protocol.md`)
2. Poll `gh pr checks` and review threads
3. On CI failure in **auto-fix** mode → enter fix loop (step 4)
4. On CI failure in **watch-only** → report and stop
5. On CI green → if merge blocked by reviews/branch protection, report and stop; else success

### 4. Auto-fix loop (auto-fix mode only)

1. **Fetch logs**: `gh run view <RUN_ID> --log-failed`
2. **Classify**: `references/ci-failure-classifier.md` or:

```bash
python3 skills/pr-follow-up/scripts/classify_ci_failure.py \
  --check-name "<CHECK_NAME>" \
  --log-file /tmp/ci.log \
  --repo-profile harness-app
```

3. If `needs-human` → escalation report and stop
4. **Apply fix** by strategy (tool or agent tier)
5. **Validity gates** for `test-fix` and `security-fix` — see reference files; invalid → escalate without commit
6. **Local validation** — rerun smallest relevant command before commit
7. **Commit** with `[pr-follow-up]` prefix — no confirmation prompt in auto-fix mode
8. **Push**: plain `git push`, or `git push --force-with-lease` after rebase on already-pushed branch
9. Follow `commit-and-push-changes` staging/exclusion rules for file selection
10. Re-poll CI; repeat until green, limit hit, or escalation

### 5. Fix strategies (summary)

| Strategy | Tier | Action |
| --- | --- | --- |
| `lint-fix` | tool | eslint/ruff/prettier `--fix` |
| `test-fix` | agent | Fix code or test + validity gate |
| `security-fix` | agent | Apply remediation + `codeguard` rules + validity gate + rescan |
| `skill-spec-fix` | agent | Fix SKILL.md; rerun `agentskills validate` |
| `registry-regen` | tool | `python3 scripts/generate-registry.py` |
| `marketplace-regen` | tool | `apm pack --marketplace=claude` |
| `rebase` | tool | fetch + rebase onto base |
| `conflict-resolve` | agent | resolve markers + rerun checks |
| `external-skills-fix` | agent | fix external-skills entry + rescan (registry profile) |

### 6. Skill Scanner context

Skill Scanner runs only when the **consumer repo wired it into CI** and the PR **touches skill paths**. Application-only PRs typically skip it. Findings usually mean the agent authored unsafe skill content — fix via `security-fix` strategy, not escalation by default.

### 7. Review comments during auto-fix

When new review threads appear during auto-fix:

1. Log a summary of new comments
2. **Continue CI auto-fix by default** — do not block on user confirmation
3. Offer to pivot to review-comment fixes only if the user explicitly asks
4. After CI is green or on escalation, offer to address review comments using `gh-pr-comment-resolution`

In **watch-only** mode, follow the original interactive flow: ask before applying review fixes.

### 8. Review comments (watch-only or user pivot)

1. Fetch threads via `gh-pr-comment-resolution` / GraphQL
2. Summarize to user; ask whether to apply fixes
3. After fixes, ask whether to resolve threads
4. Resolve with `resolveReviewThread` mutation

```bash
gh repo view --json owner,name
gh api graphql -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:50){nodes{id,isResolved,comments(first:20){nodes{id,body,author{login},path,position}}}}}}}' -f owner='<OWNER>' -f repo='<REPO>' -F number=<PR_NUMBER>
```

## Stop Conditions

| Condition | Action |
| --- | --- |
| All checks pass, mergeable | Report success |
| Checks pass, merge blocked | Report CI success + merge blocker |
| watch-only + CI failure | Report and stop |
| needs-human / invalid fix | Escalation report |
| Inner stall / outer limit / commit cap | Escalation report |
| Poll timeout | Report timeout state |

## Escalation Report

```markdown
## PR Follow-up — CI auto-fix stopped

PR: #<number>
Mode: auto-fix
Cycles completed: <n>/<max>
Auto-fix commits: <n>/5
Last failed check: <name>
Stop reason: <stall|limit|invalid-fix|needs-human|merge-blocked|success|timeout>

### Auto-fixed in this session
- <check>: <commit/message>

### Remaining (needs human)
- <check>: <reason>

### Suggested next step
<one concrete action>
```

## Reporting Format

When monitoring starts:

```markdown
Watching PR #<number>: <title> (mode: auto-fix)
```

When CI succeeds:

```markdown
PR #<number> checks passed.
Auto-fix commits: <n>
```

## Companion Skills

- `commit-and-push-changes` — staging and commit message conventions (extended for unattended auto-fix)
- `gh-pr-comment-resolution` — review thread fetch/resolve
- `pr-readiness-gate` — optional post-fix gate when installed
- `create-pull-request-with-reviewers` — runs before this skill

## Guardrails

- Do not use plain `git push --force` — only `--force-with-lease` after rebase
- Do not skip git hooks without user approval
- Do not disable CI jobs or suppress security findings to greenwash CI
- Do not weaken or skip tests to pass CI
- Do not modify files outside PR/failure scope
