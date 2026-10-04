## 1. Comparison logic

- [x] 1.1 Add `frontend/composables/recipes/use-recipe-compare.ts` with `compareRecipes` (detail rows, ingredient matching and grouping, difference counts) and `useRecipeCompare` (selected slugs, loading and error state, retry, same-recipe guard). Verify: `yarn lint` passes.
- [x] 1.2 Cover every scenario of the details and ingredient requirements in `use-recipe-compare.test.ts`. Verify: `yarn test:ci` passes.

## 2. Page

- [x] 2.1 Add the `RecipeSelect.vue` picker component. Verify: it renders in the browser (see 3.1).
- [x] 2.2 Add the page `frontend/pages/g/[groupSlug]/recipes/compare/index.vue` (two pickers, details table, ingredient groups, hint, same-recipe, loading and error states, address query). Verify: it renders in the browser (see 3.1).
- [x] 2.3 Add the sidebar entry beside Recipe Quality, register the `compare` icon, and add the `en-US` strings only. Verify: `git diff --stat` shows no locale file other than `en-US`; the entry appears in the sidebar.

## 3. Verification and archive

- [x] 3.1 Seed recipes through the API and check the page in the browser: select two recipes, the details rows and their marks, shared, only-A and only-B ingredients, the hint, the same-recipe message, a shared address, the error state with Retry, and that only read requests are sent.
- [x] 3.2 Run `task validate` and `task security`; compare the security findings with `docs/agents/tech-debt.md`.
- [x] 3.3 Update the agent docs, verify the change against its spec, archive it, and confirm `openspec list` shows no active change.
