<script setup>
import { computed, onMounted, reactive, ref } from "vue";
import { useDisplay } from "vuetify";
import {
  mdiDownload,
  mdiLogin,
  mdiLogout,
  mdiCloseCircleOutline,
  mdiAccountGroupOutline,
  mdiClockOutline,
} from "@mdi/js";
import { validar } from "../../public/validaciones.js";
import { api, fechaLocal } from "../servicios/api.js";
import { usarAccion } from "../composables/usarAccion.js";
import ListaEventos from "../componentes/ListaEventos.vue";
import TablaRegistros from "../componentes/TablaRegistros.vue";

const periodo = reactive({ desde: fechaLocal(), hasta: fechaLocal() });
const errores = ref({});
const metricas = ref(null);
const eventos = ref([]);
const periodoAplicado = ref(null);
const filtroAplicado = ref("");
const pendiente = computed(
  () =>
    Boolean(periodoAplicado.value) &&
    (periodo.desde !== periodoAplicado.value.desde ||
      periodo.hasta !== periodoAplicado.value.hasta),
);
const filtroActivo = computed(() =>
  pendiente.value ? "" : filtroAplicado.value,
);
const formatoFecha = (fecha) => fecha.split("-").reverse().join("/");
const { width } = useDisplay();
const movil = computed(() => width.value < 640);
const estadisticasAbiertas = ref(movil.value ? null : "estadisticas");
const { ocupado, aviso, fallo, ejecutar } = usarAccion();
const indicadores = computed(() =>
  metricas.value
    ? [
        ["Entradas", metricas.value.entradas, mdiLogin, "primary"],
        ["Salidas", metricas.value.salidas, mdiLogout, "secondary"],
        [
          "Rechazados",
          metricas.value.rechazados,
          mdiCloseCircleOutline,
          "error",
        ],
        [
          "Dentro ahora",
          metricas.value.aforo,
          mdiAccountGroupOutline,
          "primary",
        ],
        [
          "Permanencia media",
          `${metricas.value.promedioMinutos} min`,
          mdiClockOutline,
          "secondary",
        ],
      ]
    : [],
);
const maximo = computed(() =>
  Math.max(1, ...(metricas.value?.horas || []).map((dato) => dato.total)),
);
const consulta = (fechas) => new URLSearchParams(fechas).toString();

