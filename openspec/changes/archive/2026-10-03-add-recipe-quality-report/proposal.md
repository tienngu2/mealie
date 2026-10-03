# Proposal

## Why

Mealie recipes are often imported or typed in with gaps: no times, no yield, ingredients that are only free text, one-line instructions. Nothing in the product shows which recipes are incomplete, so cleaning up a library of hundreds of recipes means opening each one. A report that lists exactly what is missing, and links to the recipe, turns that into a short checklist.

## What Changes

- New read-only API endpoint `GET /api/recipes/quality-report` that evaluates the recipes the user can see and returns, per recipe, a list of deterministic quality issues, plus a summary count per issue type. It never modifies recipes.
- New frontend page `Recipe Quality` (`/g/{groupSlug}/recipes/quality`) with summary chips (click to filter by issue type) and a list of flagged recipes, each linking to the recipe so the user can fix it.
- New sidebar entry for the page, next to Recipe Finder.
- English strings only (other locales are managed by Crowdin).
- No database migration. No change to existing endpoints or recipe data.

Issue types in scope (all rule-based, no AI):

| Code | Flagged when |
|---|---|
| `no-ingredients` | the recipe has no ingredient lines |
| `no-instructions` | the recipe has no instruction steps with text |
| `thin-instructions` | instruction text across all steps totals fewer than 40 characters |
| `missing-times` | prep, cook, perform and total time are all empty (times are free text at this version, so values are never parsed) |
| `missing-yield` | servings, yield quantity and yield text are all empty |
| `unparsed-ingredients` | one or more ingredient lines have free text only (no food and no unit) |

## Non-goals

- Automatic fixes or AI suggestions; the report only points at problems.
- Persisting results, scheduling, or notifications; the report is computed on request.
- Per-user configurable rules or thresholds.
- Checking images, descriptions, tags, categories, or nutrition.
- Changing how recipes are stored or validated on save.

## Capabilities

### New Capabilities
- `recipe-quality-report`: evaluate recipes against deterministic completeness rules and present the findings through an API endpoint and a frontend page.

### Modified Capabilities

(none)

## Impact

- Backend: new schema `mealie/schema/recipe/recipe_quality.py`, new service `mealie/services/recipe/recipe_quality_service.py`, new repository method `RepositoryRecipes.get_quality_inputs()`, one new route in `mealie/routes/recipe/recipe_crud_routes.py` (must be declared before `/{slug}`).
- Generated code: `task dev:generate` updates `mealie/schema/recipe/__init__.py` exports, `frontend/lib/api/types/recipe.ts`, and the pytest route helpers.
- Frontend: new page, API client method in `frontend/lib/api/user/recipes/recipe.ts`, nav entry in the default layout, `en-US` strings.
- Tests: unit tests for the rules, integration tests for the endpoint (including multi-tenant isolation), Vitest for the page's helper logic.
- Performance: the endpoint scans all visible recipes on each request (O(n)); acceptable for household-sized libraries, documented in the design.
- Security: read-only; must respect group and household scoping.
