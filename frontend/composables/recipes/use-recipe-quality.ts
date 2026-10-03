import { computed, ref } from "vue";
import type { RecipeQualityCode, RecipeQualityReport, RecipeQualitySeverity } from "~/lib/api/types/recipe";
import type { RequestResponse } from "~/lib/api/types/non-generated";

export interface RecipeQualityQuery {
  code?: RecipeQualityCode[];
  page: number;
  perPage: number;
}

export type RecipeQualityFetcher = (query: RecipeQualityQuery) => Promise<RequestResponse<RecipeQualityReport>>;

/** Display order of the issue chips: errors first, then warnings. */
export const RECIPE_QUALITY_CODES: readonly RecipeQualityCode[] = [
  "no-ingredients",
  "no-instructions",
  "thin-instructions",
  "missing-times",
  "missing-yield",
  "unparsed-ingredients",
];

const ERROR_CODES: ReadonlySet<RecipeQualityCode> = new Set<RecipeQualityCode>(["no-ingredients", "no-instructions"]);

export function recipeQualitySeverity(code: RecipeQualityCode): RecipeQualitySeverity {
  return ERROR_CODES.has(code) ? "error" : "warning";
}

/** i18n key for the short label of an issue code, e.g. `recipe-quality.issue-no-ingredients`. */
export function recipeQualityMessageKey(code: RecipeQualityCode): string {
  return `recipe-quality.issue-${code}`;
}

/** Returns a new selection with `code` added, or removed when it is already selected. */
export function toggleRecipeQualityCode(selected: readonly RecipeQualityCode[], code: RecipeQualityCode): RecipeQualityCode[] {
  return selected.includes(code) ? selected.filter(c => c !== code) : [...selected, code];
}

export function useRecipeQuality(fetchReport: RecipeQualityFetcher, perPage = 20) {
  const report = ref<RecipeQualityReport | null>(null);
  const loading = ref(false);
  const error = ref(false);
  const selectedCodes = ref<RecipeQualityCode[]>([]);
  const page = ref(1);

  // Guards against an older, slower response overwriting a newer one when chips are clicked quickly.
  let latestRequest = 0;

  async function load() {
    const requestId = ++latestRequest;
    loading.value = true;
    error.value = false;

    const { data, error: requestError } = await fetchReport({
      code: selectedCodes.value.length ? [...selectedCodes.value] : undefined,
      page: page.value,
      perPage,
    });

    if (requestId !== latestRequest) {
      return;
    }

    if (requestError || !data) {
      error.value = true;
    }
    else {
      report.value = data;
    }
    loading.value = false;
  }

  async function toggleCode(code: RecipeQualityCode) {
    selectedCodes.value = toggleRecipeQualityCode(selectedCodes.value, code);
    page.value = 1;
    await load();
  }

  async function clearCodes() {
    selectedCodes.value = [];
    page.value = 1;
    await load();
  }

  async function setPage(newPage: number) {
    page.value = newPage;
    await load();
  }

  /** One chip per code, always in the same order, with the count across all flagged recipes. */
  const chips = computed(() =>
    RECIPE_QUALITY_CODES.map(code => ({
      code,
      count: report.value?.summary?.[code] ?? 0,
      severity: recipeQualitySeverity(code),
      selected: selectedCodes.value.includes(code),
    })),
  );

  const totalPages = computed(() => {
    const total = report.value?.total ?? 0;
    return Math.max(1, Math.ceil(total / perPage));
  });

  /** True when nothing is flagged at all (not merely nothing matching the current filter). */
  const allClear = computed(() => {
    if (!report.value) {
      return false;
    }
    return Object.values(report.value.summary).every(count => count === 0);
  });

  return { report, loading, error, selectedCodes, page, chips, totalPages, allClear, load, toggleCode, clearCodes, setPage };
}
