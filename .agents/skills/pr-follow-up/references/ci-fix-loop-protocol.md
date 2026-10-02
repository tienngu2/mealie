# CI Fix Loop Protocol

Post-PR auto-fix loop for `pr-follow-up`. Differs from `code-review/references/fix-loop-protocol.md`:

- **Commits and pushes** after local validation (code-review stages only)
- Adds **outer CI cycles**, **commit cap**, and **validity gates** for tests/security

## Limits

| Limit | Default | Override via `apm.yml` |
| --- | --- | --- |
| Inner iterations per failure | 6 | `prFollowUp.innerIterationLimit` |
| Outer CI cycles (push→CI→fix) | 3 | `prFollowUp.outerCycleLimit` |
| Max `[pr-follow-up]` commits | 5 | `prFollowUp.maxAutoFixCommits` |

Stop when **any** limit is hit.

## Fix Tiers

### Tool tier (deterministic)

| Strategy | Action |
| --- | --- |
| `lint-fix` | Run tool `--fix` on affected files only |
| `registry-regen` | `python3 scripts/generate-registry.py` |
| `marketplace-regen` | `apm pack --marketplace=claude` |
| `rebase` | `git fetch origin && git rebase origin/<base>` |

### Agent tier (requires judgment + validity gate)

| Strategy | Gate |
| --- | --- |
| `test-fix` | `test-fix-validity.md` |
| `security-fix` | `security-fix-validity.md` |
| `skill-spec-fix` | Rerun `agentskills validate` locally |
| `conflict-resolve` | Rerun impacted tests/lint after rebase |
| `external-skills-fix` | Rerun scanner on affected path if available |

## Loop Mechanics

```
outer_cycle = 0
auto_fix_commits = 0

while outer_cycle < outer_cycle_limit and auto_fix_commits < max_commits:
    poll PR checks and merge state
    if merge drift (BEHIND/CONFLICTING): fix before CI
    if CI pending: wait and continue
    if CI all green:
        if merge blocked by policy: report and stop
        else: report success and stop

    classify failure → auto-fixable or needs-human
    if needs-human: escalate and stop

    inner_iteration = 0
    while inner_iteration < inner_iteration_limit:
        inner_iteration += 1
        apply fix (tool or agent + validity gate)
        rerun smallest local validation for failure class
        if clean: break inner loop
        if stalled: escalate and stop

    commit with [pr-follow-up] prefix (no confirmation in auto-fix mode)
    auto_fix_commits += 1
    push (plain git push, or --force-with-lease if rebased after prior push)
    outer_cycle += 1
    poll CI until complete or timeout
```

## Push Protocol

Follow `commit-and-push-changes` staging and exclusion rules (exclude `.cursor/`, etc.).

| Situation | Push command |
| --- | --- |
| Normal fix commit | `git push` |
| After rebase on already-pushed branch | `git push --force-with-lease` |

In **auto-fix** mode: do **not** prompt "Proceed with commit? [Y/n]".

In **watch-only** mode: never commit or push.

## Local Validation Before Push

Rerun the smallest command for the failure class:

| Failure | Local rerun |
| --- | --- |
| lint-fix | Same linter on changed files |
| test-fix | Failing test file/module + standard test cmd when feasible |
| security-fix | Same scanner command CI used |
| skill-spec-fix | `agentskills validate <dir>` |
| registry-regen | `git diff docs/skills.json` sanity check |
| rebase/conflict | Impacted lint or test command |

Optionally invoke `pr-readiness-gate` when installed; local reruns are the minimum bar.

## Termination

| Condition | Stop reason |
| --- | --- |
| All checks pass, mergeable | `success` |
| Checks pass, merge blocked | `merge-blocked` |
| needs-human classification | `needs-human` |
| Invalid test/security fix | `invalid-fix` |
| Inner stall | `stall` |
| Outer/inner/commit limit | `limit` |
| Poll timeout | `timeout` |

## Session Log

Track per iteration: check name, strategy, files changed, local validation command, pass/fail, commit SHA.

## Guardrails

1. Only modify files implicated by the failure or PR diff scope.
2. Never use `ruff check --unsafe-fixes` or equivalent unsafe auto-fix flags.
3. Never disable CI jobs or add suppress directives to pass security scans.
4. Never plain `git push --force` — use `--force-with-lease` only after rebase.
5. Prefix every auto-fix commit: `[pr-follow-up] <description>`.
