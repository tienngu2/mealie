---
name: ai-native-assessment
description: Evaluate and score how AI-native a repository is. Checks for the existence and maturity of AI primitives -- spec-driven development, deterministic checks, AI skills, documentation, IDE configuration, and agentic legibility -- and produces a scored markdown report with prioritized recommended actions. Visit https://cisco-genai.github.io/ai-native-maturity-leaderboard to view the leaderboard!
compatibility: Works on any repository with local filesystem access.
metadata:
  version: "1.2"
---

# AI-Native Assessment

Use this skill to evaluate any repository's AI-native maturity. The workflow starts with deterministic candidate and evidence discovery, then uses the LLM to score the repository. The bundled scanner can also emit deterministic scores when explicitly requested.

## When To Use It

- When asked whether a repo is AI-native or AI-ready
- When measuring the impact of an `ai-harness-setup` bootstrap
- When comparing repositories for AI-native maturity
- When creating a baseline score before workflow improvements
- When you need a prioritized backlog of AI-native improvements

## Inputs

- The target repository

## Reference Files

- `references/scoring-framework.md` -- graduated rubric for all six categories and their sub-metrics
- `references/detection-signals.md` -- filesystem and tooling signals for detecting AI primitives
- `references/agentic-legibility-framework.md` -- full 9-dimension rubric for Category 6 (Agentic Legibility)

## Output Template

- `templates/ai-native-scorecard.md` -- structure for the final scorecard written to `docs/ai-native-scorecard.md`
- `templates/agentic-legibility-scorecard.md` -- template for the legibility sub-assessment section

## Workflow

### Phase 1: Deterministic Detection (Zero Cost)

Run the bundled detection script to gather all signals, candidates, and evidence deterministically:

```bash
python3 scripts/detect.py <repo_root>
```

If you want the script to also emit its deterministic score payload, use:

```bash
python3 scripts/detect.py <repo_root> --with-scoring
```

This produces a JSON object with:
- Language and package manager detection
- All tool candidates (lint/test/build/format/typecheck) with priority ranking and source provenance
- Additional scan candidates (security, boundary, duplication, dead code, API contracts, infra, container, coverage)
- Selected commands (best picks per kind)
- Evidence-rich category signals for all six categories
- Evidence from healthy OpenSpec stores explicitly configured by the target repository
- AI validation staging (ambiguous commands, review suggestions)

When `--with-scoring` is used, the JSON additionally includes:
- Category 1-5 deterministic scores and Category 6 partial deterministic scores (8/18 sub-metrics)
- Composite score and tier assignment
- Recommended actions

Parse the JSON output and use it as the foundation for Phase 2. Default mode is preferred when the model should own the final scoring decisions.

**If the script fails**, fall back to the full LLM-based detection workflow below (steps 1-2).

### OpenSpec Store Context

The assessed repository remains the scoring target. When its
`openspec/config.yaml` or `openspec/config.yml` selects a store with `store:`
or declares stores under `references:`, treat those configured stores as
delegated assessment context:

1. Resolve the relationship with `openspec context --json` when the CLI is
   available. The bundled detector can also read the first-party local store
   registry when the target does not install OpenSpec itself.
2. Include only stores explicitly selected or referenced by the target. Never
   scan every store returned by `openspec store list`.
3. Require valid store metadata and a healthy OpenSpec root. Ignore missing or
   unhealthy stores and record the resolution problem as evidence.
4. Inspect applicable store specifications, skills, agent configuration, and
   documentation using the existing category criteria. An archive-only store
   can demonstrate a mature lifecycle when completed changes are intentionally
   archived before publication; a live change is not required.
5. Judge relevance against the assessed repository. Store work items, checks,
   commands, MCP servers, or stack-specific skills count only when they apply
   to the target, not merely because they exist in the store repository.
6. Keep the existing categories, sub-metrics, weights, formulas, tiers, and
   scorecard structure unchanged.

### Phase 2: LLM Repo Scan and Deep Scoring

Phase 1 provides the structural foundation (what tools exist, what's configured, what's in CI). Phase 2 is where the LLM **reads actual code and content** to assess quality, consistency, and legibility - things a filesystem scan cannot determine.

