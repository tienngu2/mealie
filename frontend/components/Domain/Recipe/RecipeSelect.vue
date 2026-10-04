<template>
  <v-autocomplete
    v-model:search="search.query.value"
    :model-value="modelValue"
    :items="items"
    :label="label"
    :loading="search.loading.value"
    :prepend-inner-icon="$globals.icons.search"
    item-title="name"
    item-value="slug"
    return-object
    no-filter
    clearable
    variant="outlined"
    hide-details
    autocomplete="off"
    @update:model-value="onSelect"
  />
</template>

<script setup lang="ts">
import { useUserApi } from "~/composables/api";
import { useRecipeSearch } from "~/composables/recipes/use-recipe-search";
import type { Recipe } from "~/lib/api/types/recipe";

type RecipeOption = Pick<Recipe, "name" | "slug">;

const props = defineProps<{
  modelValue: RecipeOption | null;
  label: string;
}>();

const emit = defineEmits<{
  "update:modelValue": [recipe: RecipeOption | null];
}>();

const search = useRecipeSearch(useUserApi());

// The server does the filtering; the current selection stays in the list so its name stays visible.
const items = computed<RecipeOption[]>(() => {
  const found: RecipeOption[] = search.data.value.map(recipe => ({ name: recipe.name, slug: recipe.slug }));
  const current = props.modelValue;
  return current && !found.some(option => option.slug === current.slug) ? [current, ...found] : found;
});

onMounted(() => search.trigger());

function onSelect(value: RecipeOption | null) {
  emit("update:modelValue", value ?? null);
}
</script>
