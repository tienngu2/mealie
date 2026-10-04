# Proposal

## Why

Choosing between two similar recipes, such as two lasagnas or an old and a new version of a family favorite, means opening both and comparing them by eye. Mealie has no way to see the differences side by side, so it is hard to tell which one is quicker, makes more, or needs fewer ingredients.

## What Changes

- New frontend page `Compare Recipes` (`/g/{groupSlug}/recipes/compare`): pick two recipes and see their times, servings and yield, and their ingredients, side by side, with the differences marked.
- Ingredients are matched by name. Ingredients found in both recipes are shown with both amounts (marked when the amounts differ); ingredients found in only one recipe are listed separately.
- The two chosen recipes are kept in the page address (`?a=<slug>&b=<slug>`), so a comparison can be bookmarked or shared.
- New sidebar entry next to Recipe Quality.
- English strings only (other locales are managed by Crowdin).
- Frontend only: no new API endpoint, no database migration, no change to recipe data. Recipes are only read.

## Non-goals

- Comparing instructions, nutrition, images, tags or categories.
- Comparing more than two recipes.
- Converting units or scaling servings so amounts can be compared across units.
- Fuzzy matching of ingredient names, such as singular and plural forms.
- Editing either recipe from the comparison page.

## Capabilities

### New Capabilities
- `recipe-comparison`: choose two recipes and compare their details and ingredients side by side.

### Modified Capabilities

(none)

## Impact

- Frontend: new page, a recipe picker component, a composable with the comparison logic and its Vitest tests, one sidebar entry, one icon registration, `en-US` strings.
- Backend: none.
- Tests: Vitest unit tests for the comparison logic; a browser check of the page.
- Security: read-only; uses the existing authenticated recipe endpoints, so group and household access rules still apply.