Using the Phase 1 JSON as starting context, the LLM must read the target
repository and locally resolve any configured OpenSpec store ids cited in
category evidence:

1. **Scan representative source files** — read 5-10 source files across the codebase to assess:
   - Naming consistency and semantic clarity
   - Code comment quality and coverage
   - Error handling patterns
   - Type annotation depth beyond just "typecheck exists"
   - Architecture clarity (can an agent understand the boundaries?)

2. **Assess documentation quality** — read the actual content of AGENTS.md, CONTRIBUTING.md, README.md, and docs/ files to evaluate:
   - Is the documentation actionable for an AI agent, or just boilerplate?
   - Are onboarding paths clear?
   - Are invariants and constraints documented?
   - Is the dependency graph explained?
   - When guidance is centralized in a configured store, does it apply to and
     accurately route work for the assessed repository?

3. **Score Category 6 deep sub-metrics** — the 10 sub-metrics requiring content reasoning:
   - Semantic naming quality, API documentation clarity, error handling legibility, code comment informativeness, type coverage depth, dependency documentation, architecture explainability, onboarding path clarity, debug affordances, change impact clarity
   - Score each using `references/agentic-legibility-framework.md`

4. **Score the categories, or validate deterministic scores if present** - use Phase 1 evidence plus direct file reads:
    - A linter may exist but be misconfigured or have all rules disabled
    - A docs/ directory may exist but contain only stubs
    - Skills may be installed but poorly written
    - Store-provided skills and agent configuration receive the same credit as
      local equivalents when they apply to the assessed repository
    - Shared validation commands count only when they execute against the
      assessed repository; checks for the store's own code do not transfer
    - For Category 1 system and artifacts, award 4 only when one applicable
      evidence root has a recognized system, multiple complete work items,
      observable completion on at least one of those complete work items,
      recent spec activity, a passing status/check when its CLI is available,
      and workflow integration documented for contributors or agents
    - Interpret complete work items using the detected system's equivalent
      artifact structure. Do not require OpenSpec-style proposal/design/tasks
      files from SpecKit, BMAD, GSD, or another established workflow
    - Workflow integration requires affirmative, actionable SDD guidance or
      commands in a supported instruction surface such as `CONTRIBUTING.md`,
      `AGENTS.md`, `CLAUDE.md`, or `.github/copilot-instructions.md`. A bare
      mention of specs, API specifications, or a negative instruction such as
      "must not use OpenSpec" or "should not follow BMAD" does not satisfy the
      score-4 gate
    - When an installed CLI has no supported read-only repository status/check,
      treat validation as unverified until direct evidence establishes it; do
      not silently waive the score-4 validation gate
    - A current active change is optional. Archive-only main branches qualify
      when the evidence above shows an intentional archive-before-merge
      lifecycle; unrelated active store changes do not strengthen the target
    - For each healthy configured OpenSpec store, require
      `openspec validate --all --json --store <id>` to pass before satisfying
      the score-4 CLI validation gate. A validation failure does not discard
      otherwise applicable store evidence, but its sanitized error must be
      reported
    - When `--with-scoring` was used, adjust scores with evidence when the deterministic signal overstates or understates reality
    - **Review `ai_validation.evidence_gaps` when present** - these are sub-metrics where capability is present but strictness was not mechanically proven. For each gap:
      - Read the relevant CI config (Jenkins, GitHub Actions, etc.) to verify enforcement
      - Check if the validate/precommit scripts wire the check correctly
      - Confirm or adjust the score with evidence

5. **Validate CI pipeline alignment** — the deterministic scan detects CI keywords but cannot parse pipeline structure. The LLM should:
   - Read CI config files (Jenkinsfile, GitHub Actions, etc.) to confirm checks actually run and fail the build
   - Compare the CI capabilities to the local validate command — are they aligned?
   - Verify parallelized stages are still enforcing (not `continue-on-error: true`)
   - Check if coverage gates, lint strictness, or SAST are wired into CI with proper fail conditions

6. **Resolve ambiguous command selections** — review `ai_validation.ambiguous_commands` and select the correct command if the priority-based selection was wrong

The LLM receives structured evidence from Phase 1 (not starting from scratch), reducing token cost by ~80% while still performing a thorough qualitative assessment.

