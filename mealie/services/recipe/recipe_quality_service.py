"""
Deterministic completeness rules for recipes.

Everything here is a pure function over `RecipeQualityInput`: no database, no I/O, no side effects.
The repository (`RepositoryRecipes.get_quality_inputs`) gathers the facts with three narrow queries, so
the rules never need a fully loaded `Recipe`.

To add a rule, add a `RecipeQualityCode`, a predicate, and one entry in `RULES`, then add a test.
"""

from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field

from pydantic import UUID4

from mealie.schema.recipe.recipe_quality import (
    RecipeQualityCode,
    RecipeQualityIssue,
    RecipeQualityItem,
    RecipeQualityReport,
    RecipeQualitySeverity,
)

THIN_INSTRUCTIONS_MIN_CHARS = 40
"""Combined, trimmed step text shorter than this (but not empty) is flagged as thin"""


@dataclass(frozen=True, slots=True)
class IngredientFacts:
    note: str | None = None
    has_food: bool = False
    has_unit: bool = False


@dataclass(frozen=True, slots=True)
class RecipeQualityInput:
    """The facts the rules need about one recipe."""

    id: UUID4
    slug: str
    name: str | None = None
    image: str | None = None

    prep_time: str | None = None
    cook_time: str | None = None
    perform_time: str | None = None
    total_time: str | None = None

    recipe_servings: float | None = 0
    recipe_yield_quantity: float | None = 0
    recipe_yield: str | None = None

    ingredients: Sequence[IngredientFacts] = field(default_factory=tuple)
    step_texts: Sequence[str | None] = field(default_factory=tuple)


def _has_text(value: str | None) -> bool:
    return bool(value and value.strip())


def _instruction_chars(recipe: RecipeQualityInput) -> int:
    return sum(len(text.strip()) for text in recipe.step_texts if text and text.strip())


def _no_ingredients(recipe: RecipeQualityInput) -> bool:
    return len(recipe.ingredients) == 0


def _no_instructions(recipe: RecipeQualityInput) -> bool:
    return _instruction_chars(recipe) == 0


def _thin_instructions(recipe: RecipeQualityInput) -> bool:
    chars = _instruction_chars(recipe)
    return 0 < chars < THIN_INSTRUCTIONS_MIN_CHARS


def _missing_times(recipe: RecipeQualityInput) -> bool:
    # Times are free text at this schema version (no numeric columns), so only emptiness is checked.
    texts = (recipe.prep_time, recipe.cook_time, recipe.perform_time, recipe.total_time)
    return not any(_has_text(t) for t in texts)


def _missing_yield(recipe: RecipeQualityInput) -> bool:
    return not recipe.recipe_servings and not recipe.recipe_yield_quantity and not _has_text(recipe.recipe_yield)


def _unparsed_ingredients(recipe: RecipeQualityInput) -> bool:
    # Section titles have no note text, so they are ignored.
    return any(_has_text(i.note) and not i.has_food and not i.has_unit for i in recipe.ingredients)


RULES: tuple[tuple[RecipeQualityCode, RecipeQualitySeverity, Callable[[RecipeQualityInput], bool]], ...] = (
    (RecipeQualityCode.NO_INGREDIENTS, RecipeQualitySeverity.ERROR, _no_ingredients),
    (RecipeQualityCode.NO_INSTRUCTIONS, RecipeQualitySeverity.ERROR, _no_instructions),
    (RecipeQualityCode.THIN_INSTRUCTIONS, RecipeQualitySeverity.WARNING, _thin_instructions),
    (RecipeQualityCode.MISSING_TIMES, RecipeQualitySeverity.WARNING, _missing_times),
    (RecipeQualityCode.MISSING_YIELD, RecipeQualitySeverity.WARNING, _missing_yield),
    (RecipeQualityCode.UNPARSED_INGREDIENTS, RecipeQualitySeverity.WARNING, _unparsed_ingredients),
)


def assess_recipe(recipe: RecipeQualityInput) -> list[RecipeQualityIssue]:
    """Return every issue found for a recipe, in rule-table order. Empty when the recipe looks complete."""
    return [RecipeQualityIssue(code=code, severity=severity) for code, severity, check in RULES if check(recipe)]


def build_report(
    recipes: Iterable[RecipeQualityInput],
    codes: Sequence[RecipeQualityCode] | None = None,
    page: int = 1,
    per_page: int = 50,
) -> RecipeQualityReport:
    """
    Assess recipes and build a report.

    - `summary` counts flagged recipes per code across *all* flagged recipes, ignoring `codes` and pagination.
    - `codes` restricts the returned items to recipes with at least one of those codes.
    - Items are ordered by issue count (descending), then name (case-insensitive), then slug.
    """
    summary = dict.fromkeys(RecipeQualityCode, 0)
    flagged: list[RecipeQualityItem] = []

    for recipe in recipes:
        issues = assess_recipe(recipe)
        if not issues:
            continue

        for issue in issues:
            summary[issue.code] += 1

        flagged.append(
            RecipeQualityItem(
                recipe_id=recipe.id,
                slug=recipe.slug,
                name=recipe.name,
                image=recipe.image,
                issues=issues,
            )
        )

    if codes:
        wanted = set(codes)
        flagged = [item for item in flagged if any(issue.code in wanted for issue in item.issues)]

    flagged.sort(key=lambda item: (-len(item.issues), (item.name or "").casefold(), item.slug))

    start = (page - 1) * per_page
    return RecipeQualityReport(
        items=flagged[start : start + per_page],
        total=len(flagged),
        page=page,
        per_page=per_page,
        summary=summary,
    )
