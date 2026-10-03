from dataclasses import replace
from uuid import uuid4

import pytest

from mealie.schema.recipe.recipe_quality import RecipeQualityCode, RecipeQualitySeverity
from mealie.services.recipe.recipe_quality_service import (
    THIN_INSTRUCTIONS_MIN_CHARS,
    IngredientFacts,
    RecipeQualityInput,
    assess_recipe,
    build_report,
)

LONG_STEP = "Combine everything in a large bowl, mix well, then bake until golden brown."


def parsed_ingredient() -> IngredientFacts:
    return IngredientFacts(note="", has_food=True, has_unit=True)


def make_recipe(name: str = "Complete", **overrides) -> RecipeQualityInput:
    """A recipe that passes every rule unless a field is overridden."""
    data = {
        "id": uuid4(),
        "name": name,
        "slug": name.lower().replace(" ", "-"),
        "ingredients": [parsed_ingredient()],
        "step_texts": [LONG_STEP],
        "total_time": "30 minutes",
        "recipe_servings": 4,
    }
    data.update(overrides)
    return RecipeQualityInput(**data)


def codes(recipe: RecipeQualityInput) -> set[RecipeQualityCode]:
    return {issue.code for issue in assess_recipe(recipe)}


def test_complete_recipe_has_no_issues():
    assert assess_recipe(make_recipe()) == []


def test_no_ingredients():
    assert RecipeQualityCode.NO_INGREDIENTS in codes(make_recipe(ingredients=[]))


def test_no_instructions_when_there_are_no_steps():
    result = codes(make_recipe(step_texts=[]))
    assert RecipeQualityCode.NO_INSTRUCTIONS in result
    assert RecipeQualityCode.THIN_INSTRUCTIONS not in result


def test_null_step_text_is_treated_as_no_instructions():
    assert RecipeQualityCode.NO_INSTRUCTIONS in codes(make_recipe(step_texts=[None]))


def test_blank_steps_count_as_no_instructions():
    result = codes(make_recipe(step_texts=["   ", ""]))
    assert RecipeQualityCode.NO_INSTRUCTIONS in result
    assert RecipeQualityCode.THIN_INSTRUCTIONS not in result


def test_thin_instructions_not_no_instructions():
    result = codes(make_recipe(step_texts=["Mix and bake."]))
    assert RecipeQualityCode.THIN_INSTRUCTIONS in result
    assert RecipeQualityCode.NO_INSTRUCTIONS not in result


@pytest.mark.parametrize(
    ("length", "flagged"),
    [(THIN_INSTRUCTIONS_MIN_CHARS - 1, True), (THIN_INSTRUCTIONS_MIN_CHARS, False)],
)
def test_thin_instructions_boundary(length: int, flagged: bool):
    recipe = make_recipe(step_texts=["x" * length])
    assert (RecipeQualityCode.THIN_INSTRUCTIONS in codes(recipe)) is flagged


def test_instruction_length_is_summed_across_steps_and_trimmed():
    # 20 + 20 = 40 characters once trimmed, so not thin
    steps = ["  " + "a" * 20 + "  ", "b" * 20]
    assert RecipeQualityCode.THIN_INSTRUCTIONS not in codes(make_recipe(step_texts=steps))


def test_missing_times_when_nothing_is_set():
    assert RecipeQualityCode.MISSING_TIMES in codes(make_recipe(total_time=None))


@pytest.mark.parametrize("field", ["prep_time", "cook_time", "perform_time", "total_time"])
def test_any_single_time_is_enough(field: str):
    times = {"prep_time": None, "cook_time": None, "perform_time": None, "total_time": None}
    times[field] = "20 minutes"
    assert RecipeQualityCode.MISSING_TIMES not in codes(make_recipe(**times))


def test_blank_time_text_counts_as_missing():
    recipe = make_recipe(total_time="", prep_time="  ", cook_time=None, perform_time="\t")
    assert RecipeQualityCode.MISSING_TIMES in codes(recipe)


def test_missing_yield_when_everything_is_empty():
    recipe = make_recipe(recipe_servings=0, recipe_yield_quantity=0, recipe_yield=None)
    assert RecipeQualityCode.MISSING_YIELD in codes(recipe)


def test_servings_only_is_enough_for_yield():
    recipe = make_recipe(recipe_servings=4, recipe_yield_quantity=0, recipe_yield=None)
    assert RecipeQualityCode.MISSING_YIELD not in codes(recipe)


def test_yield_text_only_is_enough_for_yield():
    recipe = make_recipe(recipe_servings=0, recipe_yield_quantity=0, recipe_yield="1 loaf")
    assert RecipeQualityCode.MISSING_YIELD not in codes(recipe)


def test_blank_yield_text_is_missing():
    recipe = make_recipe(recipe_servings=0, recipe_yield_quantity=0, recipe_yield="   ")
    assert RecipeQualityCode.MISSING_YIELD in codes(recipe)


def test_unparsed_ingredient_is_flagged():
    unparsed = IngredientFacts(note="2 cups flour, sifted")
    recipe = make_recipe(ingredients=[parsed_ingredient(), unparsed])
    assert RecipeQualityCode.UNPARSED_INGREDIENTS in codes(recipe)


def test_parsed_ingredient_and_section_title_are_not_flagged():
    section = IngredientFacts(note="")  # section titles carry no note text
    recipe = make_recipe(ingredients=[section, parsed_ingredient()])
    assert RecipeQualityCode.UNPARSED_INGREDIENTS not in codes(recipe)


