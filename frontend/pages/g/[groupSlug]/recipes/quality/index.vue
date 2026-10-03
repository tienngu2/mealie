<template>
  <v-container>
    <BasePageTitle divider>
      <template #header>
        <v-img
          width="100"
          max-height="100"
          max-width="100"
          src="/svgs/manage-cookbooks.svg"
        />
      </template>
      <template #title>
        {{ $t('recipe-quality.recipe-quality') }}
      </template>

      <template #content>
        {{ $t('recipe-quality.description') }}
      </template>
    </BasePageTitle>

    <v-alert
      v-if="error"
      type="error"
      variant="tonal"
      class="mb-4"
      data-testid="quality-error"
    >
      {{ $t('recipe-quality.load-error') }}
      <template #append>
        <v-btn
          variant="text"
          @click="load"
        >
          {{ $t('recipe-quality.retry') }}
        </v-btn>
      </template>
    </v-alert>

    <div class="mb-2 text-subtitle-2">
      {{ $t('recipe-quality.filter-by-issue') }}
    </div>
    <div class="d-flex flex-wrap ga-2 mb-4">
      <v-chip
        v-for="chip in chips"
        :key="chip.code"
        :color="chip.severity === 'error' ? 'error' : 'warning'"
        :variant="chip.selected ? 'flat' : 'outlined'"
        :data-testid="`quality-chip-${chip.code}`"
        @click="toggleCode(chip.code)"
      >
        {{ $t(messageKey(chip.code)) }} · {{ chip.count }}
      </v-chip>
      <v-btn
        v-if="selectedCodes.length"
        size="small"
        variant="text"
        data-testid="quality-clear"
        @click="clearCodes"
      >
        {{ $t('recipe-quality.clear-filters') }}
      </v-btn>
    </div>

    <v-progress-linear
      v-if="loading"
      indeterminate
      class="mb-4"
    />

    <v-alert
      v-else-if="allClear"
      type="success"
      variant="tonal"
      data-testid="quality-all-clear"
    >
      {{ $t('recipe-quality.all-clear') }}
    </v-alert>

    <v-alert
      v-else-if="report && !report.items.length && !error"
      type="info"
      variant="tonal"
      data-testid="quality-no-matches"
    >
      {{ $t('recipe-quality.no-matches') }}
    </v-alert>

    <v-list
      v-else-if="report"
      lines="two"
      data-testid="quality-list"
    >
      <v-list-item
        v-for="item in report.items"
        :key="item.recipeId"
        :to="`/g/${groupSlug}/r/${item.slug}`"
      >
        <v-list-item-title>{{ item.name }}</v-list-item-title>
        <v-list-item-subtitle class="mt-1">
          <v-chip
            v-for="issue in item.issues"
            :key="issue.code"
            size="x-small"
            class="mr-1"
            :color="issue.severity === 'error' ? 'error' : 'warning'"
            variant="tonal"
          >
            {{ $t(messageKey(issue.code)) }}
          </v-chip>
        </v-list-item-subtitle>
      </v-list-item>
    </v-list>

    <v-pagination
      v-if="totalPages > 1"
      :model-value="page"
      :length="totalPages"
      class="mt-4"
      @update:model-value="setPage"
    />
  </v-container>
</template>

<script setup lang="ts">
import { useRecipeQuality, recipeQualityMessageKey as messageKey } from "~/composables/recipes/use-recipe-quality";
import { useUserApi } from "~/composables/api";

const i18n = useI18n();
const route = useRoute();
const groupSlug = computed(() => route.params.groupSlug as string);
const api = useUserApi();

useSeoMeta({
  title: i18n.t("recipe-quality.recipe-quality"),
});

const {
  report, loading, error, selectedCodes, page, chips, totalPages, allClear,
  load, toggleCode, clearCodes, setPage,
} = useRecipeQuality(query => api.recipes.getQualityReport(query));

onMounted(load);
</script>
