<template>
  <v-container>
    <BasePageTitle divider>
      <template #header>
        <v-img
          width="100"
          max-height="100"
          max-width="100"
          src="/svgs/manage-recipes.svg"
        />
      </template>
      <template #title>
        {{ $t('recipe-compare.compare-recipes') }}
      </template>

      <template #content>
        {{ $t('recipe-compare.description') }}
      </template>
    </BasePageTitle>

    <v-row>
      <v-col
        cols="12"
        md="6"
      >
        <RecipeSelect
          :model-value="selectedA"
          :label="$t('recipe-compare.recipe-a')"
          data-testid="compare-select-a"
          @update:model-value="choose('a', $event)"
        />
      </v-col>
      <v-col
        cols="12"
        md="6"
      >
        <RecipeSelect
          :model-value="selectedB"
          :label="$t('recipe-compare.recipe-b')"
          data-testid="compare-select-b"
          @update:model-value="choose('b', $event)"
        />
      </v-col>
    </v-row>

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="my-4"
      data-testid="compare-error"
    >
      {{ $t('recipe-compare.load-error') }}
      <template #append>
        <v-btn
          variant="text"
          @click="load"
        >
          {{ $t('recipe-compare.retry') }}
        </v-btn>
      </template>
    </v-alert>

    <v-progress-linear
      v-else-if="loading"
      indeterminate
      class="my-4"
    />

    <v-alert
      v-else-if="sameRecipe"
      type="info"
      variant="tonal"
      class="my-4"
      data-testid="compare-same"
    >
      {{ $t('recipe-compare.same-recipe') }}
    </v-alert>

    <v-alert
      v-else-if="!comparison"
      type="info"
      variant="tonal"
      class="my-4"
      data-testid="compare-hint"
    >
      {{ $t('recipe-compare.select-two') }}
    </v-alert>

    <template v-else>
      <h2 class="text-h6 mt-6 mb-2">
        {{ $t('recipe-compare.details') }}
      </h2>
      <v-table
        density="comfortable"
        data-testid="compare-details"
      >
        <thead>
          <tr>
            <th />
            <th>
              <router-link :to="recipeLink(selectedA?.slug)">
                {{ selectedA?.name }}
              </router-link>
            </th>
            <th>
              <router-link :to="recipeLink(selectedB?.slug)">
                {{ selectedB?.name }}
              </router-link>
            </th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in comparison.details"
            :key="row.key"
            :data-testid="`compare-detail-${row.key}`"
            :data-different="row.different"
          >
            <td class="font-weight-medium">
              {{ $t(detailLabelKey(row.key)) }}
            </td>
            <td>{{ row.a ?? $t('recipe-compare.not-set') }}</td>
            <td>{{ row.b ?? $t('recipe-compare.not-set') }}</td>
            <td>
              <v-chip
                v-if="row.different"
                size="small"
                color="warning"
                variant="tonal"
              >
                {{ $t('recipe-compare.different') }}
              </v-chip>
            </td>
          </tr>
        </tbody>
      </v-table>

      <h2 class="text-h6 mt-8 mb-1">
        {{ $t('recipe.ingredients') }}
      </h2>
      <p
        class="text-body-2 mb-2"
        data-testid="compare-ingredient-counts"
      >
        {{ $t('recipe-compare.ingredient-counts', { shared: comparison.shared.length, onlyA: comparison.onlyA.length, onlyB: comparison.onlyB.length }) }}
      </p>
      <p
        class="text-caption text-medium-emphasis mb-2"
        data-testid="compare-matching-note"
      >
        {{ $t('recipe-compare.matching-note') }}
      </p>

      <h3 class="text-subtitle-1 mt-4 mb-1">
        {{ $t('recipe-compare.in-both') }} ({{ comparison.shared.length }})
      </h3>
      <v-table
        v-if="comparison.shared.length"
        density="compact"
        data-testid="compare-shared"
      >
        <thead>
          <tr>
            <th />
            <th>{{ selectedA?.name }}</th>
            <th>{{ selectedB?.name }}</th>
            <th />
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="item in comparison.shared"
            :key="item.key"
            :data-testid="`compare-shared-${item.key}`"
            :data-different="item.different"
          >
            <td class="font-weight-medium">
              {{ item.label }}
            </td>
            <td>{{ item.a || '—' }}</td>
            <td>{{ item.b || '—' }}</td>
            <td>
              <v-chip
                v-if="item.different"
                size="small"
                color="warning"
                variant="tonal"
              >
                {{ $t('recipe-compare.different') }}
              </v-chip>
            </td>
          </tr>
        </tbody>
      </v-table>
      <p
        v-else
        class="text-medium-emphasis"
      >
        {{ $t('recipe-compare.none') }}
      </p>

      <v-row class="mt-2">
        <v-col
          cols="12"
          md="6"
        >
          <h3 class="text-subtitle-1 mb-1">
            {{ $t('recipe-compare.only-in', { name: selectedA?.name }) }} ({{ comparison.onlyA.length }})
          </h3>
          <v-list
            v-if="comparison.onlyA.length"
            density="compact"
            data-testid="compare-only-a"
          >
            <v-list-item
              v-for="item in comparison.onlyA"
              :key="item.key"
            >
              <v-list-item-title>{{ item.label }}</v-list-item-title>
              <v-list-item-subtitle v-if="item.amount">
                {{ item.amount }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <p
            v-else
            class="text-medium-emphasis"
          >
            {{ $t('recipe-compare.none') }}
          </p>
        </v-col>
        <v-col
          cols="12"
          md="6"
        >
          <h3 class="text-subtitle-1 mb-1">
            {{ $t('recipe-compare.only-in', { name: selectedB?.name }) }} ({{ comparison.onlyB.length }})
          </h3>
          <v-list
            v-if="comparison.onlyB.length"
            density="compact"
            data-testid="compare-only-b"
          >
            <v-list-item
              v-for="item in comparison.onlyB"
              :key="item.key"
            >
              <v-list-item-title>{{ item.label }}</v-list-item-title>
              <v-list-item-subtitle v-if="item.amount">
                {{ item.amount }}
              </v-list-item-subtitle>
            </v-list-item>
          </v-list>
          <p
            v-else
            class="text-medium-emphasis"
          >
            {{ $t('recipe-compare.none') }}
          </p>
        </v-col>
      </v-row>
    </template>
  </v-container>
</template>

<script setup lang="ts">
import { detailLabelKey, useRecipeCompare } from "~/composables/recipes/use-recipe-compare";
import { useUserApi } from "~/composables/api";

const i18n = useI18n();
const route = useRoute();
const router = useRouter();
const groupSlug = computed(() => route.params.groupSlug as string);
const api = useUserApi();

useSeoMeta({
  title: i18n.t("recipe-compare.compare-recipes"),
});

const { selectedA, selectedB, loading, error, sameRecipe, comparison, setSlugs, load } = useRecipeCompare(
  slug => api.recipes.getOne(slug),
);

function queryValue(value: unknown): string | null {
  const first = Array.isArray(value) ? value[0] : value;
  return typeof first === "string" && first ? first : null;
}

// The page address is the source of truth, so a comparison can be bookmarked or shared.
watch(
  () => [route.query.a, route.query.b],
  () => {
    setSlugs(queryValue(route.query.a), queryValue(route.query.b));
    load();
  },
  { immediate: true },
);

function choose(side: "a" | "b", recipe: { slug?: string } | null) {
  router.replace({ query: { ...route.query, [side]: recipe?.slug || undefined } });
}

function recipeLink(slug: string | undefined) {
  return `/g/${groupSlug.value}/r/${slug ?? ""}`;
}
</script>
