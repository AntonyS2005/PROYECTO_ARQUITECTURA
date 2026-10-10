<script setup>
import { onMounted, ref } from "vue";
import { mdiRefresh } from "@mdi/js";
import { api } from "../servicios/api.js";
import { usarAccion } from "../composables/usarAccion.js";

const informacion = ref(null);
const { ocupado, aviso, ejecutar } = usarAccion();
async function cargar() {
  await ejecutar(async () => {
    informacion.value = await api("/nodo");
  });
}
onMounted(cargar);
</script>

<template>
  <v-alert v-if="aviso" type="error" class="tw:mb-3">{{ aviso }}</v-alert>
  <v-card class="panel-lista">
    <div class="cabecera-panel">
      <h2>Coordinador y nodos</h2>
      <v-btn
        :icon="mdiRefresh"
        size="small"
        variant="text"
        aria-label="Actualizar estado"
        :loading="ocupado"
        @click="cargar"
      />
    </div>
    <template v-if="informacion">
      <dl class="datos-resumen">
        <dt>Coordinador</dt>
        <dd>{{ informacion.nombre }}</dd>
        <dt>Base de datos</dt>
        <dd>{{ informacion.baseDatos }}</dd>
        <dt>Tiempo activo</dt>
        <dd>{{ Math.floor(informacion.tiempoActivoSegundos / 60) }} minutos</dd>
        <dt>Memoria del proceso</dt>
        <dd>{{ informacion.memoriaMb }} MB</dd>
      </dl>
      <div class="tw:grid tw:gap-3 tw:sm:grid-cols-2 tw:mt-4">
        <v-card
          v-for="nodo in informacion.nodos"
          :key="nodo.id"
          class="tw:p-4"
          variant="tonal"
          ><h3>{{ nodo.id }}</h3>
          <p>
            {{ nodo.status
            }}<span v-if="nodo.latenciaMs !== null">
              · {{ nodo.latenciaMs }} ms</span
            >
          </p></v-card
        >
      </div>
    </template>
  </v-card>
</template>
