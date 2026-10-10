<script setup>
import TablaRegistros from "./TablaRegistros.vue";
import { ref } from "vue";
import { usarSesion } from "../stores/sesion.js";
import { fechaHora } from "../servicios/api.js";
import {
  mdiLogin,
  mdiLogout,
  mdiCloseCircleOutline,
  mdiCameraOutline,
} from "@mdi/js";

const sesion = usarSesion();
const fotoEvento = ref(null);
const errorFoto = ref(false);
function verFoto(evento) {
  errorFoto.value = false;
  fotoEvento.value = evento;
}

const props = defineProps({
  eventos: { type: Array, required: true },
  detallado: Boolean,
  cargando: Boolean,
  porPagina: { type: Number, default: 4 },
});
const columnas = [
  { clave: "persona", etiqueta: "Persona" },
  { clave: "fecha_hora", etiqueta: "Fecha y hora" },
  { clave: "estado", etiqueta: "Resultado" },
  ...(props.detallado
    ? [
        { clave: "usuario", etiqueta: "Operador", secundaria: true },
        { clave: "nodo", etiqueta: "Nodo", secundaria: true },
        { clave: "similitud", etiqueta: "Similitud", secundaria: true },
      ]
    : []),
];
</script>

<template>
  <TablaRegistros
    :columnas="columnas"
    :filas="eventos"
    :por-pagina="porPagina"
    :cargando="cargando"
  >
    <template #persona="{ fila }"
      ><strong>{{ fila.nombres }} {{ fila.apellidos }}</strong
      ><small class="uuid">{{ fila.uuid }}</small></template
    >
    <template #fecha_hora="{ fila }">{{ fechaHora(fila.fecha_hora) }}</template>
    <template #estado="{ fila }"
      ><div>
        <v-chip
          size="small"
          :prepend-icon="
            fila.estado === 'RECHAZADO'
              ? mdiCloseCircleOutline
              : fila.tipo === 'ENTRADA'
                ? mdiLogin
                : mdiLogout
          "
          :color="fila.estado === 'RECHAZADO' ? 'error' : 'primary'"
          >{{
            fila.estado === "RECHAZADO"
              ? "Rechazado"
              : fila.tipo === "ENTRADA"
                ? "Entrada"
                : "Salida"
          }}</v-chip
        >
        <v-btn
          v-if="sesion.administrador && fila.tiene_foto"
          size="small"
          variant="text"
          color="primary"
          :prepend-icon="mdiCameraOutline"
          @click="verFoto(fila)"
          >Ver foto</v-btn
        >
        <details v-if="detallado" class="evento-detalle">
          <summary>Ver detalles</summary>
          <dl class="datos-resumen">
            <dt>Operador</dt>
            <dd>{{ fila.usuario }}</dd>
            <dt>Nodo</dt>
            <dd>{{ fila.nodo }}</dd>
            <dt>Similitud</dt>
            <dd>{{ fila.similitud.toFixed(3) }}</dd>
          </dl>
        </details>
      </div></template
    >
    <template #similitud="{ fila }">{{ fila.similitud.toFixed(3) }}</template>
  </TablaRegistros>
  <v-dialog
    :model-value="Boolean(fotoEvento)"
    max-width="380"
    @update:model-value="
      (valor) => {
        if (!valor) fotoEvento = null;
      }
    "
  >
    <v-card v-if="fotoEvento" class="tw:p-4">
      <h2>Captura del intento rechazado</h2>
      <p class="texto-secundario tw:mt-1">
        {{ fechaHora(fotoEvento.fecha_hora) }}
      </p>
      <p class="texto-secundario tw:mt-1">
        Carné presentado: {{ fotoEvento.nombres }} {{ fotoEvento.apellidos }}.
      </p>
      <p v-if="errorFoto" class="mensaje-error tw:my-4" role="alert">
        La fotografía ya no está disponible.
      </p>
      <img
        v-else
        :src="`/api/eventos/${fotoEvento.id}/foto`"
        alt="Captura del intento de acceso rechazado"
        class="captura-rechazo"
        @error="errorFoto = true"
      />
      <p class="texto-secundario tw:mb-3">
        Se conservan las últimas 500 fotografías de rechazos.
      </p>
      <v-btn color="primary" @click="fotoEvento = null">Cerrar</v-btn>
    </v-card>
  </v-dialog>
</template>
