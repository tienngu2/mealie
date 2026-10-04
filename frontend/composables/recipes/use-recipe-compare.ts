import { computed, ref } from "vue";
import { useFraction } from "./use-fraction";
import type { Recipe, RecipeIngredient } from "~/lib/api/types/recipe";
import type { RequestResponse } from "~/lib/api/types/non-generated";

const { frac } = useFraction();

/** The parts of a recipe that are compared. */
export type ComparableRecipe = Pick<
  Recipe,
  "name" | "slug" | "prepTime" | "performTime" | "totalTime" | "recipeServings" | "recipeYieldQuantity" | "recipeYield" | "recipeIngredient"
>;

export type DetailKey = "prepTime" | "performTime" | "totalTime" | "servings" | "yield";

/** Order of the detail rows. `performTime` is the field the app labels "Cook Time"; the legacy `cookTime` is never shown. */
export const DETAIL_KEYS: readonly DetailKey[] = ["prepTime", "performTime", "totalTime", "servings", "yield"];

const DETAIL_LABEL_KEYS: Record<DetailKey, string> = {
  prepTime: "recipe.prep-time",
  performTime: "recipe.perform-time",
  totalTime: "recipe.total-time",
  servings: "recipe.servings",
  yield: "recipe.yield",
};

/** i18n key of the existing label for a detail row. */
export function detailLabelKey(key: DetailKey): string {
  return DETAIL_LABEL_KEYS[key];
}

export interface DetailRow {
  key: DetailKey;
  /** Display value, or null when the recipe has none (shown as "Not set"). */
  a: string | null;
  b: string | null;
  different: boolean;
}

export interface SharedIngredient {
  key: string;
  label: string;
  a: string;
  b: string;
  /** True when the quantity or the unit differs; units are never converted. */
  different: boolean;
}

export interface SingleIngredient {
  key: string;
  label: string;
  amount: string;
}

export interface RecipeComparison {
  details: DetailRow[];
  shared: SharedIngredient[];
  onlyA: SingleIngredient[];
  onlyB: SingleIngredient[];
  differentDetails: number;
  differentAmounts: number;
}

function normalize(text: string): string {
  return text.trim().replace(/\s+/g, " ").toLowerCase();
}

function textOrNull(value: string | null | undefined): string | null {
  const text = (value ?? "").trim();
  return text || null;
}

const DETAIL_READERS: Record<DetailKey, (recipe: ComparableRecipe) => string | null> = {
  prepTime: recipe => textOrNull(recipe.prepTime),
  performTime: recipe => textOrNull(recipe.performTime),
  totalTime: recipe => textOrNull(recipe.totalTime),
  servings: recipe => (recipe.recipeServings ? String(Number(recipe.recipeServings)) : null),
  yield: (recipe) => {
    const quantity = recipe.recipeYieldQuantity ? String(Number(recipe.recipeYieldQuantity)) : "";
    return textOrNull(`${quantity} ${recipe.recipeYield ?? ""}`);
  },
};

function formatQuantity(quantity: number): string {
  const fraction = frac(quantity, 10, true);
  const parts: string[] = [];
  if (fraction[0] !== undefined && fraction[0] > 0) {
    parts.push(String(fraction[0]));
  }
  if (fraction[1] > 0) {
    parts.push(`${fraction[1]}/${fraction[2]}`);
  }
  return parts.length ? parts.join(" ") : String(quantity);
}

function unitText(unit: RecipeIngredient["unit"]): string {
  if (!unit) {
    return "";
  }
  const text = unit.useAbbreviation && unit.abbreviation ? unit.abbreviation : unit.name;
  return (text ?? "").trim();
}

function unitKey(unit: RecipeIngredient["unit"]): string {
  return normalize(unit?.name || unit?.abbreviation || "");
}

interface Line {
  key: string;
  label: string;
  amount: string;
  amountKey: string;
}

/** Turns one ingredient line into a comparable line, or null for section titles and blank lines. */
function toLine(ingredient: RecipeIngredient): Line | null {
  const food = textOrNull(ingredient.food?.name);
  const linked = textOrNull(ingredient.referencedRecipe?.name);
  const note = textOrNull(ingredient.note);
  const label = food ?? linked ?? note;
  if (!label) {
    return null;
  }

  const quantity = ingredient.quantity ? Number(ingredient.quantity) : 0;
  // Like the recipe page, a unit is only shown together with a quantity.
  const base = quantity ? [formatQuantity(quantity), unitText(ingredient.unit)].filter(Boolean).join(" ") : "";
  const extra = label === note ? "" : (note ?? "");

  return {
    key: normalize(label),
    label,
    amount: [base, extra].filter(Boolean).join(", "),
    amountKey: quantity ? `${quantity}|${unitKey(ingredient.unit)}` : "",
  };
}