### Fallback: Full LLM Detection

If Phase 1 is unavailable, use the following parallelized detection workflow:

### Parallelization

Use subagents whenever possible to parallelize independent detection and scoring work. The detection phase (step 1) is highly parallelizable -- launch separate subagents for spec-driven development detection, deterministic checks detection, AI skills + documentation detection, and AI IDE + tech stack detection. These four detection streams have no dependencies on each other and should run concurrently. The scoring phase (step 2) depends on detection results, so it runs after detection completes, but the agentic legibility assessment (Category 6) can run in parallel with the other category scoring since it uses its own independent framework (`references/agentic-legibility-framework.md`).

### 1. Detect the Repo's Stack and AI Primitives

Before scoring, scan the repository to identify what exists. Read `references/detection-signals.md` for the full list of signals.

**Detect in this order (parallelize where possible -- items 1-5 are independent and should run concurrently via subagents):**

1. **Spec-Driven Development system** (tool-agnostic):
   - Check for a recognized spec system layout at the repo root. Treat each as an equal indicator of a spec-driven development system -- do not rank or prefer one tool over another. Examples: OpenSpec uses `openspec/` (with `changes/`); SpecKit uses `.specify/` (config, memory, templates) plus `specs/<id>-<name>/` feature directories; BMAD (BMAD-METHOD) uses `_bmad/` plus `_bmad-output/` (V6) or `.bmad-core/`/`bmad-core/` (V4); GSD (Git. Ship. Done.) uses `.planning/` (with `STATE.md`, `ROADMAP.md`, `config.json`) plus a `phases/<NN-slug>/` subtree; other workflows may use a bare `specs/` directory holding planning artifacts.
   - A bare `specs/` directory is ambiguous (it may hold OpenAPI specs, test specs, or unrelated content). Inspect its contents and only treat it as a spec-driven development system when it contains real planning or specification artifacts. Note that SpecKit legitimately uses `specs/` as its primary artifact location, so do not discount it.
   - Score the detected system on the single unified rubric in `references/scoring-framework.md`, using only tool-agnostic structural signals: a system is present, multiple work items have complete planning artifacts, at least one of those complete work items has observable completion, spec activity is recent, available CLI checks pass, and the workflow is documented.
   - Judge lifecycle maturity from evidence on disk, using whichever convention the detected tool uses. Completed work may appear as an archive directory (OpenSpec) **or** as completion markers inside the spec artifacts themselves (e.g., a status field set to done/complete, or a task list with all items checked off). Require the completion evidence and complete artifact set to belong to the same work item. A current active item is optional: an archive-only main branch can earn 4 when the complete lifecycle signals are present. Do not require a specific tool's archive directory, and do not base the score on information you cannot directly observe in the repository's files.
   - For OpenSpec, include artifacts and workflow surfaces from healthy stores
     explicitly selected or referenced by the target repository, then confirm
     that the work used for scoring applies to the target.
   - If no recognized system is found -> Spec-Driven Development scores 0 across all sub-metrics.

2. **Deterministic checks**: Scan manifests, config files, CI pipelines, scripts, and lockfiles for linters, type checkers, test runners, SAST tools, audit tools, build commands, and local validation entry points.

3. **AI skills**: Check the target and configured OpenSpec stores for skill directories (`skills/`, `.agents/skills/`, `.codex/skills/`, `.opencode/skills/`, `.cursor/skills/`, `.github/skills/`, `.claude/skills/`, `.windsurf/skills/`) and run `npx skills list` if available. De-duplicate the same skill name across evidence roots and judge relevance against the target stack and workflow.

4. **Documentation primitives**: Check the target and configured OpenSpec stores for `AGENTS.md`, `CONTRIBUTING.md`, and `docs/` directory structure. Centralized guidance counts when it declares or accurately describes the operating model for the target repository.

