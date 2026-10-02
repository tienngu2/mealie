# Salesforce Deterministic Scans

Use `sf code-analyzer run` as the primary static-analysis gate for Salesforce repositories. This file records only sample-verified behavior; do not extend the coverage claims below without rerunning verification against representative fixtures.

## Tool Resolution Order

1. Salesforce CLI (`sf`) must be on `PATH`. Detect the installed version with `sf --version`.
2. `@salesforce/plugin-code-analyzer` must be installed. Detect it with `sf plugins --core` (look for `code-analyzer <version>` in the output).
3. Java must be available for the bundled `pmd` engine.
4. Node.js and `npm` are required only for the complementary `sfdx-lwc-jest` and `prettier` checks; `retire-js` inspects vendored libraries directly in the Salesforce metadata tree and does not require `npm ci` or `node_modules` (see "Dependency-Installation Prerequisite" below).

## Verified Prerequisites

Verified on APM CLI 0.27.0, `@salesforce/cli` 2.140.6, and `@salesforce/plugin-code-analyzer` 5.5.0:

- `sf code-analyzer run` requires no additional plugin configuration to execute against a Salesforce DX source-format or Metadata API format project.
- The CLI reports a plugin/CLI version mismatch on its own (for example: `Plugin @salesforce/plugin-code-analyzer (5.5.0) is older than the version specified by sf (5.13.0)`). The generated local entrypoint should surface this message rather than suppress it.

## Exact Tested Code Analyzer Plugin Installation for CI

```bash
sf plugins install @salesforce/plugin-code-analyzer@5.5.0
```

Pin CI to this exact verified version. Updating it requires rerunning the sample verification described in this file and in `design.md` of the `add-salesforce-stack` change, then updating this pinned version.

## Local Version-Mismatch Handling

The generated local entrypoint should check the installed plugin version before scanning and report a mismatch rather than silently using an unverified version:

```bash
installed_version=$(sf plugins --core 2>/dev/null | grep -m1 '^code-analyzer' | awk '{print $2}')
if [ "$installed_version" != "5.5.0" ]; then
    echo "Warning: @salesforce/plugin-code-analyzer $installed_version is installed; this repo's checks were verified against 5.5.0." >&2
fi
```

## `sf code-analyzer run` as the Primary Static-Analysis Gate

```bash
sf code-analyzer run --workspace . --output-file code-analyzer-results.json
```

Target Salesforce-owned roots (`force-app`, or the Metadata API format directories associated with the Salesforce-namespaced `package.xml`) in mixed repositories rather than the whole workspace. See "Mixed Repositories" below.

### Verified Coverage

Verified against source-format and Metadata API format fixtures containing an Apex class and trigger, an LWC bundle (`.js`/`.html`/`.css`/`.js-meta.xml`), a Flow, and a vendored vulnerable JavaScript library. Both formats produced identical results (20 violations across 4 files: 15 `pmd`, 5 `eslint`).

| Concern | Covered by default Code Analyzer selection | Complement |
| --- | --- | --- |
| Apex static analysis | Yes -- `pmd` fired `ApexSOQLInjection`, `ApexCRUDViolation`, `OperationWithLimitsInLoop`, `AvoidLogicInTrigger`, `ApexDoc`, `AvoidDebugStatements`, `DebugsShouldUseLoggingLevel` on `.cls` and `.trigger` files | Optional `--rule-selector sfge` for `DevPreview`-tagged data-flow rules (see below) |
| LWC JavaScript lint | Yes -- `eslint` fired `no-var`, `@lwc/lwc/no-document-query`, `@lwc/lwc/no-inner-html` | `auto_discover_eslint_config` (see below) when the repo owns an LWC ESLint config |
| LWC CSS lint | Yes -- `eslint` fired `@salesforce-ux/slds/no-hardcoded-values-slds2` | -- |
| LWC HTML template lint | Not observed in the sample -- no template-specific rule fired | Repo-native LWC template lint if the repo requires it |
| Flow analysis | Narrow -- the `flow` engine parses and traverses `.flow-meta.xml` / `.flow` files, but at plugin 5.5.0 exposes only two rules, both security-focused: `PreventPassingUserDataIntoElementWithoutSharing` (severity 2/High) and `PreventPassingUserDataIntoElementWithSharing` (severity 4/Low) | Repo-native Flow review for non-security concerns (best-practice patterns such as DML-in-loop are not covered) |
| Vulnerable JavaScript libraries vendored in the Salesforce tree | Yes -- `retire-js` fired `LibraryWithKnownMediumSeverityVulnerability` against a jQuery 3.3.1 file placed under a Salesforce metadata directory | -- |
| npm dependency tree vulnerabilities | No -- `node_modules` is excluded from the workspace scan, and installing dependencies did not change the Code Analyzer result | `npm audit` |
| Code formatting | No | `prettier --check` with `prettier-plugin-apex` |
| LWC unit tests | No | `sfdx-lwc-jest` |

Apex test execution is intentionally absent from this baseline. Salesforce deployment controls Apex test levels and executes the required tests in the target org; this harness does not add a separate `sf apex run test` command or require CI org authentication.

**`sfge` is not in the default rule selection.** All seven `sfge` rules (`ApexFlsViolation`, `ApexNullPointerException`, `AvoidDatabaseOperationInLoop`, `AvoidMultipleMassSchemaLookups`, `DatabaseOperationsMustUseWithSharing`, `MissingNullCheckOnSoqlVariable`, `UnimplementedType`) are tagged `DevPreview` at plugin 5.5.0 and require an explicit `--rule-selector sfge` to run. Treat `sfge` as an optional, not default, complement until the plugin promotes it out of `DevPreview`.

