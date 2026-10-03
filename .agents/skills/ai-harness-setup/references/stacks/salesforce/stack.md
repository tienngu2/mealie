# Salesforce

Read this file for Salesforce repositories: Apex, Lightning Web Components (LWC), Flows, and other Salesforce metadata.

## Repo Markers

Salesforce detection runs before JavaScript detection because Salesforce repositories routinely carry a `package.json` for the `sf` CLI, LWC test tooling, and formatting plugins. Evaluate these markers first:

- `sfdx-project.json` and its configured `packageDirectories` -- Salesforce DX source-format marker.
- `package.xml` whose root element declares the Salesforce Metadata API namespace `http://soap.sforce.com/2006/04/metadata` -- Metadata API format marker. A file merely named `package.xml` without that namespace is not Salesforce evidence.
- `*.cls` paired with a `*.cls-meta.xml` descriptor, and `*.trigger` paired with a `*.trigger-meta.xml` descriptor (Apex classes and triggers). An unpaired `*.cls` file is not Salesforce evidence on its own -- `.cls` is also the LaTeX document-class extension -- unless it already sits inside an established Salesforce-owned root.
- `*.js-meta.xml` -- the LWC bundle descriptor. A directory containing this file alongside a `.js`, `.html`, and optional `.css` file is an LWC bundle, in either an SFDX package directory or a Metadata API format tree.
- Additional verified metadata suffixes: `*.flow-meta.xml` (Flows, source format) or `*.flow` (Flows, Metadata API format), and Aura `*.cmp` bundles.

## Salesforce-Owned-Root Derivation

Derive Salesforce-owned roots before evaluating any JavaScript application marker:

1. If `sfdx-project.json` exists, each configured package directory is Salesforce-owned.
2. If a Salesforce-namespaced `package.xml` exists, its associated metadata tree is Salesforce-owned.
3. Otherwise, cluster the discovered Apex (`*.cls`/`*.trigger` paired with their `-meta.xml` descriptor) and `*.js-meta.xml` files by their nearest shared metadata-tree ancestor (for example, each top-level directory containing its own `classes/`, `triggers/`, or `lwc/` subtree) and treat each cluster's common directory as Salesforce-owned. Do not promote markers from multiple independent metadata trees to their shared monorepo ancestor -- a repository can contain more than one Salesforce-owned root.
4. Exclude dependency (`node_modules`), generated, VCS (`.git`), and harness-owned directories while searching.

JavaScript confined to a Salesforce-owned root -- including an LWC bundle identified by `*.js-meta.xml` -- does not by itself select a JavaScript or frontend package. A Node, React, or Angular application with its own manifest, workspace membership, framework configuration, source root, or build entrypoint **outside** every Salesforce-owned root remains independently eligible for its matching stack package (see the polyglot behavior below).

## Project Layout

**Salesforce DX source format** (the common authoring format):

```
sfdx-project.json
force-app/
  main/
    default/
      classes/
        MyClass.cls
        MyClass.cls-meta.xml
      triggers/
      lwc/
        myComponent/
          myComponent.js
          myComponent.html
          myComponent.css
          myComponent.js-meta.xml
      flows/
        My_Flow.flow-meta.xml
```

**Metadata API format** (retrieved or legacy metadata, no `sfdx-project.json`):

```
package.xml            <!-- Salesforce Metadata API namespace -->
classes/
  MyClass.cls
  MyClass.cls-meta.xml
triggers/
lwc/
  myComponent/
flows/
  My_Flow.flow
```

Both formats are supported. Detection does not require `sfdx-project.json`; a Salesforce-namespaced `package.xml` or Salesforce-specific metadata files alone establish a Salesforce-owned root.

## Tooling Prerequisites

- Salesforce CLI (`sf`) on `PATH`.
- `@salesforce/plugin-code-analyzer` installed (`sf plugins install @salesforce/plugin-code-analyzer`). See `references/stacks/salesforce/deterministic-scans.md` for the exact verified version and version-mismatch handling.
- Java, which the bundled `pmd` engine requires.
- Node.js and `npm` when the repo carries LWC dependencies (`sfdx-lwc-jest`, ESLint, Prettier).

## Skills to Install

Install the `stack-salesforce` package when Salesforce evidence is detected:

```bash
apm install --target <ide-1> --target <ide-2> --allow-protocol-fallback cisco-genai/awesome-cisco/packages/stack-salesforce#stack-salesforce-v<latest>
```

This package covers `platform-apex-generate`, `platform-apex-test-generate`, `platform-soql-query`, and the transitive `core` workflow bundle. It does not include the Code Analyzer tooling skills (`dx-code-analyzer-*`), Apex test-run, debugging, or LWC generation skills -- those remain available through the dynamic add-on path when the repo genuinely needs them.

## Polyglot Behavior

A repository can contain both Salesforce metadata and an independently detected application:

- If the only JavaScript or TypeScript evidence is confined to Salesforce-owned roots (LWC bundles, `sf`/LWC tooling in a root `package.json`), install only `stack-salesforce`.
- If a Node, React, or Angular application exists outside every Salesforce-owned root with its own framework, workspace, source, or build markers, install `stack-salesforce` **and** the matching application stack package. Target each package's deterministic checks to the paths that package owns (Salesforce-owned roots for Code Analyzer, the application's own root for its stack's checks).

See `references/stacks/salesforce/deterministic-scans.md` for the deterministic-check baseline, verified Code Analyzer coverage, enforcement variants, and CI wiring.