function revisar() {
  errores.value = validar("periodo", periodo);
  return !Object.keys(errores.value).length;
}
async function cargar(filtro = "personalizado") {
  if (ocupado.value || !revisar()) return;
  const fechas = { ...periodo };
  await ejecutar(async () => {
    const resultado = await Promise.all([
      api(`/metricas?${consulta(fechas)}`),
      api(`/eventos?${consulta(fechas)}`),
    ]);
    [metricas.value, eventos.value] = resultado;
    periodoAplicado.value = fechas;
    filtroAplicado.value = filtro;
  });
}
function establecer(semana = false) {
  const inicio = new Date();
  if (semana) inicio.setDate(inicio.getDate() - ((inicio.getDay() + 6) % 7));
  periodo.desde = fechaLocal(inicio);
  periodo.hasta = fechaLocal();
  cargar(semana ? "semana" : "hoy");
}
async function exportar() {
  if (!periodoAplicado.value || pendiente.value || ocupado.value) return;
  await ejecutar(async () => {
    const respuesta = await fetch(
      `/api/exportar?${consulta(periodoAplicado.value)}`,
      {
        credentials: "same-origin",
      },
    );
    if (!respuesta.ok) {
      if (respuesta.status === 401)
        window.dispatchEvent(new Event("sesion-finalizada"));
      throw new Error((await respuesta.json()).mensaje);
    }
    const url = URL.createObjectURL(await respuesta.blob());
    const enlace = document.createElement("a");
    enlace.href = url;
    enlace.download = "reporte-accesos.csv";
    enlace.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}
onMounted(() => cargar("hoy"));
</script>

<template>
  <v-card class="panel-filtro">
    <form class="filtros" novalidate @submit.prevent="cargar()">
      <v-text-field
        v-model="periodo.desde"
        label="Desde"
        type="date"
        :error-messages="errores.desde"
        :disabled="ocupado"
        @update:model-value="revisar"
      />
      <v-text-field
        v-model="periodo.hasta"
        label="Hasta"
        type="date"
        :error-messages="errores.hasta"
        :disabled="ocupado"
        @update:model-value="revisar"
      />
      <div class="tw:flex tw:flex-wrap tw:gap-2">
        <v-btn
          type="submit"
          color="primary"
          :variant="
            filtroActivo === 'personalizado' || pendiente ? 'flat' : 'outlined'
          "
          :aria-pressed="filtroActivo === 'personalizado'"
          :loading="ocupado"
          >Consultar</v-btn
        ><v-btn
          :variant="filtroActivo === 'hoy' ? 'flat' : 'tonal'"
          :color="filtroActivo === 'hoy' ? 'primary' : undefined"
          :aria-pressed="filtroActivo === 'hoy'"
          :disabled="ocupado"
          @click="establecer()"
          >Hoy</v-btn
        ><v-btn
          :variant="filtroActivo === 'semana' ? 'flat' : 'tonal'"
          :color="filtroActivo === 'semana' ? 'primary' : undefined"
          :aria-pressed="filtroActivo === 'semana'"
          :disabled="ocupado"
          @click="establecer(true)"
          >Semana</v-btn
        ><v-btn
          variant="text"
          :prepend-icon="mdiDownload"
          :disabled="ocupado || pendiente || !periodoAplicado"
          @click="exportar"
          >CSV</v-btn
        >
      </div>
    </form>
    <div
      class="estado-filtro texto-secundario"
      role="status"
      aria-live="polite"
    >
      <p v-if="ocupado">Procesando consulta…</p>
      <p v-else-if="periodoAplicado">
        Período aplicado: {{ formatoFecha(periodoAplicado.desde) }} –
        {{ formatoFecha(periodoAplicado.hasta) }} ·
        {{
          filtroAplicado === "hoy"
            ? "Hoy"
            : filtroAplicado === "semana"
              ? "Semana"
              : "Personalizado"
        }}.
      </p>
      <p v-if="pendiente">
        Fechas modificadas. Seleccione Consultar para aplicarlas.
      </p>
    </div>
  </v-card>
  <v-alert v-if="aviso" :type="fallo ? 'error' : 'success'" class="tw:mt-3">{{
    aviso
  }}</v-alert>
  <div v-if="metricas" class="metricas" aria-label="Totales del período">
    <v-chip
      v-for="[etiqueta, valor, icono, color] in indicadores"
      :key="etiqueta"
      :prepend-icon="icono"
      :color="color"
      class="indicador-metrica"
      >{{ etiqueta }} <strong>{{ valor }}</strong></v-chip
    >
  </div>
  <v-expansion-panels
    v-if="metricas"
    v-model="estadisticasAbiertas"
    class="estadisticas"
    variant="accordion"
  >
    <v-expansion-panel value="estadisticas" elevation="0">
      <v-expansion-panel-title min-height="40" class="tw:py-2 tw:px-3"
        >Estadísticas del período</v-expansion-panel-title
      >
      <v-expansion-panel-text>
        <div class="tw:grid tw:gap-3 tw:md:grid-cols-2 tw:mt-1">
          <v-card class="panel-lista"
            ><h2>Movimientos por hora</h2>
            <div
              class="histograma"
              role="img"
              :aria-label="
                metricas.horas
                  .filter((d) => d.total)
                  .map((d) => `${d.hora} horas: ${d.total}`)
                  .join('; ') || 'No hay movimientos.'
              "
            >
              <div
                v-for="dato in metricas.horas"
                :key="dato.hora"
                :style="{ height: `${(dato.total / maximo) * 100}%` }"
                :title="`${dato.hora}:00 · ${dato.total} movimientos`"
              />
            </div>
            <div class="tw:flex tw:justify-between texto-secundario">
              <span>00 h</span><span>12 h</span><span>23 h</span>
            </div></v-card
          >
          <v-card class="panel-lista"
            ><h2 class="tw:mb-1">Frecuencia de acceso</h2>
            <TablaRegistros
              :columnas="[
                { clave: 'nombre', etiqueta: 'Persona' },
                { clave: 'total', etiqueta: 'Movimientos' },
              ]"
              :filas="metricas.recurrencia"
              :por-pagina="2"
              clave="uuid"
          /></v-card>
        </div>
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
  <v-card class="panel-lista"
    ><h2 class="tw:mb-3">Bitácora del período</h2>
    <ListaEventos
      :eventos="eventos"
      :por-pagina="2"
      :cargando="ocupado"
      detallado
  /></v-card>
</template>
