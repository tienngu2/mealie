# recipe-quality-report Specification

## Purpose
Help users find and fix incomplete recipes by reporting deterministic quality issues for each recipe they can see, through an API endpoint and a frontend page. The report is read-only and never changes recipe data.

## Requirements

### Requirement: Quality report endpoint
The system SHALL provide an authenticated, read-only endpoint `GET /api/recipes/quality-report` that returns the recipes that have at least one quality issue, a total count, and a summary of how many recipes have each issue type.

#### Scenario: Only flagged recipes are returned
- **WHEN** a user requests the report and the household has one complete recipe and one recipe with no instructions
- **THEN** the response lists only the recipe with no instructions, and the summary count for `no-instructions` is 1

#### Scenario: Authentication required
- **WHEN** a request without a valid token is made to the endpoint
- **THEN** the response is 401 and no recipe data is returned

#### Scenario: Complete library
- **WHEN** no recipe has any issue
- **THEN** the response contains an empty item list, a total of 0, and a summary with no issue counts above zero

### Requirement: Issue detection rules
The system SHALL flag a recipe with each of the following issue codes when the condition holds, and SHALL NOT flag it otherwise.

- `no-ingredients`: the recipe has no ingredient lines.
- `no-instructions`: the recipe has no instruction step with non-blank text.
- `thin-instructions`: the recipe has instruction text, but the combined length of all step texts (after trimming) is fewer than 40 characters. A recipe flagged `no-instructions` SHALL NOT also be flagged `thin-instructions`.
- `missing-times`: prep time, cook time, perform time, and total time are all empty (blank or whitespace-only text). Times are free text in this version of Mealie, so only presence is checked, never the value.
- `missing-yield`: servings is 0 or unset, yield quantity is 0 or unset, and yield text is empty.
- `unparsed-ingredients`: at least one ingredient line has non-blank note text, no food, and no unit. Section titles (lines without note text) are ignored.

#### Scenario: Missing times
- **WHEN** a recipe has no prep, cook, perform, or total time
- **THEN** it is flagged `missing-times`

#### Scenario: A single time is enough
- **WHEN** a recipe has only a total time of 30 minutes
- **THEN** it is not flagged `missing-times`

#### Scenario: Blank time text counts as missing
- **WHEN** every time field is empty or only whitespace
- **THEN** it is flagged `missing-times`

#### Scenario: Thin instructions
- **WHEN** a recipe's only step reads "Mix and bake." (13 characters)
- **THEN** it is flagged `thin-instructions` and not `no-instructions`

#### Scenario: Blank steps count as no instructions
- **WHEN** a recipe has steps but every step text is blank
- **THEN** it is flagged `no-instructions`

#### Scenario: Unparsed ingredient
- **WHEN** an ingredient line has note "2 cups flour, sifted" and no food and no unit
- **THEN** the recipe is flagged `unparsed-ingredients`

#### Scenario: Parsed ingredient and section title
- **WHEN** an ingredient line has a food and a unit, and another line is only a section title
- **THEN** neither line causes `unparsed-ingredients`

#### Scenario: Servings-only yield
- **WHEN** a recipe has servings 4 and no yield text
- **THEN** it is not flagged `missing-yield`

#### Scenario: Multiple issues
- **WHEN** a recipe has no ingredients, no times, and no yield
- **THEN** it is flagged with all three of `no-ingredients`, `missing-times`, and `missing-yield`

### Requirement: Report content and ordering
Each returned item SHALL contain the recipe's id, slug, name, and image reference, and the list of issues, where each issue has a code and a severity of `error` or `warning`. `no-ingredients` and `no-instructions` SHALL have severity `error`; all other codes SHALL have severity `warning`. Items SHALL be ordered by number of issues descending, then by recipe name ascending (case-insensitive).

#### Scenario: Ordering
- **WHEN** recipe A has 1 issue, recipe B has 3 issues, and recipe C has 3 issues with a name that sorts after B
- **THEN** the items are ordered B, C, A

### Requirement: Filtering and pagination
The endpoint SHALL accept an optional `code` query parameter (repeatable) that restricts the returned items to recipes with at least one of the given codes, and SHALL accept `page` and `perPage` parameters. The summary SHALL always describe all flagged recipes the user can see, regardless of `code` and pagination. An unknown `code` value SHALL result in a 422 response.

#### Scenario: Filter by code
- **WHEN** the user requests the report with `code=missing-yield`
- **THEN** every returned item has `missing-yield` among its issues, and the summary still counts every issue type across all flagged recipes

#### Scenario: Pagination
- **WHEN** 25 recipes are flagged and the user requests `perPage=10&page=3`
- **THEN** 5 items are returned and the total is 25

#### Scenario: Unknown code
- **WHEN** the user requests `code=not-a-real-code`
- **THEN** the response is 422

### Requirement: Scope and isolation
The report SHALL cover only recipes in the requesting user's household. Recipes from other households or groups SHALL NOT appear in items or in summary counts.

#### Scenario: Other household's recipes are excluded
- **WHEN** another household in the same group has an incomplete recipe
- **THEN** it does not appear in the user's report and is not counted in the summary

#### Scenario: Other group's recipes are excluded
- **WHEN** a different group has an incomplete recipe
- **THEN** it does not appear in the user's report and is not counted in the summary

### Requirement: Read-only behavior
Requesting the report SHALL NOT create, modify, or delete any recipe, and SHALL NOT change any recipe's `updatedAt` value.

#### Scenario: No side effects
- **WHEN** the report is requested twice in a row
- **THEN** both responses are identical and no recipe's `updatedAt` changed

### Requirement: Recipe Quality page
The frontend SHALL provide a page at `/g/{groupSlug}/recipes/quality`, reachable from the main sidebar, that shows the summary as one chip per issue type with its count, and a list of flagged recipes. Selecting a chip SHALL filter the list to that issue type, and selecting it again SHALL clear the filter. Each list entry SHALL show the recipe name, its issues in readable language, and a link that opens the recipe.

#### Scenario: Chip filters the list
- **WHEN** the user selects the "Missing yield" chip
- **THEN** only recipes with that issue are listed, and selecting the chip again shows all flagged recipes

#### Scenario: Open a recipe to fix it
- **WHEN** the user selects a recipe in the list
- **THEN** the recipe page opens

#### Scenario: Nothing to fix
- **WHEN** the report has no flagged recipes
- **THEN** the page shows a message that all recipes look complete

#### Scenario: Load error
- **WHEN** the request fails
- **THEN** the page shows an error message instead of an empty list

### Requirement: Localization boundary
New user-visible strings SHALL be added to the `en-US` locale only; other locale files SHALL NOT be modified.

#### Scenario: Only en-US changes
- **WHEN** the change is complete
- **THEN** the diff contains no modified locale files other than `en-US`