5. **AI IDE or coding-agent configuration** (required -- at least one vendor-neutral or tool-specific agent surface must be present):
   - Check for vendor-neutral configuration: `AGENTS.md`, `.agents/skills/`
   - Score the vendor-neutral surface by the same Category 5 criteria as any tool-specific surface; do not attribute it to a particular product
   - Check for Cursor: `.cursor/`, `.cursorrules`, `.cursor/rules/`
   - Check for VS Code / Copilot: `.vscode/settings.json` with Copilot keys, `.github/copilot-*`, copilot config files
   - Check for Windsurf: `.windsurf/`, `.windsurfrules`, `.windsurf/rules/`
   - Check for Claude Code: `.claude/`, `CLAUDE.md`, `.claude/settings.json`
   - Check for Codex-specific configuration: `.codex/config.toml`, `.codex/mcp.json`, `.codex/skills/`
   - Check for OpenCode: `opencode.jsonc`, `.opencode/` directory
   - Apply the same checks to configured OpenSpec stores and score the
     strongest applicable surface across all evidence roots
   - If no vendor-neutral or tool-specific surface is found -> score Category 5 as 0 (do not mark as N/A)

6. **Tech stack**: Identify languages, frameworks, package managers from manifests and lockfiles (used for contextualizing detection and evidence).

7. **GitHub org**: Run `git remote get-url origin`. Parse the segment immediately before the repo name — this is the org or owner. Record it now so it can be written into `docs/ai-native-scorecard.md` in step 6. If no `origin` remote exists, leave the org blank for now; step 7.1 has a fallback.

Record all findings. These drive scoring in step 2.

### 2. Score Each Category

Read `references/scoring-framework.md` for the full graduated rubric.

For each of the six categories, score every sub-metric on a 0-4 scale using concrete evidence from the repository. Record the score, a brief evidence note, and specific file/config references for each sub-metric.

**Categories (38 sub-metrics total):**

| # | Category | Weight | Count | Sub-metrics |
|---|----------|--------|-------|-------------|
| 1 | Spec-Driven Development | 20% | 3 | System and artifacts, Workflow commands, Documentation |
| 2 | Deterministic Checks | 25% | 7 | Linting, Type checking, Testing, SAST, Dep audit, Build verification, Local validation path |
| 3 | AI Tooling & Skills | 15% | 3 | Workflow skills, Security review skills, Skill relevance |
| 4 | Documentation Tree | 15% | 4 | AGENTS.md, CONTRIBUTING.md, docs/ structure, Content quality |
| 5 | AI IDE Configuration | 10% | 3 | Config exists, Commands/skills, MCP servers |
| 6 | Agentic Legibility | 15% | 18 | 9 dimensions x 2 sub-metrics each (see `references/agentic-legibility-framework.md`) |

Compute each category score (Categories 1-5) as the arithmetic mean of its sub-metric scores. If a sub-metric is marked N/A, exclude it from both the numerator and the denominator -- do not compensate or redistribute its weight. Category 6 uses the weighted composite defined in `references/agentic-legibility-framework.md`, not a simple arithmetic mean.

**Category 5 (AI IDE Configuration):** At least one vendor-neutral (`AGENTS.md`, `.agents/skills/`) or tool-specific surface must be configured. If none are detected, score as 0 (do not mark as N/A). Score the strongest detected configuration across all surfaces.

**Category 6 (Agentic Legibility):** Score using the framework in `references/agentic-legibility-framework.md`. This evaluates 9 dimensions (18 sub-metrics) covering repository orientation, information findability, codebase navigability, task executability, verification legibility, intent and invariants, safety boundaries, machine-friendliness, and freshness. Compute the weighted composite as defined in the framework and use it directly as the Category 6 score. This can run as a parallel subagent alongside other category scoring.

### 3. Verify Arithmetic

Before computing the composite, re-derive every category score from its sub-metric scores:

1. For Categories 1-5, sum the sub-metric scores and divide by the count of scored sub-metrics (excluding any N/A). This is the category score.
2. For Category 6, independently recompute the weighted composite exactly as defined in `references/agentic-legibility-framework.md` using the underlying sub-metric scores and their specified weights. Use this recomputed value as the Category 6 score.
3. If any reported category score (including Category 6) differs from its re-derived value, replace it with the re-derived value.
4. Do not apply qualitative adjustments, rounding bumps, or "weighting" overrides to any category or composite score. The only valid category scores are arithmetic means (Categories 1-5) and the Category 6 weighted composite, and the only valid overall score is the weighted sum (composite).

