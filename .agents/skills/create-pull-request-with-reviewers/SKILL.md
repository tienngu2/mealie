---
name: create-pull-request-with-reviewers
description: Create a pull request with automatically recommended reviewers based on git history. Use this skill when the user wants to create a PR with reviewers, open a pull request, or submit changes for review with the right people assigned.
compatibility: Requires git and GitHub CLI (gh) to be installed
metadata:
  repository: ""
  defaultReviewer: ""
  jiraBaseUrl: "https://cisco-jira.atlassian.net"
  version: "1.1.0"
---

# Create Pull Request with Reviewers

## Setup

Before using this skill, check if any metadata fields are empty strings. If any are empty:
1. Prompt the user to provide the missing values (only prompt for fields that are empty):
   - `repository`: GitHub repository in format "org/repo"
   - `defaultReviewer`: Default reviewer GitHub username to use if no reviewers found
2. Update the SKILL.md frontmatter with the provided values so they don't need to configure again

## Instructions

1. **Get Changed Files**

Get files changed between current branch and main:

```bash
git diff --name-only origin/main...HEAD
```

2. **Analyze Git History for Reviewers**

For each changed file, find contributors with commit counts and recency:

```bash
git log --format='%an|%ar' -- <file> | sort | uniq -c | sort -rn | head -10
```

Run this for each file from Step 1 to build per-file reviewer data.

3. **Get Eligible Collaborators**

Get collaborators who can review:

```bash
gh api /repos/<metadata.repository>/collaborators --jq '.[].login'
```

Omit generic/service accounts (usernames containing `-gen` or `-gen_cisco`).

4. **Get Current User**

Get the current git user to exclude from reviewers:

```bash
git config user.name
```

5. **Rank Reviewers**

- Match git history contributors with GitHub collaborators
- **Exclude** the current user (PR author) from recommendations
- Rank by number of commits to the affected files
- Select **up to 3** reviewers (default to metadata.defaultReviewer if none found)

6. **Analyze Changes for PR Content**

Understand the changes to generate PR details:

```bash
git log main..HEAD --oneline
git diff main...HEAD --stat
git diff main...HEAD
```

7. **Generate PR Details**

Generate PR title using format: `JIRA-KEY - Verb + description`

Extract Jira keys from commit messages or branch name.

Generate the PR body from `templates/pull_request_template.md`.

- Preserve the standard section headings and checklist labels from the template.
- Replace the description section with a concise summary of the change, its motivation, and any important review context.
- Fill `- **JIRA ticket:**` with the extracted Jira key. If no Jira key is available, leave the field present and note that none was found.
- Add any related GitHub issues, Jira tickets, or PRs in the issues section when available.
- Keep the `### 🖼 Screenshots` section in the generated body. If screenshots are not applicable, set the section content to `Not applicable.`
- Keep the `### 🧪 How This Was Tested` section in the body. Check the box that best matches the change: `Created tests (unit and/or E2E)` if test files were added/modified, `Automated testing unnecessary (chores, doc updates, etc.)` for docs/chore-only changes, otherwise `Ran locally and verified`.
- Keep the `### 🛡️ Security` section in the body. If the change is not security-related, state `Not applicable.`
- Leave checklist items unchecked unless the repository changes clearly justify marking them complete.

Use this structure:

```markdown
### 🚀 Description, Motivation, and Context
<summary of changes>

### 📖 Issues and Related PRs
- **JIRA ticket:** [JIRA-KEY](<metadata.jiraBaseUrl>/browse/JIRA-KEY)

### 🖼 Screenshots
Not applicable.

### 🧪 How This Was Tested
- [ ] Ran locally and verified
- [ ] Created tests (unit and/or E2E)
- [ ] Automated testing unnecessary (chores, doc updates, etc.)

### ☑️ Required Items Complete
- [ ] Unit tests written
- [ ] Integration tests written
- [ ] Coverage verified
- [ ] Functionally tested
- [ ] Deployable to production
- [ ] Uses feature flags <List of flag names>
- [ ] README updated
- [ ] Build passes

### 🛡️ Security
Not applicable.
```

8. **Present for Confirmation**

Present both the PR details and reviewer recommendations:

```markdown
🚀 **Ready to Create PR**

**Title:** EADL-1234 - Add circuit breaker retry logic

**Description:**
### 🚀 Description, Motivation, and Context
Adds circuit breaker pattern with configurable retry logic for LLM calls.

### 📖 Issues and Related PRs
- **JIRA ticket:** [EADL-1234](<metadata.jiraBaseUrl>/browse/EADL-1234)

### 🖼 Screenshots
Not applicable.

### 🧪 How This Was Tested
- [ ] Ran locally and verified
- [x] Created tests (unit and/or E2E)
- [ ] Automated testing unnecessary (chores, doc updates, etc.)

### ☑️ Required Items Complete
- [x] Unit tests written
- [ ] Integration tests written
- [ ] Coverage verified
- [ ] Functionally tested
- [ ] Deployable to production
- [ ] Uses feature flags <List of flag names>
- [ ] README updated
- [ ] Build passes

### 🛡️ Security
Not applicable.

---

🎯 **Recommended Reviewers (based on git history):**

**test1_cisco** (3/3 files, 33 total commits)
| File | Commits | Last Active |
|------|---------|-------------|
| circuit.py | 23 | 1 week ago |
| llm_factory.py | 6 | 1 month ago |
| test_circuit.py | 4 | 3 months ago |

**test2_cisco** (2/3 files, 23 total commits)
| File | Commits | Last Active |
|------|---------|-------------|
| llm_factory.py | 15 | 3 weeks ago |
| circuit.py | 8 | 2 months ago |

**test3_cisco** (1/3 files, 12 total commits)
| File | Commits | Last Active |
|------|---------|-------------|
| test_circuit.py | 12 | 2 weeks ago |

---

Create PR with these reviewers? [Y/n]
```

9. **Create PR with Reviewers**

After user confirms, create the PR with reviewers in one command. Use a HEREDOC or file-based body input so the generated body preserves the standard template formatting exactly:

```bash
gh pr create \
  --repo <metadata.repository> \
  --base main \
  --head "$(git branch --show-current)" \
  --title "TITLE" \
  --body-file <path-to-rendered-body.md> \
  --reviewer <reviewer1>,<reviewer2>,<reviewer3>
```

10. **Display PR Link**

After creating the PR, display the URL as a clickable hyperlink so the user can easily navigate to it.
