from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from mealie.schema.recipe.recipe import Recipe
from mealie.schema.recipe.recipe_ingredient import RecipeIngredient, SaveIngredientFood
from mealie.schema.recipe.recipe_settings import RecipeSettings
from mealie.schema.recipe.recipe_step import RecipeStep
from tests.utils import api_routes
from tests.utils.factories import random_string
from tests.utils.fixture_schemas import TestUser

LONG_STEP = "Combine everything in a large bowl, mix well, then bake until golden brown."


def _delete_all_recipes(user: TestUser) -> None:
    for recipe in user.repos.recipes.get_all():
        user.repos.recipes.delete(recipe.slug, "slug")


@pytest.fixture(autouse=True)
def clean_libraries(request: pytest.FixtureRequest):
    """
    The user fixtures are module-scoped, so recipes from one test would leak into the next report.
    Start every test with empty libraries for the users it actually requests.
    """
    for name in ("unique_user", "h2_user", "g2_user"):
        if name in request.fixturenames:
            _delete_all_recipes(request.getfixturevalue(name))
    yield


def create_complete_recipe(user: TestUser, **overrides) -> Recipe:
    """A recipe that passes every quality rule unless a field is overridden."""
    food = user.repos.ingredient_foods.create(
        SaveIngredientFood(id=uuid4(), name=random_string(), group_id=user.group_id)
    )
    data = {
        "user_id": user.user_id,
        "group_id": user.group_id,
        "name": random_string(),
        "recipe_ingredient": [RecipeIngredient(food_id=food.id, food=food, note="")],
        "recipe_instructions": [RecipeStep(text=LONG_STEP)],
        "total_time": "30 minutes",
        "recipe_servings": 4,
        "settings": RecipeSettings(),
    }
    data.update(overrides)
    return user.repos.recipes.create(Recipe(**data))


def get_report(api_client: TestClient, user: TestUser, **params):
    response = api_client.get(api_routes.recipes_quality_report, params=params, headers=user.token)
    assert response.status_code == 200, response.text
    return response.json()


def test_requires_authentication(api_client: TestClient):
    response = api_client.get(api_routes.recipes_quality_report)
    assert response.status_code == 401


def test_route_is_not_shadowed_by_the_slug_route(api_client: TestClient, unique_user: TestUser):
    body = get_report(api_client, unique_user)
    assert set(body) >= {"items", "total", "page", "perPage", "summary"}


def test_empty_library_returns_an_empty_report(api_client: TestClient, unique_user: TestUser):
    body = get_report(api_client, unique_user)

    assert body["items"] == []
    assert body["total"] == 0
    assert all(count == 0 for count in body["summary"].values())


def test_complete_recipe_is_not_listed(api_client: TestClient, unique_user: TestUser):
    create_complete_recipe(unique_user)

    body = get_report(api_client, unique_user)

    assert body["items"] == []
    assert body["total"] == 0


def test_flagged_recipe_is_listed_with_its_issues(api_client: TestClient, unique_user: TestUser):
    bare = create_complete_recipe(unique_user, recipe_ingredient=[], recipe_instructions=[], total_time=None)
    create_complete_recipe(unique_user)

    body = get_report(api_client, unique_user)

    assert [item["slug"] for item in body["items"]] == [bare.slug]
    item = body["items"][0]
    assert item["recipeId"] == str(bare.id)
    assert item["name"] == bare.name
    severity = {issue["code"]: issue["severity"] for issue in item["issues"]}
    assert severity == {
        "no-ingredients": "error",
        "no-instructions": "error",
        "missing-times": "warning",
    }
    assert body["summary"]["no-ingredients"] == 1
    assert body["summary"]["missing-yield"] == 0


def test_filter_by_code_keeps_the_full_summary(api_client: TestClient, unique_user: TestUser):
    no_yield = create_complete_recipe(unique_user, recipe_servings=0)
    create_complete_recipe(unique_user, recipe_instructions=[])

    body = get_report(api_client, unique_user, code="missing-yield")

    assert [item["slug"] for item in body["items"]] == [no_yield.slug]
    assert body["total"] == 1
    assert body["summary"]["missing-yield"] == 1
    assert body["summary"]["no-instructions"] == 1


def test_filter_with_several_codes_matches_any(api_client: TestClient, unique_user: TestUser):
    no_yield = create_complete_recipe(unique_user, recipe_servings=0)
    no_steps = create_complete_recipe(unique_user, recipe_instructions=[])
    create_complete_recipe(unique_user, recipe_ingredient=[])

    body = get_report(api_client, unique_user, code=["missing-yield", "no-instructions"])

    assert {item["slug"] for item in body["items"]} == {no_yield.slug, no_steps.slug}


def test_unknown_code_is_rejected(api_client: TestClient, unique_user: TestUser):
    response = api_client.get(api_routes.recipes_quality_report, params={"code": "nonsense"}, headers=unique_user.token)
    assert response.status_code == 422


def test_pagination(api_client: TestClient, unique_user: TestUser):
    for _ in range(5):
        create_complete_recipe(unique_user, recipe_servings=0)

    page1 = get_report(api_client, unique_user, page=1, perPage=2)
    page3 = get_report(api_client, unique_user, page=3, perPage=2)

    assert page1["total"] == 5
    assert len(page1["items"]) == 2
    assert (page1["page"], page1["perPage"]) == (1, 2)
    assert len(page3["items"]) == 1


@pytest.mark.parametrize("params", [{"page": 0}, {"perPage": 0}, {"perPage": 201}])
def test_invalid_paging_is_rejected(api_client: TestClient, unique_user: TestUser, params: dict):
    response = api_client.get(api_routes.recipes_quality_report, params=params, headers=unique_user.token)
    assert response.status_code == 422


def test_report_is_read_only(api_client: TestClient, unique_user: TestUser):
    recipe = create_complete_recipe(unique_user, recipe_instructions=[])
    before = unique_user.repos.recipes.get_one(recipe.slug)
    assert before

    first = get_report(api_client, unique_user)
    second = get_report(api_client, unique_user)

    assert first == second
    after = unique_user.repos.recipes.get_one(recipe.slug)
    assert after
    assert after.updated_at == before.updated_at
    assert after.recipe_instructions == before.recipe_instructions


def test_other_household_in_the_same_group_is_not_included(
    api_client: TestClient, unique_user: TestUser, h2_user: TestUser
):
    assert unique_user.group_id == h2_user.group_id
    mine = create_complete_recipe(unique_user, recipe_instructions=[])
    theirs = create_complete_recipe(h2_user, recipe_instructions=[])

    mine_slugs = {item["slug"] for item in get_report(api_client, unique_user)["items"]}
    theirs_slugs = {item["slug"] for item in get_report(api_client, h2_user)["items"]}

    assert mine_slugs == {mine.slug}
    assert theirs_slugs == {theirs.slug}


def test_other_group_is_not_included(api_client: TestClient, unique_user: TestUser, g2_user: TestUser):
    assert unique_user.group_id != g2_user.group_id
    mine = create_complete_recipe(unique_user, recipe_instructions=[])
    theirs = create_complete_recipe(g2_user, recipe_instructions=[])

    mine_body = get_report(api_client, unique_user)
    theirs_body = get_report(api_client, g2_user)

    assert [item["slug"] for item in mine_body["items"]] == [mine.slug]
    assert [item["slug"] for item in theirs_body["items"]] == [theirs.slug]
    assert mine_body["summary"]["no-instructions"] == 1
    assert theirs_body["summary"]["no-instructions"] == 1
