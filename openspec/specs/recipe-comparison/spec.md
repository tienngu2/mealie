# recipe-comparison Specification

## Purpose
Let users see how two recipes differ, side by side, without opening both. The page only reads recipes and never changes them.

## Requirements

### Requirement: Recipe comparison page
The frontend SHALL provide a page at `/g/{groupSlug}/recipes/compare`, reachable from the main sidebar, with two recipe pickers labelled A and B. The page SHALL show a comparison only when two different recipes are selected. The selected recipes SHALL be reflected in the page address as the query parameters `a` and `b` (recipe slugs), and opening an address that contains both parameters SHALL load that comparison.

#### Scenario: Compare two recipes
- **WHEN** the user selects a recipe in picker A and a different recipe in picker B
- **THEN** the page shows the details comparison and the ingredient comparison for the two recipes, and the address contains both slugs

#### Scenario: Open a shared comparison
- **WHEN** the user opens `/g/{groupSlug}/recipes/compare?a=<slug-1>&b=<slug-2>` for two existing recipes
- **THEN** both recipes are loaded and compared without further input

#### Scenario: Only one recipe selected
- **WHEN** only one recipe is selected
- **THEN** the page shows a hint to select a second recipe and no comparison

#### Scenario: Same recipe twice
- **WHEN** the user selects the same recipe in both pickers
- **THEN** the page shows a message that two different recipes are needed and no comparison

#### Scenario: Load error
- **WHEN** a selected recipe cannot be loaded
- **THEN** the page shows an error message with a way to retry instead of a partial comparison

### Requirement: Details comparison
The comparison SHALL list prep time, cook time, total time, servings and yield for both recipes, one row each. The cook time row SHALL use the recipe's perform time field, which the app labels "Cook Time"; the separate legacy cook time field is not shown or editable anywhere in the app and SHALL NOT be compared. A row whose two values differ SHALL be marked as different. A value that is not set SHALL be shown as "Not set"; two unset values are equal. Time and yield text SHALL be compared after trimming whitespace and ignoring letter case.

#### Scenario: Differing value is marked
- **WHEN** recipe A has a total time of "30 minutes" and recipe B has "45 minutes"
- **THEN** the total time row is marked as different

#### Scenario: Equal values are not marked
- **WHEN** recipe A has the total time "30 Minutes" and recipe B has "30 minutes"
- **THEN** the total time row is not marked

#### Scenario: Missing value
- **WHEN** recipe A has a cook time and recipe B has none
- **THEN** recipe B's cell shows "Not set" and the row is marked as different

#### Scenario: Both values missing
- **WHEN** neither recipe has a cook time
- **THEN** both cells show "Not set" and the row is not marked

### Requirement: Ingredient comparison
Ingredient lines SHALL be matched between the two recipes by the name of the food, ignoring letter case and surrounding whitespace; a line without a food SHALL be matched by its text. Section titles and blank lines SHALL be ignored. Lines of the same recipe that match the same name SHALL be combined into one entry. The comparison SHALL list the entries found in both recipes (with the amount from each recipe), the entries only in recipe A, and the entries only in recipe B, each group with its count. The amounts of a matched entry SHALL be marked as different when the quantity or the unit differs; units SHALL NOT be converted.

#### Scenario: Shared ingredient with the same amount
- **WHEN** both recipes contain "2 cups flour"
- **THEN** flour appears under the shared ingredients and is not marked as different

#### Scenario: Shared ingredient with different amounts
- **WHEN** recipe A has "2 cups flour" and recipe B has "3 cups flour"
- **THEN** flour appears under the shared ingredients with both amounts and is marked as different

#### Scenario: Different units are not converted
- **WHEN** recipe A has "1 cup milk" and recipe B has "240 ml milk"
- **THEN** milk is shared and marked as different

#### Scenario: Ingredient in only one recipe
- **WHEN** recipe A contains eggs and recipe B does not
- **THEN** eggs are listed under "only in A" and not under the shared ingredients

#### Scenario: Names match regardless of case
- **WHEN** recipe A has the food "Butter" and recipe B has the food "butter"
- **THEN** butter is a shared ingredient

#### Scenario: Section titles and blank lines are ignored
- **WHEN** a recipe has a line that is only a section title such as "For the sauce"
- **THEN** it appears in none of the groups

#### Scenario: Repeated ingredient is combined
- **WHEN** recipe A lists salt in two different lines
- **THEN** salt appears once, with both amounts

### Requirement: Read-only behavior
The comparison page SHALL NOT create, modify or delete any recipe.

#### Scenario: No side effects
- **WHEN** the user compares two recipes
- **THEN** no request other than reading recipes is sent

### Requirement: Localization boundary
New user-visible strings SHALL be added to the `en-US` locale only; other locale files SHALL NOT be modified.

#### Scenario: Only en-US changes
- **WHEN** the change is complete
- **THEN** the diff contains no modified locale files other than `en-US`
