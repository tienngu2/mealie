import { describe, expect, test, vi } from "vitest";
import { compareRecipes, detailLabelKey, useRecipeCompare } from "./use-recipe-compare";
import type { ComparableRecipe, DetailKey, RecipeFetcher } from "./use-recipe-compare";
import type { Recipe, RecipeIngredient } from "~/lib/api/types/recipe";

function line(food: string | null, quantity: number | null = null, unit: string | null = null, note: string | null = null): RecipeIngredient {
  return { quantity, unit: unit ? { name: unit } : null, food: food ? { name: food } : null, note };
}

function recipe(overrides: Partial<ComparableRecipe> = {}): ComparableRecipe {
  return {
    name: "Recipe",
    slug: "recipe",
    prepTime: null,
    performTime: null,
    totalTime: null,
    recipeServings: 0,
    recipeYieldQuantity: 0,
    recipeYield: null,
    recipeIngredient: [],
    ...overrides,
  };
}

function detail(a: Partial<ComparableRecipe>, b: Partial<ComparableRecipe>, key: DetailKey) {
  const row = compareRecipes(recipe(a), recipe(b)).details.find(r => r.key === key);
  if (!row) {
    throw new Error(`missing row ${key}`);
  }
  return row;
}

describe("compareRecipes: details", () => {
  test("lists the rows in a fixed order, with the existing labels", () => {
    const keys = compareRecipes(recipe(), recipe()).details.map(row => row.key);

    expect(keys).toEqual(["prepTime", "performTime", "totalTime", "servings", "yield"]);
    expect(detailLabelKey("performTime")).toBe("recipe.perform-time");
  });

  test("marks a differing value", () => {
    const row = detail({ totalTime: "30 minutes" }, { totalTime: "45 minutes" }, "totalTime");

    expect(row).toMatchObject({ a: "30 minutes", b: "45 minutes", different: true });
  });

  test("ignores letter case and surrounding whitespace", () => {
    expect(detail({ totalTime: "30 Minutes" }, { totalTime: " 30 minutes " }, "totalTime").different).toBe(false);
  });

  test("shows a missing value as null and marks the row", () => {
    const row = detail({ performTime: "20 minutes" }, {}, "performTime");

    expect(row).toMatchObject({ a: "20 minutes", b: null, different: true });
  });

  test("two unset values are equal, blank text counts as unset", () => {
    const row = detail({ prepTime: null }, { prepTime: "   " }, "prepTime");

    expect(row).toMatchObject({ a: null, b: null, different: false });
  });

  test("servings compare as numbers and zero means not set", () => {
    expect(detail({ recipeServings: 4 }, { recipeServings: 4 }, "servings").different).toBe(false);
    expect(detail({ recipeServings: 4 }, { recipeServings: 6 }, "servings")).toMatchObject({ a: "4", b: "6", different: true });
    expect(detail({ recipeServings: 0 }, {}, "servings")).toMatchObject({ a: null, b: null, different: false });
  });

  test("yield combines the quantity and the text", () => {
    expect(detail({ recipeYieldQuantity: 12, recipeYield: "cookies" }, {}, "yield").a).toBe("12 cookies");
    expect(detail({ recipeYieldQuantity: 12, recipeYield: "cookies" }, { recipeYieldQuantity: 12, recipeYield: "Cookies" }, "yield").different).toBe(false);
    expect(detail({ recipeYieldQuantity: 0, recipeYield: "1 loaf" }, {}, "yield").a).toBe("1 loaf");
  });

  test("counts the rows that differ", () => {
    const result = compareRecipes(recipe({ prepTime: "5 min", totalTime: "1 h" }), recipe({ prepTime: "10 min", totalTime: "1 h" }));

    expect(result.differentDetails).toBe(1);
  });
});

