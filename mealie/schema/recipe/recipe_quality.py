from enum import StrEnum
from typing import Any

from pydantic import UUID4

from mealie.schema._mealie.mealie_model import MealieModel


class RecipeQualityCode(StrEnum):
    NO_INGREDIENTS = "no-ingredients"
    NO_INSTRUCTIONS = "no-instructions"
    THIN_INSTRUCTIONS = "thin-instructions"
    MISSING_TIMES = "missing-times"
    MISSING_YIELD = "missing-yield"
    UNPARSED_INGREDIENTS = "unparsed-ingredients"


class RecipeQualitySeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"


class RecipeQualityIssue(MealieModel):
    code: RecipeQualityCode
    severity: RecipeQualitySeverity


class RecipeQualityItem(MealieModel):
    recipe_id: UUID4
    slug: str
    name: str | None = None
    image: Any | None = None
    issues: list[RecipeQualityIssue]


class RecipeQualityReport(MealieModel):
    items: list[RecipeQualityItem]
    total: int
    """Number of flagged recipes matching the `code` filter (before pagination)"""
    page: int
    per_page: int
    summary: dict[RecipeQualityCode, int]
    """Flagged-recipe count per code across all flagged recipes, ignoring the `code` filter and pagination"""
