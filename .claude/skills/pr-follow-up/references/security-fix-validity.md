# Security Fix Validity Gate

Security findings from Skill Scanner, Semgrep, or similar CI checks are auto-fixable in agent tier — but must pass this gate before commit.

## When Skill Scanner Fires

Only when **both**:

1. Consumer repo wired `skill-scanner` into CI
2. PR touches skill paths (`skills/`, `.github/skills/`, etc.)

Application-only PRs typically never hit this check.

## Root Cause Diagnosis

| Root cause | Valid fix path |
| --- | --- |
| Unsafe shell/subprocess in skill script | Parameterized API; no shell interpolation |
| Prompt-injection pattern in SKILL.md | Rewrite instructions safely |
| Hardcoded secret in skill content | Remove; use env reference |
| Missing compatibility declaration | Add accurate frontmatter |
| SARIF/log includes remediation | Apply as documented |

## Valid Fixes

- Apply scanner-provided `remediation` text
- Refactor code to remove flagged pattern (not hide it)
- Sanitize SKILL.md instructions triggering static rules
- Replace exfil-prone shell pipelines with safe library calls
- Apply `codeguard` rules from `core` when crafting the fix. Do not trade one vulnerability for another.
- Rerun scanner locally before push when available:

```bash
pip install cisco-ai-skill-scanner==2.0.6  # when not installed
skill-scanner scan <skill-dir> --fail-on-severity high
```

## Invalid Fixes (reject — escalate)

- Disable, delete, or comment out the CI security job
- Add ignore/suppress without fixing root cause (`# nosec`, `# noqa: security`, allowlists for this finding only)
- Delete flagged file instead of fixing (when capability still needed)
- Obfuscate pattern to evade YARA without changing unsafe behavior
- Remove security-relevant validation logic to pass scan

## Verification Before Commit

1. Rerun same scanner command CI used (or closest local equivalent)
2. Confirm original rule ID no longer fires on changed files
3. Confirm no new HIGH/CRITICAL findings in same files
4. Log: rule ID, root cause, valid/invalid, remediation applied

## Escalation Message

```markdown
Security fix classified **invalid** — not committed.

Rule: <rule_id>
File: <path>
Proposed change: <summary>
Reason: <e.g., suppress-only diff, scanner disabled>

Suggested next step: <manual remediation guidance>
```