describe("compareRecipes: ingredients", () => {
  test("a shared ingredient with the same amount is not marked", () => {
    const result = compareRecipes(recipe({ recipeIngredient: [line("flour", 2, "cup")] }), recipe({ recipeIngredient: [line("flour", 2, "cup")] }));

    expect(result.shared).toEqual([{ key: "flour", label: "flour", a: "2 cup", b: "2 cup", different: false }]);
    expect(result.onlyA).toEqual([]);
    expect(result.onlyB).toEqual([]);
  });

  test("different quantities are marked", () => {
    const result = compareRecipes(recipe({ recipeIngredient: [line("flour", 2, "cup")] }), recipe({ recipeIngredient: [line("flour", 3, "cup")] }));

    expect(result.shared[0]).toMatchObject({ a: "2 cup", b: "3 cup", different: true });
    expect(result.differentAmounts).toBe(1);
  });

  test("units are never converted", () => {
    const result = compareRecipes(recipe({ recipeIngredient: [line("milk", 1, "cup")] }), recipe({ recipeIngredient: [line("milk", 240, "ml")] }));

    expect(result.shared[0]).toMatchObject({ a: "1 cup", b: "240 ml", different: true });
  });

  test("an ingredient in only one recipe is listed on its own side", () => {
    const result = compareRecipes(recipe({ recipeIngredient: [line("eggs", 2)] }), recipe({ recipeIngredient: [line("sugar", 1, "cup")] }));

    expect(result.shared).toEqual([]);
    expect(result.onlyA).toEqual([{ key: "eggs", label: "eggs", amount: "2" }]);
    expect(result.onlyB).toEqual([{ key: "sugar", label: "sugar", amount: "1 cup" }]);
  });

  test("names match regardless of letter case and spacing", () => {
    const result = compareRecipes(recipe({ recipeIngredient: [line("Butter", 1, "cup")] }), recipe({ recipeIngredient: [line("  butter ", 1, "cup")] }));

    expect(result.shared).toHaveLength(1);
    expect(result.shared[0].label).toBe("Butter");
    expect(result.shared[0].different).toBe(false);
  });

  test("section titles and blank lines are ignored", () => {
    const lines: RecipeIngredient[] = [{ title: "For the sauce" }, {}, { note: "   " }, line("salt", 1, "tsp")];
    const result = compareRecipes(recipe({ recipeIngredient: lines }), recipe());

    expect(result.onlyA.map(item => item.key)).toEqual(["salt"]);
    expect(result.shared).toEqual([]);
    expect(result.onlyB).toEqual([]);
  });

  test("repeated ingredients are combined into one entry with all amounts", () => {
    const result = compareRecipes(
      recipe({ recipeIngredient: [line("salt", 1, "tsp"), line("pepper", 1), line("salt", 2, "tsp")] }),
      recipe({ recipeIngredient: [line("salt", 3, "tsp")] }),
    );

    expect(result.shared).toHaveLength(1);
    expect(result.shared[0]).toMatchObject({ key: "salt", a: "1 tsp + 2 tsp", b: "3 tsp", different: true });
  });

  test("lines without a food match by their text", () => {
    const result = compareRecipes(
      recipe({ recipeIngredient: [line(null, null, null, "2 cups flour, sifted")] }),
      recipe({ recipeIngredient: [line(null, null, null, "2 Cups Flour, Sifted")] }),
    );

    expect(result.shared).toHaveLength(1);
    expect(result.shared[0]).toMatchObject({ a: "", b: "", different: false });
  });

  test("a linked recipe is matched by its name", () => {
    const linked = { referencedRecipe: { name: "Pizza dough" } as Recipe };
    const result = compareRecipes(recipe({ recipeIngredient: [linked] }), recipe({ recipeIngredient: [line("pizza DOUGH")] }));

    expect(result.shared).toHaveLength(1);
  });

  test("quantities are shown as fractions, and a unit needs a quantity", () => {
    const result = compareRecipes(
      recipe({ recipeIngredient: [line("milk", 0.5, "cup"), line("sugar", 1.5, "cup"), line("flour", 2, "cup"), line("salt", null, "pinch")] }),
      recipe(),
    );

    expect(result.onlyA.map(item => item.amount)).toEqual(["1/2 cup", "1 1/2 cup", "2 cup", ""]);
  });

  test("a note is shown with the amount but does not make it different", () => {
    const result = compareRecipes(
      recipe({ recipeIngredient: [line("onion", 1, null, "diced")] }),
      recipe({ recipeIngredient: [line("onion", 1)] }),
    );

    expect(result.shared[0]).toMatchObject({ a: "1, diced", b: "1", different: false });
  });

  test("recipes without an ingredient list do not break the comparison", () => {
    const result = compareRecipes(recipe({ recipeIngredient: undefined }), recipe({ recipeIngredient: null }));

    expect(result.shared).toEqual([]);
    expect(result.onlyA).toEqual([]);
    expect(result.onlyB).toEqual([]);
  });
});

