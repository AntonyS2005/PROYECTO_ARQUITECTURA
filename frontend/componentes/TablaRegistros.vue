<script setup>
import { computed } from "vue";
import { useDisplay } from "vuetify";

const props = defineProps({
  columnas: { type: Array, required: true },
  filas: { type: Array, required: true },
  porPagina: { type: Number, default: 4 },
  clave: { type: String, default: "id" },
  cargando: Boolean,
});
const { width } = useDisplay();
const movil = computed(() => width.value < 640);
const encabezados = computed(() =>
  props.columnas
    .filter((columna) => !movil.value || !columna.secundaria)
    .map((columna) => ({ key: columna.clave, title: columna.etiqueta })),
);
</script>

<template>
  <v-data-table
    :headers="encabezados"
    :items="filas"
    :item-value="clave"
    :items-per-page="movil ? 1 : porPagina"
    :mobile="movil"
    :loading="cargando"
    loading-text="Cargando registros…"
    density="compact"
    disable-sort
    :hide-default-header="movil"
    class="tabla-registros"
    no-data-text="No hay registros para mostrar."
  >
    <template
      v-for="columna in columnas"
      :key="columna.clave"
      #[`item.${columna.clave}`]="{ item }"
    >
      <slot :name="columna.clave" :fila="item">{{ item[columna.clave] }}</slot>
    </template>
    <template #bottom="{ page, pageCount, setPage }">
      <div
        v-if="filas.length"
        class="tw:flex tw:items-center tw:justify-between tw:gap-2 tw:mt-2"
      >
        <span class="texto-secundario"
          >{{ filas.length }} registros · {{ page }} / {{ pageCount }}</span
        >
        <v-pagination
          v-if="pageCount > 1"
          :model-value="page"
          :length="pageCount"
          :total-visible="movil ? 1 : 3"
          density="compact"
          size="small"
          active-color="primary"
          aria-label="Páginas de registros"
          @update:model-value="setPage"
        />
      </div>
    </template>
  </v-data-table>
</template>
