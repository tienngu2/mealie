# APM management

[APM](https://github.com/microsoft/apm) delivers the agent skills in this repository. `apm.yml` is the manifest, `apm.lock.yaml` the lockfile.

## Installed packages

- `skills/ai-native-assessment`, `skills/ai-harness-setup` (from `cisco-genai/awesome-cisco`)
- `packages/stack-python-uv` v1.0.5 and `packages/stack-javascript-typescript` v1.0.5 (code review, security review, codeguard, PR and commit helpers, language best-practice skills, and more)

Targets: `claude`, `copilot`, `cursor`, `codex`. Deployed files appear in `.agents/skills/`, `.claude/skills/`, `.github/skills/`, `.github/prompts/`, and `.cursor/`. OpenSpec adds its own commands and skills to the same places.

## Commands

```bash
apm install                         # sync everything in apm.yml (run after pulling)
apm install -t claude,copilot,cursor,codex <package>   # add a package (use one comma-separated -t; repeated --target keeps only the last)
```

Requires `gh` authenticated with access to the private `cisco-genai` org (account `tienngu2_cisco`).

## Rules

- Commit deployed skill files and `apm.lock.yaml`; do not commit `apm_modules/` (gitignored).
- Do not hand-edit deployed skills; change `apm.yml` and re-run `apm install`.
- These folders are excluded from ruff in `pyproject.toml` because they hold third-party code.
- `accelint-ts-best-practices` is TypeScript-oriented and only loosely relevant (see [tech debt](../tech-debt.md)).
