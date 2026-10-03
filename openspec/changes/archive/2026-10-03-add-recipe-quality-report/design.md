# Design

## Context

- `GET /api/recipes/suggestions` is the closest precedent: its own schema file (`mealie/schema/recipe/recipe_suggestion.py`), logic outside the controller (`mealie/repos/_recipe_suggestions.py`), and a plain response model. This change follows the same shape.
- `RepositoryRecipes` is `HouseholdRepositoryGeneric[Recipe, RecipeModel]`, and its `get_all()` goes through an overridden `page_all` that returns `RecipeSummary` items, which carry no ingredients or steps. So the rules cannot be fed from `get_all()`; a dedicated repository method with narrow column queries is used instead (decision 3).
- All routes in `recipe_crud_routes.py` share `router = UserAPIRouter(prefix="/recipes")`, and `/{slug}` is a catch-all `GET`; a fixed path like `/quality-report` must be declared before it, as `/suggestions` is.
- At the pinned commit recipe times are free text only (`prep_time`, `cook_time`, `perform_time`, `total_time`); there are no numeric `*_seconds` columns. Servings are `recipe_servings`, `recipe_yield_quantity`, and `recipe_yield`.
- Frontend types in `frontend/lib/api/types/` are generated from Pydantic schemas (`task dev:generate`, which needs `json2ts` on PATH) and must not be hand-edited.

## Goals / Non-Goals

**Goals:**
- Rules are pure functions over a small input dataclass, testable without a database or HTTP.
- The endpoint adds no write path and no new table.
- The page reuses existing Mealie components and patterns (title block, chips, cards) so it looks native.

**Non-Goals:**
- Caching or precomputing results.
- A plug-in or user-configurable rule system.

## Decisions

1. **Rules live in a service module, not in the controller or repo.** New `mealie/services/recipe/recipe_quality_service.py` exposes `assess_recipe(recipe: RecipeQualityInput) -> list[RecipeQualityIssue]` and `build_report(recipes, codes, page, per_page) -> RecipeQualityReport`. `RecipeQualityInput` and `IngredientFacts` are small frozen dataclasses holding only the facts the rules need. The controller only loads inputs and calls the service. *Alternative:* SQL queries per rule in the repository. Rejected: the rules combine fields and inspect text; SQL would be harder to test and to read, and would couple rules to the schema.

2. **Rules are a declarative table of `(code, severity, predicate)`.** Adding a rule is one entry plus a test. Severity is fixed per code: `no-ingredients` and `no-instructions` are `error`, everything else `warning`. *Alternative:* an enum with an `if` chain. Rejected: harder to keep the summary and the ordering consistent with the rule list.

3. **Load facts with `RepositoryRecipes.get_quality_inputs()` (three narrow column queries) and evaluate in Python; paginate after evaluation.** The summary must describe all flagged recipes, so a full scan is unavoidable. The method scopes with the same `_filter_builder()` that `page_all` uses, so the controller's household-scoped repo (`self.recipes`) gives the isolation the spec requires. Ingredient and step rows are fetched in chunks of 500 recipe ids to stay below database bound-parameter limits. Only the needed columns are read, never full `Recipe` objects. *Alternative:* `get_all()`. Rejected after investigation: it returns `RecipeSummary` without ingredients or steps.

4. **Response shape.**
   ```
   RecipeQualityReport { items: [RecipeQualityItem], total: int, page: int, per_page: int, summary: {code: count} }
   RecipeQualityItem  { recipe_id, slug, name, image, issues: [RecipeQualityIssue] }
   RecipeQualityIssue { code: RecipeQualityCode, severity: "error"|"warning" }
   ```
   `RecipeQualityCode` is a `StrEnum`, so FastAPI returns 422 for an unknown `code` query value for free and the TypeScript type is generated. The summary always contains every code (zero when none), so the UI can render stable chips. Schemas use the existing `MealieModel` base (camelCase aliases on the wire). *Alternative:* reuse `PaginationBase`. Rejected: its shape has no room for the summary, and it is built for DB-level pagination.

5. **Issue detail is just the code.** The page maps each code to an `en-US` message. No server-side prose, so there is nothing to translate on the backend.

6. **Rule details that need a decision**
   - `unparsed-ingredients` checks `food is None and unit is None and note.strip()`. Counting lines with only a quantity (for example "2 eggs" with a food) as fine avoids false positives; section titles have no note and are ignored.
   - `missing-times` treats a time as present if any of the four text fields has non-blank text. Values are never parsed (free text at this version).
   - Numeric time consistency (prep + perform vs total) is out of scope: there are no numeric time columns at the pinned commit.
   - `thin-instructions` uses a fixed 40-character threshold on the trimmed, concatenated step text. This is deliberately simple and documented; it is not configurable.

7. **Frontend.** New page `frontend/pages/g/[groupSlug]/recipes/quality/index.vue`; API method `getQualityReport` on the recipes client; a small composable `use-recipe-quality.ts` holds loading state, chip selection, and code-to-message mapping so the logic is Vitest-testable without mounting the page. Navigation entry added beside Recipe Finder in the default layout. Chip filtering is done by calling the endpoint with `code` (server-side), keeping the page consistent with pagination.

## Risks / Trade-offs

- **Full scan per request** → fine for typical libraries; the response is not cached. If it proves slow, add caching without an API change.
- **Heuristic rules produce false positives** (for example a deliberately short recipe) → severity `warning`, wording says "check", and nothing is auto-changed.
- **Memory of large libraries** → only narrow columns are read; measured during implementation with a seeded larger library and recorded in the verification notes.
- **Route ordering mistake** (`/{slug}` would swallow `quality-report`) → covered by an integration test that fails if the route is shadowed.
- **Generated files drift** → `task dev:generate` is an explicit task step, and `task validate` runs the tests that cover generated route helpers.

## Open Questions

- Whether the sidebar entry should be hidden for users without any recipes. Can be decided during the UI task without changing specs.