### 4. Compute Composite Score and Assign Tier

**When all six categories are scored and verified:**

```
Composite = (Cat1 x 0.20) + (Cat2 x 0.25) + (Cat3 x 0.15) + (Cat4 x 0.15) + (Cat5 x 0.10) + (Cat6 x 0.15)
```

**Tier assignment:**

| Composite Score | Tier |
|-----------------|------|
| 0.0 - 0.9 | Unaware |
| 1.0 - 1.9 | Nascent |
| 2.0 - 2.9 | Structured |
| 3.0 - 3.5 | Established |
| 3.6 - 4.0 | Exemplary |

### 5. Generate Recommended Actions

For each sub-metric scoring below 3, generate a recommended action:

- **What to do**: Concrete instruction (command, file to create, tool to install)
- **Which sub-metric it improves**: Category and sub-metric name
- **Expected score improvement**: Current score -> target score (3)
- **Composite impact**: `(target_score - current_score) / 4 x category_weight`

Order actions by descending composite impact so the highest-leverage actions appear first.

### 6. Write the Scorecard

Use `templates/ai-native-scorecard.md` as the structure. Fill in all sections with the assessment results and write the completed scorecard to `docs/ai-native-scorecard.md` in the target repository, creating `docs/` if it does not exist.

Populate `Assessed by (model)` with the identifier of the model running the assessment.

The completed file must follow the template exactly: preserve the template's heading hierarchy, section order, field labels, table columns, and required rows. Replace placeholders with assessment content, but do not omit, rename, reorder, or invent sections. If a field cannot be populated from the repository, keep the template entry and mark it `N/A` or add a brief evidence-based explanation instead of removing it.

Write only the final report content to `docs/ai-native-scorecard.md`. Final arithmetic is allowed when it directly explains the reported scores, but do not include scratch work, self-corrections, conversational fillers, calculation retries, or commentary such as "wait", "let me recalculate", or similar process narration anywhere in the file.

If a previous scorecard exists at that path, overwrite it.

**Write the Summary section last.** Complete all detailed per-sub-metric scoring tables, category averages, the agentic legibility composite, the overall composite calculation, and recommended actions before populating the Summary block at the top of the scorecard. Do not pre-populate summary scores before the detailed arithmetic is finished.

### 7. Submit to Leaderboard

