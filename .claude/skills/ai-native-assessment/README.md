# AI-Native Assessment

Use `ai-native-assessment` to evaluate how AI-native a repository is. The skill first scans the repo for AI primitives - spec-driven development, deterministic checks, AI skills, documentation, IDE and coding-agent configuration, and agentic legibility - and uses that evidence to produce a scored markdown report with prioritized recommended actions.

Visit the [AI-Native Maturity Leaderboard](https://cisco-genai.github.io/ai-native-maturity-leaderboard) to view how repositories compare.

## Two Installation Options

You can install this skill with either `apm` or `npx skills`.

## Private Repository Access Prerequisites

Before installing from `cisco-genai/awesome-cisco`, make sure your GitHub account has access to the `cisco-genai` org and that your token is authorized for it.

1. Join one of the below Cisco MyID groups:
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
apm install cisco-genai/awesome-cisco/skills/ai-native-assessment -t opencode -t cursor -t copilot
```

Notes:

- Adjust the `-t` targets to match the tools you use.
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
npx skills add https://github.com/cisco-genai/awesome-cisco --skill ai-native-assessment
```

You can verify the CLI and installed skills with:

```bash
npx skills --version
npx skills list
```

## How To Invoke It

Some AI CLIs expose installed skills as slash commands. When they do, prefer invoking `ai-native-assessment` that way.

### OpenCode

```text
Use the ai-native-assessment skill for this repository.
```

### Cursor

```text
/ai-native-assessment
```

### GitHub Copilot Chat

```text
/ai-native-assessment
```

### Claude Code

```text
/ai-native-assessment
```

### Codex

```text
Use the ai-native-assessment skill for this repository.
```

## Bundled Detection Script

The skill includes `scripts/detect.py` for fast deterministic discovery.

Default mode returns candidates, selected commands, additional scans, category signals, and AI validation hints so the model can make the scoring decisions:

```bash
python3 scripts/detect.py <repo_root>
```

If you want the script to also include deterministic category scores and recommended actions, opt in explicitly:

```bash
python3 scripts/detect.py <repo_root> --with-scoring
```

Run the focused detector regression tests with:

```bash
python3 scripts/test_detect.py
```

### OpenSpec Stores

When the target repository selects a store with `store:` or declares stores
under `references:` in `openspec/config.yaml`, the assessment includes
applicable evidence from those configured stores. This supports centralized
development models where specifications, skills, agent instructions, and
workflow documentation are maintained once instead of copied into every child
repository.

The assessed repository remains the unit of scoring. The detector:

- follows only stores explicitly configured by the target;
- validates store metadata and health;
- counts applicable store evidence without a locality penalty;
- scores maturity and documentation sub-metrics from the strongest complete
  evidence root instead of combining partial signals across roots;
- ignores unrelated registered stores;
- de-duplicates skills shared across roots;
- identifies stores by id in reportable evidence without exposing local paths;
- keeps target-specific checks, stack relevance, and codebase properties tied
  to the target unless a shared asset demonstrably operates on it.

This changes evidence discovery only. The six categories, 38 sub-metrics,
weights, formulas, tier thresholds, scorecard structure, and leaderboard data
contract remain unchanged.

## Typical Outputs

Depending on the repository's current state, the skill produces:

- `docs/ai-native-scorecard.md` — the completed scorecard, formatted to match `templates/ai-native-scorecard.md`, with per-sub-metric scores, category averages, composite score, and tier assignment
- A prioritized list of recommended actions ordered by composite impact
- An optional pull request to the [AI-Native Maturity Leaderboard](https://cisco-genai.github.io/ai-native-maturity-leaderboard)

## What The Skill Does

The assessment evaluates six weighted categories and computes a composite score on a 0–4 scale:

| # | Category | Weight |
|---|----------|--------|
| 1 | Spec-Driven Development | 20% |
| 2 | Deterministic Checks | 25% |
| 3 | AI Tooling & Skills | 15% |
| 4 | Documentation Tree | 15% |
| 5 | AI IDE Configuration | 10% |
| 6 | Agentic Legibility | 15% |

The Spec-Driven Development category is tool-agnostic. It recognizes the major SDD frameworks — OpenSpec, SpecKit, BMAD (BMAD-METHOD), and GSD (Git. Ship. Done.) — and also scores generic, homegrown, or other spec-driven workflows (for example, a `specs/` directory holding real planning artifacts). Every framework is evaluated on the same rubric, and no tool is favored or can reach a higher score than another. The score reflects the substance of the work — that a system exists, work items carry complete planning artifacts, the workflow is used, and it is documented — not which tool produced it.

Based on the composite score, the repository is assigned a maturity tier:

| Composite Score | Tier |
|-----------------|------|
| 0.0 – 0.9 | Unaware |
| 1.0 – 1.9 | Nascent |
| 2.0 – 2.9 | Structured |
| 3.0 – 3.5 | Established |
| 3.6 – 4.0 | Exemplary |

The skill writes a completed scorecard to `docs/ai-native-scorecard.md` using the exact section and table structure from `templates/ai-native-scorecard.md`, and optionally submits it to the leaderboard via a pull request.

## Good Times To Use It

- After running `ai-harness-setup` to verify and measure what was set up
- Before starting AI workflow improvements to establish a baseline
- Periodically to track maturity progress over time
- When onboarding a repo into an AI-native engineering practice