function fakeRecipe(slug: string, overrides: Partial<Recipe> = {}): Recipe {
  return { id: `${slug}-id`, slug, name: slug.toUpperCase(), ...overrides } as Recipe;
}

function ok(value: Recipe) {
  return { response: null, data: value, error: null };
}

describe("useRecipeCompare", () => {
  test("loads both recipes and compares them", async () => {
    const fetchRecipe = vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug)));
    const compare = useRecipeCompare(fetchRecipe);

    compare.setSlugs("a", "b");
    await compare.load();

    expect(fetchRecipe).toHaveBeenCalledTimes(2);
    expect(compare.selectedA.value?.slug).toBe("a");
    expect(compare.selectedB.value?.slug).toBe("b");
    expect(compare.comparison.value).not.toBeNull();
    expect(compare.loading.value).toBe(false);
    expect(compare.error.value).toBe(false);
  });

  test("never compares a recipe with itself", async () => {
    const compare = useRecipeCompare(vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug))));

    compare.setSlugs("a", "a");
    await compare.load();

    expect(compare.sameRecipe.value).toBe(true);
    expect(compare.comparison.value).toBeNull();
  });

  test("one selected recipe loads without a comparison", async () => {
    const fetchRecipe = vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug)));
    const compare = useRecipeCompare(fetchRecipe);

    compare.setSlugs("a", null);
    await compare.load();

    expect(fetchRecipe).toHaveBeenCalledTimes(1);
    expect(compare.selectedA.value?.slug).toBe("a");
    expect(compare.selectedB.value).toBeNull();
    expect(compare.comparison.value).toBeNull();
    expect(compare.error.value).toBe(false);
  });

  test("accepts a recipe id as well as a slug", async () => {
    const compare = useRecipeCompare(vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug.replace("-id", "")))));

    compare.setSlugs("a-id", "b");
    await compare.load();

    expect(compare.selectedA.value?.slug).toBe("a");
    expect(compare.comparison.value).not.toBeNull();
  });

  test("does not fetch again a recipe whose selection did not change", async () => {
    const fetchRecipe = vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug)));
    const compare = useRecipeCompare(fetchRecipe);
    compare.setSlugs("a", "b");
    await compare.load();

    compare.setSlugs("a", "c");
    await compare.load();

    expect(fetchRecipe.mock.calls.map(([slug]) => slug).sort()).toEqual(["a", "b", "c"]);
    expect(compare.selectedB.value?.slug).toBe("c");
  });

  test("a recipe loaded for another selection is not shown", async () => {
    const compare = useRecipeCompare(vi.fn<RecipeFetcher>(async slug => ok(fakeRecipe(slug))));
    compare.setSlugs("a", "b");
    await compare.load();

    compare.setSlugs("x", "b");

    expect(compare.selectedA.value).toBeNull();
    expect(compare.comparison.value).toBeNull();
  });

  test("a failed load sets the error and hides the comparison, and a retry recovers", async () => {
    let failB = true;
    const fetchRecipe = vi.fn<RecipeFetcher>(async (slug) => {
      if (slug === "b" && failB) {
        return { response: null, data: null, error: new Error("boom") };
      }
      return ok(fakeRecipe(slug));
    });
    const compare = useRecipeCompare(fetchRecipe);
    compare.setSlugs("a", "b");

    await compare.load();

    expect(compare.error.value).toBe(true);
    expect(compare.loading.value).toBe(false);
    expect(compare.comparison.value).toBeNull();

    failB = false;
    await compare.load();

    expect(compare.error.value).toBe(false);
    expect(compare.comparison.value).not.toBeNull();
  });

  test("a slow older response never overwrites a newer one", async () => {
    let releaseSlow: (value: ReturnType<typeof ok>) => void = () => {};
    const slow = new Promise<ReturnType<typeof ok>>((resolve) => {
      releaseSlow = resolve;
    });
    const fetchRecipe = vi.fn<RecipeFetcher>(async (slug) => {
      return slug === "a" ? slow : ok(fakeRecipe(slug));
    });
    const compare = useRecipeCompare(fetchRecipe);

    compare.setSlugs("a", "b");
    const first = compare.load();
    compare.setSlugs("c", "d");
    await compare.load();
    releaseSlow(ok(fakeRecipe("a")));
    await first;

    expect(compare.selectedA.value?.slug).toBe("c");
    expect(compare.selectedB.value?.slug).toBe("d");
    expect(compare.loading.value).toBe(false);
  });
});
