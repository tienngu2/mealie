# AI Harness Setup

Use `ai-harness-setup` to bootstrap a repository for agent-driven engineering. The skill inspects the full tech stack first, then sets up APM, spec-driven development (OpenSpec by default, or the repo's existing system), deterministic checks with CI wiring, Dependabot, AI workflow and security skills, MCP servers matched to the stack, workflow documentation, and AI IDE configuration for every tool the team uses — finishing with a mandatory harness verification pass.

## Two Installation Options

You can install this skill with either `apm` or `npx skills`.

## Private Repository Access Prerequisites

Before installing from `cisco-genai/awesome-cisco`, make sure your GitHub account has access to the `cisco-genai` org and that your token is authorized for it.

1. Join one Cisco MyID group:
   - Cisco IT users: [emu-org-cisco-it-group](https://myid-groups.cisco.com/group-details/name/emu-org-cisco-it-group)
   - Everyone else: [emu-org-cisco-genai-contributors](https://myid-groups.cisco.com/group-details/name/emu-org-cisco-genai-contributors)
2. Create a GitHub personal access token:
   - Fine-grained PAT: [github.com/settings/personal-access-tokens/new](https://github.com/settings/personal-access-tokens/new)
   - Classic PAT: [github.com/settings/tokens/new](https://github.com/settings/tokens/new)
3. Set the token locally:

```bash
export GITHUB_TOKEN=<your_pat>
```

4. Authorize the PAT for the `cisco-genai` org in GitHub:
   - Manage tokens: [github.com/settings/tokens](https://github.com/settings/tokens)
   - If your token shows `Configure SSO`, use it and authorize the token for `cisco-genai`.

## Option 1: Install With APM

Use this option when you want the skill managed as a dependency and deployed to one or more supported targets.

### Prerequisites

- Install APM if needed: `curl -sSL https://aka.ms/apm-unix | sh`
- Verify APM: `apm --version`
- Initialize APM in the repo if needed: `apm init --yes`

### Install The Skill

```bash
apm install cisco-genai/awesome-cisco/skills/ai-harness-setup -t opencode -t cursor -t copilot -t claude -t windsurf
```

Notes:

- Adjust the `-t` targets to match the tools your team uses. Supported targets: `opencode`, `cursor`, `copilot`, `claude`, `windsurf`.
- For OpenCode only, `-t opencode` is enough.
- For private repository access, ensure `GITHUB_TOKEN` is exported in your shell before running `apm install`.

### Verify The Install

```bash
apm deps list
apm deps tree
```

## Option 2: Install With `npx skills`

Use this option when you want to add the skill directly from the repository without managing it through APM.

```bash
npx skills add https://github.com/cisco-genai/awesome-cisco --skill ai-harness-setup
```

You can verify the CLI and installed skills with:

```bash
npx skills --version
npx skills list
```

## What The Skill Helps Set Up

1. **Stack detection** — inspects manifests, lockfiles, CI configs, and existing docs before making any changes
2. **APM** — skill and dependency delivery layer; initializes `apm.yml` and keeps the lockfile aligned
3. **Spec-driven development** — OpenSpec by default, or respects SpecKit, BMAD, or any existing system
4. **Deterministic checks** — type checking, linting, testing, security scanning, and build verification matched to the detected stack, with CI wiring for the detected CI system (for example, GitHub Actions, Jenkins, or GitLab CI)
5. **Dependabot** — automated dependency updates for each detected ecosystem
6. **AI tooling and skills** — workflow skills (PRs, review, reflection), security review rules, and stack-specific skills installed via APM; optional GitHub Agentic Workflows; MCP servers matched to the repo's stack
7. **Docs tree** — architecture, dev environment, validation, deployment, and workflow docs derived from the actual repo; `AGENTS.md` as a lean routing file; `CONTRIBUTING.md` updated to reference the docs
8. **AI IDE configuration** — Copilot, Cursor, Windsurf, Claude Code, and OpenCode surfaces configured for whichever tools the team uses
9. **Finalize APM state** — runs `apm install` to sync `apm_modules/`, lockfile, and all deployed files; commits `apm.yml`, `apm.lock.yaml`, and all deployed skill/prompt surfaces so every contributor gets agent context without running `apm install`
10. **Harness verification** — mandatory audit of the full changeset to close any gaps before finishing

## How To Invoke It

Different AI tools expose installed skills differently.

### GitHub Copilot Chat / Cursor / Claude Code / Windsurf

```text
/ai-harness-setup
```

### OpenCode

```text
Use the ai-harness-setup skill for this repository.
```

## Typical Outcomes

Depending on what the repository already contains, this skill may create or update:

- `apm.yml` and `apm.lock.yaml`
- GitHub Agentic Workflow files (`.github/workflows/`) when the team opts in
- `openspec/` (or documentation of the existing spec system)
- deterministic check configs and matching CI stages
- `.github/dependabot.yml`
- `.github/`, `.claude/`, `.opencode/`, `.cursor/`, or `.windsurf/` skill and prompt surfaces
- `docs/` tree with real content derived from the repo
- `AGENTS.md` and `CONTRIBUTING.md`

## Good Times To Use It

- When starting AI workflow adoption in an existing repo
- When bootstrapping a new repo for agent-assisted development
- When standardizing repo setup across multiple AI IDEs
- Before running an `ai-native-assessment`