def test_ingredient_with_only_a_food_is_not_flagged():
    eggs = IngredientFacts(note="large", has_food=True)
    assert RecipeQualityCode.UNPARSED_INGREDIENTS not in codes(make_recipe(ingredients=[eggs]))


def test_multiple_issues_are_all_reported():
    recipe = make_recipe(
        ingredients=[],
        total_time=None,
        recipe_servings=0,
    )
    assert codes(recipe) == {
        RecipeQualityCode.NO_INGREDIENTS,
        RecipeQualityCode.MISSING_TIMES,
        RecipeQualityCode.MISSING_YIELD,
    }


def test_severity_by_code():
    recipe = make_recipe(
        ingredients=[],
        step_texts=[],
        total_time=None,
    )
    severity = {issue.code: issue.severity for issue in assess_recipe(recipe)}
    assert severity[RecipeQualityCode.NO_INGREDIENTS] == RecipeQualitySeverity.ERROR
    assert severity[RecipeQualityCode.NO_INSTRUCTIONS] == RecipeQualitySeverity.ERROR
    assert severity[RecipeQualityCode.MISSING_TIMES] == RecipeQualitySeverity.WARNING


# ---- build_report -------------------------------------------------------------------------------------------------


def test_report_only_lists_flagged_recipes_and_counts_them():
    report = build_report([make_recipe("Good"), make_recipe("Bare", step_texts=[])])

    assert [item.name for item in report.items] == ["Bare"]
    assert report.total == 1
    assert report.summary[RecipeQualityCode.NO_INSTRUCTIONS] == 1


def test_report_for_a_complete_library_is_empty():
    report = build_report([make_recipe("A"), make_recipe("B")])

    assert report.items == []
    assert report.total == 0
    assert set(report.summary) == set(RecipeQualityCode)
    assert all(count == 0 for count in report.summary.values())


def test_report_with_no_recipes():
    report = build_report([])
    assert report.items == []
    assert report.total == 0


def test_report_items_carry_recipe_identity():
    recipe = make_recipe("Bare", step_texts=[], image="abc123")
    item = build_report([recipe]).items[0]

    assert item.recipe_id == recipe.id
    assert item.slug == recipe.slug
    assert item.name == "Bare"
    assert item.image == "abc123"


def test_report_ordering_issue_count_then_name():
    one_issue = make_recipe("Alpha", recipe_servings=0)
    three_b = make_recipe("bravo", ingredients=[], recipe_servings=0, step_texts=[])
    three_c = make_recipe("Charlie", ingredients=[], recipe_servings=0, step_texts=[])

    report = build_report([one_issue, three_c, three_b])

    assert [item.name for item in report.items] == ["bravo", "Charlie", "Alpha"]


def test_report_ordering_is_case_insensitive_and_stable_on_ties():
    a = make_recipe("apple", recipe_servings=0)
    b = make_recipe("Banana", recipe_servings=0)
    same1 = make_recipe("Same", slug="same-1", recipe_servings=0)
    same2 = make_recipe("Same", slug="same-2", recipe_servings=0)

    report = build_report([same2, b, same1, a])

    assert [item.slug for item in report.items] == ["apple", "banana", "same-1", "same-2"]


def test_filter_by_code_keeps_the_full_summary():
    no_yield = make_recipe("Yieldless", recipe_servings=0)
    no_steps = make_recipe("Stepless", step_texts=[])

    report = build_report([no_yield, no_steps], codes=[RecipeQualityCode.MISSING_YIELD])

    assert [item.name for item in report.items] == ["Yieldless"]
    assert report.total == 1
    assert report.summary[RecipeQualityCode.MISSING_YIELD] == 1
    assert report.summary[RecipeQualityCode.NO_INSTRUCTIONS] == 1


def test_filter_with_several_codes_matches_any():
    no_yield = make_recipe("Yieldless", recipe_servings=0)
    no_steps = make_recipe("Stepless", step_texts=[])
    no_ingredients = make_recipe("Ingredientless", ingredients=[])

    report = build_report(
        [no_yield, no_steps, no_ingredients],
        codes=[RecipeQualityCode.MISSING_YIELD, RecipeQualityCode.NO_INSTRUCTIONS],
    )

    assert {item.name for item in report.items} == {"Yieldless", "Stepless"}


def test_pagination():
    recipes = [make_recipe(f"Recipe {i:02d}", recipe_servings=0) for i in range(25)]

    page3 = build_report(recipes, page=3, per_page=10)
    assert len(page3.items) == 5
    assert page3.total == 25
    assert (page3.page, page3.per_page) == (3, 10)

    page1 = build_report(recipes, page=1, per_page=10)
    assert [item.name for item in page1.items] == [f"Recipe {i:02d}" for i in range(10)]


def test_page_beyond_the_end_is_empty_but_reports_total():
    report = build_report([make_recipe("A", recipe_servings=0)], page=5, per_page=10)
    assert report.items == []
    assert report.total == 1


def test_summary_counts_recipes_not_issues():
    # two unparsed lines in one recipe still count once
    recipe = make_recipe(ingredients=[IngredientFacts(note="a"), IngredientFacts(note="b")])
    assert build_report([recipe]).summary[RecipeQualityCode.UNPARSED_INGREDIENTS] == 1


def test_assessing_does_not_modify_the_recipe():
    recipe = make_recipe(ingredients=[], recipe_servings=0)
    before = replace(recipe)

    build_report([recipe])

    assert recipe == before
