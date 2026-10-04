# Design

## Context

- Frontend only. `GET /api/recipes/{slug}` already returns everything needed (times, servings, yield and `recipeIngredient` with quantity, unit, food, note and title), and `GET /api/recipes?search=` returns a page of recipes for a picker.
- At the pinned commit recipe times are free text (no numeric columns); servings is a number; yield is a number plus free text.
- Existing building blocks: `useRecipeSearch(api)` (debounced search), `useUserApi().recipes.getOne`, `useFraction` for fractions, the page layout pattern of the Recipe Quality page, and Vuetify's `v-autocomplete`.
- The existing `RecipeDialogSearch` has a "select" mode, but it relies on `$attrs.selected`, which Vue 3 does not populate for a declared `selected` emit, so it navigates to the recipe instead of selecting it. It is only used by the header search. It is not reused (decision 3).
- The frontend lints `vue/no-v-html`, so ingredient text is rendered as plain text, not HTML.

## Goals / Non-Goals

**Goals:**
- The comparison rules are a pure function, testable without mounting a page or calling the API.
- The page reuses existing Mealie patterns so it looks native.
- A comparison is shareable through the page address.

**Non-Goals:**
- Comparing instructions or more than two recipes.
- Unit conversion or fuzzy ingredient matching.
- Any backend, database or generated-code change.

## Decisions

1. **Comparison logic is a pure function with a small stateful wrapper, in one composable module.** `frontend/composables/recipes/use-recipe-compare.ts` exports `compareRecipes(a, b)` and `useRecipeCompare(fetchRecipe)`. `compareRecipes` takes a structural subset of `Recipe` (names, times, servings, yield, ingredients) and returns the detail rows, the shared, only-A and only-B ingredient entries, and counts of differences. `useRecipeCompare` holds the selected slugs, loading and error state, and the same-recipe guard. *Alternative:* logic inside the page component. Rejected: not testable without mounting.

2. **Ingredients match by food name; lines without a food match by their text.** Matching key is the name trimmed, with inner whitespace collapsed and lower-cased. Section titles (a title, no food and no note) and blank lines are skipped. Lines of one recipe with the same key are combined into one entry with all their amounts. There is no fuzzy matching, so "tomato" and "tomatoes" are different entries; this is a documented limitation, not a bug. *Alternative:* fuzzy or plural-aware matching. Rejected: it would add surprising false matches and is out of scope.

3. **A small new picker component instead of the existing search dialog.** `frontend/components/Domain/Recipe/RecipeSelect.vue` wraps `v-autocomplete` over `useRecipeSearch(api)`: the server filters (`no-filter`), the first page of recipes is loaded as soon as the picker is shown so the list is ready when it opens, and the currently selected recipe is always kept in the item list so its name stays visible. *Alternative:* fix and reuse `RecipeDialogSearch`. Rejected: it is a modal built for navigation, and changing it would touch the global header search.

4. **Amounts are compared structurally, never converted.** An entry's amount key is the numeric quantity plus the normalized unit name (abbreviation when there is no name). Two entries are "different" when the amount keys differ, so "1 cup" and "240 ml" are different. For display, the amount is the quantity (with fractions through `useFraction`), the unit and any note, as plain text.

5. **The page address is the source of truth.** The page reads `a` and `b` from the query, loads both recipes with `getOne`, and each picker updates the query with `router.replace`. Opening a shared address therefore loads the comparison directly, and the browser back button is not filled with every selection.

6. **Details rows.** Fixed rows in this order: prep time, cook time, total time, servings, yield. The cook time row reads the recipe's `performTime`, which the app labels "Cook Time"; the separate legacy `cookTime` field is never shown or edited in the UI (checked: no use in components, pages or composables), so comparing it would always show "Not set". Text is compared after trim and lower-casing; servings compare as numbers (0 means not set); yield is the quantity and the text together (both empty means not set). An unset value is shown as "Not set"; two unset values are equal.

## Risks / Trade-offs

- **Name-only matching misses synonyms and plurals** → documented in the page hint and in the non-goals; the "only in A / only in B" groups make mismatches visible rather than hidden.
- **Repeated lines are listed, not added up** → "1 tsp + 2 tsp" in one recipe and "3 tsp" in the other are marked as different, because adding amounts would need unit conversion; the page note says amounts are compared as written.
- **Free-text times cannot be compared numerically** ("1 hr" and "60 minutes" are different) → rows are marked as different, never judged as better or worse.
- **Large ingredient lists** → a recipe rarely has more than a few dozen lines, so the matching (a map lookup) is not a concern.
- **A deep link with a bad slug** → the load fails, and the page shows the error state with Retry instead of a partial comparison.

## Open Questions

- Whether the recipe page's action menu should also offer "Compare with...". It would touch an existing component and is left for a later change.