## ESLint Configuration Behavior (Verified)

- `auto_discover_eslint_config` defaults to `false`. With the default, a project `eslint.config.js` is ignored entirely and only the bundled base configs (JavaScript, LWC, SLDS) apply.
- Setting `engines.eslint.auto_discover_eslint_config: true` in `code-analyzer.yml` merges the project's own ESLint config, and project rule overrides take precedence over the bundled base configs. In the sample, turning off `no-var` and `prefer-template` in the project config reduced ESLint findings from 8 to 6 under `--rule-selector eslint`.
- Discovery resolves the project config relative to the linted files' directory tree; running `sf code-analyzer run` from the repository root with `--workspace .` keeps the config and any of its plugin imports resolvable. A narrower `--workspace` under the project root also picked up the same root-level config in the sample.
- Rule-selector breadth matters independently of auto-discovery: the default `Recommended` selection produced 5 ESLint findings against the sample LWC files, while `--rule-selector eslint` (all ESLint rules) produced 8.

```yaml
# code-analyzer.yml
engines:
  eslint:
    auto_discover_eslint_config: true
```

## Dependency-Installation Prerequisite (Verified)

`retire-js` does **not** require `npm ci` or an installed `node_modules` tree to find a vulnerable library. It matches vendored library files it can see inside the scanned tree directly. In the sample, installing dependencies with `npm install` left the Code Analyzer result unchanged (20 violations before and after), and `retire-js` still needed the vulnerable file placed on disk under the scanned Salesforce tree, not merely present in `node_modules` (which the workspace scan does not enter).

Do not add `npm ci` as a required step for Code Analyzer coverage. Keep vendored static-resource libraries out of the default lint target where possible -- in the sample, scanning a vendored minified library alongside the source files added roughly 350 incidental ESLint findings unrelated to the repo's own code.

## Complementary Checks

Code Analyzer does not cover formatting or LWC unit tests. Add these as separate, repo-native commands:

```bash
npx prettier --check "force-app/**/*.{cls,trigger,js,html,css}" --plugin=prettier-plugin-apex
npx sfdx-lwc-jest
```

## Enforced and Advisory Variants

Enforced mode passes the team-selected numeric severity threshold, recorded alongside the harness configuration:

```bash
sf code-analyzer run --workspace force-app --severity-threshold <1-5> --output-file code-analyzer-results.json
```

Verified: `--severity-threshold 2` against the sample exited `2` with `Error (2): 5 violations met or exceeded the severity threshold of "High"`. Omitting the flag exited `0` while still reporting all violations.

Advisory mode omits `--severity-threshold` entirely so the scan reports violations and exits zero:

```bash
sf code-analyzer run --workspace force-app --output-file code-analyzer-results.json
```

The complementary `prettier --check` and `sfdx-lwc-jest` commands have no native severity flag. Make them non-blocking at the generated entrypoint in advisory mode:

```bash
npx prettier --check "force-app/**/*.{cls,trigger,js,html,css}" --plugin=prettier-plugin-apex || true
npx sfdx-lwc-jest || true
```

## CI Wiring

Follow the shared enforcement-mode conventions in `references/ci-wiring.md`. Install the pinned plugin version before scanning.

### GitHub Actions

```yaml
jobs:
  deterministic-checks:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Set up Node.js
        uses: actions/setup-node@v4
        with:
          node-version: '20'

      - name: Set up Salesforce CLI
        run: npm install --global @salesforce/cli

      - name: Install Code Analyzer plugin
        run: sf plugins install @salesforce/plugin-code-analyzer@5.5.0

      - name: Code Analyzer
        run: sf code-analyzer run --workspace force-app --severity-threshold {severity} --output-file code-analyzer-results.json

      - name: Install Node dependencies
        run: npm ci

      - name: Formatting
        run: npx prettier --check "force-app/**/*.{cls,trigger,js,html,css}" --plugin=prettier-plugin-apex

      - name: LWC unit tests
        run: npx sfdx-lwc-jest
```

Add `continue-on-error: true` to each step in advisory mode, following the pattern in `references/ci-wiring.md`.

### Jenkins

```groovy
stage('Deterministic Checks') {
    steps {
        sh 'command -v sf >/dev/null || npm install --global @salesforce/cli'
        sh 'command -v java >/dev/null || { echo "Java is required for the pmd engine; install it on this agent before running Code Analyzer."; exit 1; }'
        sh 'npm ci'
        sh 'sf plugins install @salesforce/plugin-code-analyzer@5.5.0'
        sh 'sf code-analyzer run --workspace force-app --severity-threshold {severity} --output-file code-analyzer-results.json'
        sh 'npx prettier --check "force-app/**/*.{cls,trigger,js,html,css}" --plugin=prettier-plugin-apex'
        sh 'npx sfdx-lwc-jest'
    }
}
```

Wrap each `sh` step in `catchError(buildResult: 'SUCCESS', stageResult: 'UNSTABLE') { ... }` for advisory mode, following the pattern in `references/ci-wiring.md`.

## Mixed Repositories

When a Salesforce project coexists with an independently detected Node, React, or Angular application (see the polyglot behavior in `references/stacks/salesforce/stack.md`):

- Target `sf code-analyzer run --workspace` at the Salesforce-owned root (for example `force-app`, or the Metadata API format directories associated with the Salesforce-namespaced `package.xml`) rather than the whole repository.
- Exclude the independent application's directory from the Code Analyzer target so its own stack's deterministic checks -- not Code Analyzer -- own that path.
- Keep both check sets wired into the same CI job or pipeline stage set, each scoped to the paths it owns.