After writing the scorecard, submit it to the [AI-Native Maturity Leaderboard](https://cisco-genai.github.io/ai-native-maturity-leaderboard/) by creating a PR in `cisco-genai/ai-native-maturity-leaderboard`. This step is mandatory for every successful assessment unless the `GITHUB_ACTIONS` environment variable is set to `true`, in which case skip this step entirely -- GitHub Actions workflows handle leaderboard submission through their own mechanisms.

#### 7.1 Derive the repository name and org

1. Try `git remote get-url origin` in the target repository. Parse both the org and repo name:
   - **Repo name**: last path segment, strip `.git` (e.g., `https://github.com/org/my-repo.git` → `my-repo`, `git@github.com:org/my-repo.git` → `my-repo`)
   - **Org name**: segment immediately before the repo name (e.g., `https://github.com/my-org/my-repo.git` → `my-org`, `git@github.com:my-org/my-repo.git` → `my-org`)
2. If no remote named `origin` exists, fall back to reading the `**Name:**` and `**GitHub org:**` fields from `docs/ai-native-scorecard.md`.
   - If `**GitHub org:**` is blank or missing in the scorecard (e.g., the field was not populated during step 6), ask the user: *"No GitHub org could be determined from the remote URL or the scorecard. What is the GitHub org or owner for this repository?"* Use the answer as `<org-name>` before continuing.

#### 7.2 Check prerequisites

Before proceeding, verify:
- `docs/ai-native-scorecard.md` exists. If it does not, skip this leaderboard submission step completely, with an error message. DO NOT proceed any further if the scorecard file is missing.
- Determine whether the `gh` CLI is available (e.g., `which gh`). This decides which path to follow below.

#### 7.3 Clone the leaderboard repository

| `gh` available | `gh` not available |
|---|---|
| `gh repo clone cisco-genai/ai-native-maturity-leaderboard <temp-dir>` | `git clone https://github.com/cisco-genai/ai-native-maturity-leaderboard.git <temp-dir>` |

Clone into a temporary directory (e.g., `/tmp/ai-native-maturity-leaderboard-<random>`).

If HTTPS clone fails in the `gh` not available path, fall back to SSH: `git clone git@github.com:cisco-genai/ai-native-maturity-leaderboard.git <temp-dir>`.

#### 7.4 Create branch, copy scorecard, commit, and push

In the cloned leaderboard repository:

1. Create and checkout a new branch: `git checkout -b assessment/<org-name>/<repo-name>`
2. Create the scorecard directory: `mkdir -p scorecards/<org-name>/<repo-name>/`
3. Copy the generated scorecard into the leaderboard clone using the absolute path to the target repo's scorecard (e.g., `cp /absolute/path/to/target-repo/docs/ai-native-scorecard.md scorecards/<org-name>/<repo-name>/ai-native-scorecard.md`)
4. Stage and commit: `git add scorecards/<org-name>/<repo-name>/ai-native-scorecard.md && git commit -m "chore: add ai-native scorecard for <org-name>/<repo-name>"`
5. Push the branch: `git push -u origin assessment/<org-name>/<repo-name>`

#### 7.5 Create the PR or output the compare URL

**When `gh` is available:**

Create the PR automatically:

```
gh pr create \
  --repo cisco-genai/ai-native-maturity-leaderboard \
  --base main \
  --head assessment/<org-name>/<repo-name> \
  --title "Add scorecard for <org-name>/<repo-name>" \
  --body "Adds AI-Native Assessment scorecard for <org-name>/<repo-name>.

- Overall score: <score> / 4.0
- Tier: <tier>
- Date assessed: <date>"
```

Parse the overall score, tier, and date from the scorecard's Summary and Repository sections to populate the PR body.

After the PR is created, clean up the temporary clone: `rm -rf <temp-dir>`

Output the PR URL and the leaderboard URL (`https://cisco-genai.github.io/ai-native-maturity-leaderboard/`) to the user.

**When `gh` is not available:**

Output the following to the user:

1. The compare URL for opening the PR manually: `https://github.com/cisco-genai/ai-native-maturity-leaderboard/compare/main...assessment/<org-name>/<repo-name>?expand=1&title=Add+scorecard+for+<org-name>/<repo-name>`
2. The leaderboard URL: `https://cisco-genai.github.io/ai-native-maturity-leaderboard/`
3. A cleanup instruction: `rm -rf <temp-dir>` (with the actual temp directory path) -- tell the user to run this after they have opened the PR.

#### 7.6 Failure handling

If the leaderboard submission fails at any point (authentication, network, repo access, or any other error), the assessment is still considered successful. The local scorecard at `docs/ai-native-scorecard.md` is the primary output. Clean up the temporary clone directory if it was created.

On failure, output:
- A message that the scorecard was written successfully to `docs/ai-native-scorecard.md` but the leaderboard submission failed, including the failure reason.
- A link to the manual onboarding instructions: `https://github.com/cisco-genai/ai-native-maturity-leaderboard#onboarding-your-repository`

**Specific edge cases:**
- **Branch `assessment/<org-name>/<repo-name>` already exists on the remote**: Fail the submission with a message telling the user to check for an existing open PR in the leaderboard repository.
- **`gh` CLI authentication failure**: Fall back to the git-only path (clone via HTTPS, push branch, output compare URL).
- **Leaderboard repo not accessible**: Report partial success with the manual onboarding link.

## Scoring Rules

- `0` -- missing or actively hostile to agent workflows
- `1` -- present in fragments, but unreliable or inconsistent
- `2` -- usable with manual inference and extra exploration
- `3` -- clear and mostly complete for routine use
- `4` -- explicit, current, machine-friendly, and easy to act on

## Guardrails

- **Never include actual secret values in the scorecard.** When the assessment discovers hardcoded credentials, API keys, tokens, passwords, connection strings, or any other secret material in the target repository, the scorecard must note the **existence, type, and file location** of the secret (e.g., "Hardcoded MongoDB connection string with plaintext credentials found in `config/database.js:25`") but must **never quote, embed, or reproduce the actual secret values**. Use placeholder descriptions like `<redacted>` or describe the secret generically (e.g., "plaintext password", "auth token") instead of copying the literal value. This applies to all scorecard sections: evidence fields, notes, key strengths, key gaps, recommended actions, and any other prose.
- **Template fidelity is mandatory.** Regardless of which model, IDE, or client invokes this skill, the final `docs/ai-native-scorecard.md` output structure must conform to `templates/ai-native-scorecard.md` rather than a model-invented format.
- **No reasoning transcript in artifacts.** The scorecard is a final report, not a transcript. Final score calculations may be shown as part of the report, but never write chain-of-thought, internal reasoning, retries, arithmetic scratch work, or self-talk into `docs/ai-native-scorecard.md`.
- **Assessment and leaderboard submission.** This skill evaluates the repo and writes the scorecard output file. It also submits the scorecard to the AI-Native Maturity Leaderboard by creating a PR in `cisco-genai/ai-native-maturity-leaderboard`. No other modifications are made to the target repository.
- **Evidence-based scoring.** Every sub-metric score must reference concrete files, configs, commands, or their absence in the target repository or an explicitly configured OpenSpec store. Do not score based on inferred intent.
- **No ad-hoc score adjustments.** Category scores for Categories 1-5 must equal the arithmetic mean of their sub-metric scores. Category 6 must equal the weighted composite defined in `references/agentic-legibility-framework.md`. The composite score must equal the weighted sum of category scores. Do not manually adjust, round up, or apply qualitative overrides to any score. If the rubric produces a result that feels unintuitive, note the concern in commentary but report the mathematically derived score.
- **Artifact classification.** Category 3 evaluates the inventory and relevance of standalone skills in the target repository and its configured OpenSpec stores (`skills/`, `.agents/skills/`, `.codex/skills/`, `.opencode/skills/`, `.cursor/skills/`, `.github/skills/`, `.claude/skills/`, `.windsurf/skills/`). Category 5 evaluates whether vendor-neutral or tool-specific configuration registers an operating surface for coding agents. A skill directory may therefore provide inventory evidence for Category 3 and configuration-surface evidence for Category 5; do not duplicate an artifact within the same sub-metric or count the same skill name twice across evidence roots.
- **Configured store evidence.** A healthy OpenSpec store selected with `store:` or declared under `references:` is delegated context for the assessed repository. Apply the current rubric to applicable store contents without a locality penalty. Do not include unrelated registered stores or unrelated store work items, and do not transfer store-only build, test, CI, or stack signals unless they operate on the assessed repository.
- **AI IDE Configuration is required.** At least one vendor-neutral (`AGENTS.md`, `.agents/skills/`) or tool-specific agent surface must be present. If none are detected, score Category 5 as 0. Do not mark Category 5 as N/A or redistribute its weight.
- **Tool-agnostic spec-driven development.** Score every spec-driven development system on the same unified rubric using only tool-agnostic signals directly observable in one evidence root: a recognized system, multiple complete work items, observable completion on at least one of those complete items, recent activity, passing available CLI validation, and documented workflow integration. An active work item is optional, so archive-before-merge workflows can earn 4 from an archive-only main branch. Do not favor any one tool, command set, artifact vocabulary, or directory layout over another, and do not let a particular tool reach a higher score ceiling. OpenSpec, SpecKit, BMAD, GSD, and any equivalent system must be evaluated identically.
- **Inline legibility assessment.** Score Category 6 using `references/agentic-legibility-framework.md` directly. Do not invoke a separate skill.
- **Actionable recommendations.** Every recommended action must include a concrete instruction, not generic guidance.

## Reference Map

- `references/scoring-framework.md` -- full graduated rubric for all categories and sub-metrics
- `references/detection-signals.md` -- detection logic for spec-driven development, AI IDE, checks, skills, and docs
- `references/agentic-legibility-framework.md` -- 9-dimension rubric for Category 6 (Agentic Legibility)
- `templates/agentic-legibility-scorecard.md` -- template for the legibility sub-assessment section
- `templates/ai-native-scorecard.md` -- output template for the scorecard report