interface Group {
  label: string;
  amounts: string[];
  amountKeys: string[];
}

function groupLines(ingredients: RecipeIngredient[] | null | undefined): Map<string, Group> {
  const groups = new Map<string, Group>();

  for (const ingredient of ingredients ?? []) {
    const line = toLine(ingredient);
    if (!line) {
      continue;
    }

    const group = groups.get(line.key) ?? { label: line.label, amounts: [], amountKeys: [] };
    if (line.amount) {
      group.amounts.push(line.amount);
    }
    group.amountKeys.push(line.amountKey);
    groups.set(line.key, group);
  }

  return groups;
}

function signature(group: Group): string {
  return [...group.amountKeys].sort().join("&");
}

/** Compares two recipes: the detail rows, and their ingredients matched by food name (or text). */
export function compareRecipes(a: ComparableRecipe, b: ComparableRecipe): RecipeComparison {
  const details: DetailRow[] = DETAIL_KEYS.map((key) => {
    const valueA = DETAIL_READERS[key](a);
    const valueB = DETAIL_READERS[key](b);
    return { key, a: valueA, b: valueB, different: normalize(valueA ?? "") !== normalize(valueB ?? "") };
  });

  const groupsA = groupLines(a.recipeIngredient);
  const groupsB = groupLines(b.recipeIngredient);
  const shared: SharedIngredient[] = [];
  const onlyA: SingleIngredient[] = [];
  const onlyB: SingleIngredient[] = [];

  for (const [key, groupA] of groupsA) {
    const groupB = groupsB.get(key);
    if (groupB) {
      shared.push({
        key,
        label: groupA.label,
        a: groupA.amounts.join(" + "),
        b: groupB.amounts.join(" + "),
        different: signature(groupA) !== signature(groupB),
      });
    }
    else {
      onlyA.push({ key, label: groupA.label, amount: groupA.amounts.join(" + ") });
    }
  }

  for (const [key, groupB] of groupsB) {
    if (!groupsA.has(key)) {
      onlyB.push({ key, label: groupB.label, amount: groupB.amounts.join(" + ") });
    }
  }

  return {
    details,
    shared,
    onlyA,
    onlyB,
    differentDetails: details.filter(row => row.different).length,
    differentAmounts: shared.filter(item => item.different).length,
  };
}

export type RecipeFetcher = (slug: string) => Promise<RequestResponse<Recipe>>;

function matchesSlug(recipe: Recipe | null, slug: string | null): recipe is Recipe {
  return !!recipe && !!slug && (recipe.slug === slug || recipe.id === slug);
}

/** Holds the two selected recipes (by slug or id), loads them, and exposes their comparison. */
export function useRecipeCompare(fetchRecipe: RecipeFetcher) {
  const slugA = ref<string | null>(null);
  const slugB = ref<string | null>(null);
  const recipeA = ref<Recipe | null>(null);
  const recipeB = ref<Recipe | null>(null);
  const loading = ref(false);
  const error = ref(false);

  // Guards against an older, slower response overwriting a newer one when the selection changes quickly.
  let latestRequest = 0;

  const sameRecipe = computed(() => !!slugA.value && slugA.value === slugB.value);

  /** The loaded recipe for each side, or null while it does not match the current selection. */
  const selectedA = computed(() => (matchesSlug(recipeA.value, slugA.value) ? recipeA.value : null));
  const selectedB = computed(() => (matchesSlug(recipeB.value, slugB.value) ? recipeB.value : null));

  const comparison = computed(() => {
    if (sameRecipe.value || !selectedA.value || !selectedB.value) {
      return null;
    }
    return compareRecipes(selectedA.value, selectedB.value);
  });

  function setSlugs(a: string | null, b: string | null) {
    slugA.value = a;
    slugB.value = b;
  }

  async function resolve(slug: string | null, current: Recipe | null) {
    if (!slug) {
      return { recipe: null, failed: false };
    }
    if (matchesSlug(current, slug)) {
      return { recipe: current, failed: false };
    }

    const { data, error: requestError } = await fetchRecipe(slug);
    return { recipe: data, failed: !!requestError || !data };
  }

  async function load() {
    const requestId = ++latestRequest;
    loading.value = true;
    error.value = false;

    const [a, b] = await Promise.all([resolve(slugA.value, recipeA.value), resolve(slugB.value, recipeB.value)]);

    if (requestId !== latestRequest) {
      return;
    }

    loading.value = false;
    if (a.failed || b.failed) {
      error.value = true;
      return;
    }

    recipeA.value = a.recipe;
    recipeB.value = b.recipe;
  }

  return { slugA, slugB, selectedA, selectedB, loading, error, sameRecipe, comparison, setSlugs, load };
}
