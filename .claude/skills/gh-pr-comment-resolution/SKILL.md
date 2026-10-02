---
name: gh-pr-comment-resolution
description: Use for workflows that fetch GitHub pull request review comments with the gh CLI, identify review threads from any reviewer, classify obsolete versus current threads, and resolve them automatically by default (opt-in review-before-apply mode on request), iterating after each push until current unresolved threads are cleared. Trigger when asked to review/resolve PR comments, fetch PR review threads, or document how to close review threads via gh api graphql.
compatibility: Requires gh CLI to be installed and authenticated
metadata:
  version: "1.2.0"
---

# GH PR Comment Resolution

## Overview

Use gh CLI + GraphQL to run an iterative review-thread workflow: check branch state, fetch all review threads with enough context to classify them, resolve obsolete churn immediately, then fix and resolve the remaining real issues automatically by default. If the invoking prompt asks to review changes first, gate code edits on explicit approval instead. Repeat after each push until current unresolved review threads are cleared.

## Workflow

### 1) Identify the PR and check merge state

- Get the PR details for the current branch:

```bash
gh pr view --json number,title,url,headRefName,baseRefName,mergeable,mergeStateStatus
```

- Handle merge state before comment triage:

| State | Action |
| --- | --- |
| `mergeStateStatus == "BEHIND"` and `mergeable == "MERGEABLE"` | Update the branch from `origin/<baseRefName>`, push, then continue |
| `mergeStateStatus == "DIRTY"` or `mergeable == "CONFLICTING"` | Stop and report the conflict state |
| `mergeStateStatus == "BLOCKED"` and `mergeable == "MERGEABLE"` | Continue; note the blocker in the final report |

### 2) Fetch all review threads

- Use GraphQL pagination and capture thread ids for resolution plus enough context for classification:

```bash
gh api graphql -f query='query($owner:String!,$repo:String!,$number:Int!,$after:String){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:50,after:$after){pageInfo{hasNextPage,endCursor}nodes{id,isResolved,isOutdated,comments(first:1){nodes{author{login}body path line originalLine diffHunk}}}}}}}' -f owner='<OWNER>' -f repo='<REPO>' -F number=<PR_NUMBER>
```

- Optionally list classic review comments for easier scanning:

```bash
gh api repos/<OWNER>/<REPO>/pulls/<PR_NUMBER>/comments
```

### 3) Classify unresolved threads

- Filter by `author.login` to focus on a specific reviewer (optional; the skill works with any reviewer).
- Ignore threads already marked `isResolved == true`.
- Bucket each unresolved thread into one of these groups:
  - `outdated` — `isOutdated == true`
  - `duplicate` — repeated issue theme on the same file path; keep the newest current thread
  - `stale-meta` — PR-title or PR-description scope comments that no longer match the actual change
  - `current-real` — current actionable review issues

Use `path`, `line`, `originalLine`, `diffHunk`, and the full first-comment `body` to map each current thread back to the workspace.

### 4) Auto-resolve obsolete threads

- Resolve `outdated`, `duplicate`, and `stale-meta` threads immediately:

```bash
gh api graphql -f query='mutation($threadId:ID!){resolveReviewThread(input:{threadId:$threadId}){thread{id,isResolved}}}' -F threadId='<THREAD_ID>'
```

These are workflow-cleanup operations; they do not require code changes.

### 5) Determine the fix mode

- **Default: autonomous.** Apply fixes for every `current-real` thread and resolve them without stopping for approval.
- **Opt-in: review-gated.** Only use this mode when the invoking prompt explicitly asks to review or approve changes first (e.g., "review with me", "review before applying", "walk me through the fixes first"). This can be requested up front or at any later point in the conversation.

### 6) Apply fixes

- **Autonomous mode (default):** make code changes directly for every `current-real` thread, then continue to resolving threads and pushing.
- **Review-gated mode (opt-in):** summarize the remaining `current-real` threads in thread order using the compact format below, stop, and wait for explicit user approval before editing code. After approval, make code changes only for the approved threads.

#### Review-gate output format (review-gated mode only)

- Keep the primary view compact and scannable. Use one numbered item per thread with exactly:
  - `Thread ID`
  - `File:line`
  - `Reviewer`
  - `Issue summary` (1-2 sentences)
  - `Proposed fix` (1 sentence)
  - `Action type` (`code change` or `docs-only`)
- Do **not** inline full diff hunks or full comment bodies in the primary view.
- Add optional detail blocks only when the user asks for full context.
- After listing threads, include one explicit approval prompt: `Approve applying these fixes? (yes/no)`

- If the file is vendored or patched, update the patch script instead of the vendored file.
- Run the narrowest relevant validation for the touched slice before resolving the associated threads.

### 7) Resolve fixed threads and push

- Resolve each fixed thread via GraphQL:

```bash
gh api graphql -f query='mutation($threadId:ID!){resolveReviewThread(input:{threadId:$threadId}){thread{id,isResolved}}}' -F threadId='<THREAD_ID>'
```

- If a comment was already addressed, reply with context when useful and resolve the thread.
- Push the approved fixes to the PR branch.

### 8) Re-pull and repeat

- After each push, re-fetch review threads and repeat classification.
- Continue until there are no `current-real` unresolved threads left, the branch enters a conflict state, or the user declines further fixes.

### 9) Report back

- Summarize:
  - fix mode used (autonomous or review-gated)
  - threads auto-resolved as obsolete
  - threads fixed and resolved
  - remaining unresolved current threads, if any
  - final merge-policy blockers, if any
- Suggest tests if relevant.

## Notes

- Prefer GraphQL for review thread resolution because REST review comments do not expose thread ids.
- If `reviewThreads` exceed 50, paginate with `reviewThreads(first:50, after: <cursor>)` until `hasNextPage == false`.
- `isOutdated` is the key signal for collapsing stale churn before code edits.
- Default to autonomous fix-and-resolve; only gate on approval when the invoking prompt asks to review changes first.
