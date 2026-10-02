# Test Fix Validity Gate

Every proposed test fix must be classified **valid** or **invalid** before commit in auto-fix mode. Invalid fixes escalate even if they would pass locally.

## Root Cause Diagnosis

Pick one before fixing:

| Root cause | Valid fix path |
| --- | --- |
| PR introduced logic bug | Fix **implementation** |
| Test outdated vs intentional PR change | Update **test expectations** with rationale |
| Fixture/setup/import drift from PR | Fix test infrastructure |
| Flaky repro locally | Stabilize setup; do not skip |

## Valid Fixes

- Correct implementation bug exposed by assertion
- Update expectations when PR intentionally changed behavior and test was stale
- Fix fixtures, imports, types, or test data caused by PR diff
- Regenerate snapshots when output change is intentional and documented

## Invalid Fixes (reject — escalate)

- Remove or weaken assertions (delete expects, broaden matchers)
- Skip/disable tests (`skip`, `xit`, `xfail`, `@pytest.mark.skip`) without tracked external blocker
- Mock/stub/spy away the behavior under test
- Change test to encode objectively wrong implementation behavior
- Delete failing test files or cases to reduce failure count
- Catch and swallow errors the test was meant to surface

## Regression Checks (required before commit)

1. Rerun originally failing test(s)
2. Rerun full test file or module
3. Rerun repo standard test command when feasible
4. Diff test changes: flag if assertion count decreased or skip/todo increased
5. Log: root cause, valid/invalid, one-line rationale

## Escalation Message

```markdown
Test fix classified **invalid** — not committed.

Failed check: <name>
Proposed change: <summary>
Reason: <e.g., assertions removed, tests skipped>

Suggested next step: <manual fix guidance>
```
