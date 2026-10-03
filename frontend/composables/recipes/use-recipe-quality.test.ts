import { describe, expect, test, vi } from "vitest";
import {
  RECIPE_QUALITY_CODES,
  recipeQualityMessageKey,
  recipeQualitySeverity,
  toggleRecipeQualityCode,
  useRecipeQuality,
} from "./use-recipe-quality";
import type { RecipeQualityFetcher } from "./use-recipe-quality";
import type { RecipeQualityCode, RecipeQualityReport } from "~/lib/api/types/recipe";

function makeReport(overrides: Partial<RecipeQualityReport> = {}): RecipeQualityReport {
  const summary = Object.fromEntries(RECIPE_QUALITY_CODES.map(code => [code, 0]));
  return { items: [], total: 0, page: 1, perPage: 20, summary, ...overrides };
}

function ok(report: RecipeQualityReport) {
  return { response: null, data: report, error: null };
}

describe("recipe quality helpers", () => {
  test("errors are the codes that make a recipe unusable", () => {
    expect(recipeQualitySeverity("no-ingredients")).toBe("error");
    expect(recipeQualitySeverity("no-instructions")).toBe("error");
    expect(recipeQualitySeverity("missing-yield")).toBe("warning");
    expect(recipeQualitySeverity("unparsed-ingredients")).toBe("warning");
  });

  test("message keys follow the locale naming", () => {
    expect(recipeQualityMessageKey("thin-instructions")).toBe("recipe-quality.issue-thin-instructions");
  });

  test("every code has a stable chip position", () => {
    expect(new Set(RECIPE_QUALITY_CODES).size).toBe(RECIPE_QUALITY_CODES.length);
  });

  test("toggle adds then removes a code without mutating the input", () => {
    const start: RecipeQualityCode[] = ["missing-times"];

    const added = toggleRecipeQualityCode(start, "missing-yield");
    expect(added).toEqual(["missing-times", "missing-yield"]);
    expect(start).toEqual(["missing-times"]);

    expect(toggleRecipeQualityCode(added, "missing-times")).toEqual(["missing-yield"]);
  });
});

describe("useRecipeQuality", () => {
  test("load stores the report and sends no code filter by default", async () => {
    const fetchReport = vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport({ total: 3 })));
    const quality = useRecipeQuality(fetchReport, 20);

    await quality.load();

    expect(fetchReport).toHaveBeenCalledWith({ code: undefined, page: 1, perPage: 20 });
    expect(quality.report.value?.total).toBe(3);
    expect(quality.error.value).toBe(false);
    expect(quality.loading.value).toBe(false);
  });

  test("chips always list every code in order, with counts from the summary", async () => {
    const summary = Object.fromEntries(RECIPE_QUALITY_CODES.map(code => [code, 0]));
    summary["missing-times"] = 4;
    const quality = useRecipeQuality(vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport({ summary, total: 4 }))));

    expect(quality.chips.value.map(chip => chip.code)).toEqual([...RECIPE_QUALITY_CODES]);
    expect(quality.chips.value.every(chip => chip.count === 0)).toBe(true);

    await quality.load();

    expect(quality.chips.value.find(chip => chip.code === "missing-times")?.count).toBe(4);
    expect(quality.chips.value.find(chip => chip.code === "no-ingredients")?.count).toBe(0);
  });

  test("toggling a chip reloads from page 1 with that code", async () => {
    const fetchReport = vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport()));
    const quality = useRecipeQuality(fetchReport, 20);
    await quality.setPage(3);

    await quality.toggleCode("missing-yield");

    expect(fetchReport).toHaveBeenLastCalledWith({ code: ["missing-yield"], page: 1, perPage: 20 });
    expect(quality.chips.value.find(chip => chip.code === "missing-yield")?.selected).toBe(true);

    await quality.toggleCode("missing-yield");

    expect(fetchReport).toHaveBeenLastCalledWith({ code: undefined, page: 1, perPage: 20 });
  });

  test("clearCodes removes every filter", async () => {
    const fetchReport = vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport()));
    const quality = useRecipeQuality(fetchReport);
    await quality.toggleCode("missing-times");
    await quality.toggleCode("missing-yield");

    await quality.clearCodes();

    expect(quality.selectedCodes.value).toEqual([]);
    expect(fetchReport).toHaveBeenLastCalledWith({ code: undefined, page: 1, perPage: 20 });
  });

  test("a failed request sets the error state and keeps the previous report", async () => {
    const fetchReport = vi
      .fn<RecipeQualityFetcher>()
      .mockResolvedValueOnce(ok(makeReport({ total: 2 })))
      .mockResolvedValueOnce({ response: null, data: null, error: new Error("boom") });
    const quality = useRecipeQuality(fetchReport);

    await quality.load();
    await quality.load();

    expect(quality.error.value).toBe(true);
    expect(quality.loading.value).toBe(false);
    expect(quality.report.value?.total).toBe(2);
  });

  test("a later success clears the error state", async () => {
    const fetchReport = vi
      .fn<RecipeQualityFetcher>()
      .mockResolvedValueOnce({ response: null, data: null, error: new Error("boom") })
      .mockResolvedValueOnce(ok(makeReport()));
    const quality = useRecipeQuality(fetchReport);

    await quality.load();
    expect(quality.error.value).toBe(true);

    await quality.load();
    expect(quality.error.value).toBe(false);
  });

  test("a slow older response never overwrites a newer one", async () => {
    let releaseSlow: (value: ReturnType<typeof ok>) => void = () => {};
    const slow = new Promise<ReturnType<typeof ok>>((resolve) => {
      releaseSlow = resolve;
    });
    const fetchReport = vi
      .fn<RecipeQualityFetcher>()
      .mockReturnValueOnce(slow)
      .mockResolvedValueOnce(ok(makeReport({ total: 99 })));
    const quality = useRecipeQuality(fetchReport);

    const first = quality.load();
    await quality.load();
    releaseSlow(ok(makeReport({ total: 1 })));
    await first;

    expect(quality.report.value?.total).toBe(99);
  });

  test("totalPages rounds up and is never below 1", async () => {
    const quality = useRecipeQuality(vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport({ total: 41 }))), 20);
    expect(quality.totalPages.value).toBe(1);

    await quality.load();

    expect(quality.totalPages.value).toBe(3);
  });

  test("allClear is only true when the whole summary is zero", async () => {
    const summary = Object.fromEntries(RECIPE_QUALITY_CODES.map(code => [code, 0]));
    const clean = useRecipeQuality(vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport())));
    expect(clean.allClear.value).toBe(false);
    await clean.load();
    expect(clean.allClear.value).toBe(true);

    // A filter that matches nothing is not "all clear": other issues still exist.
    summary["missing-times"] = 1;
    const filtered = useRecipeQuality(vi.fn<RecipeQualityFetcher>().mockResolvedValue(ok(makeReport({ summary, total: 0 }))));
    await filtered.load();
    expect(filtered.allClear.value).toBe(false);
  });
});
