<script setup>
import { onMounted, ref } from "vue";
import {
  mdiCameraOutline,
  mdiCameraOffOutline,
  mdiQrcodeScan,
  mdiRefresh,
} from "@mdi/js";
import { usarSesion } from "../stores/sesion.js";
import { usarCamara } from "../composables/usarCamara.js";
import { usarAccion } from "../composables/usarAccion.js";
import { api, fechaLocal } from "../servicios/api.js";
import ListaEventos from "../componentes/ListaEventos.vue";

const sesion = usarSesion();
const video = ref(null);
const recientes = ref([]);
const { aviso, fallo: falloCarga, ejecutar } = usarAccion();
async function cargar() {
  await ejecutar(async () => {
    const consulta = sesion.administrador
      ? `?${new URLSearchParams({ desde: fechaLocal(), hasta: fechaLocal() })}`
      : "";
    recientes.value = (await api(`/eventos${consulta}`)).slice(0, 5);
  });
}
const {
  activa,
  buscando,
  enviando,
  segundos,
  proporcion,
  resultado,
  titulo,
  indicacion,
  fallo,
  iniciar,
  cancelar,
} = usarCamara(video, cargar);
defineExpose({ iniciar });
onMounted(cargar);
</script>

<template>
  <div class="accesos-distribucion">
    <v-card class="panel-camara">
      <div class="cabecera-panel">
        <div>
          <h2>Rostro y carné</h2>
          <p>La captura y la validación son automáticas.</p>
        </div>
        <v-icon :icon="mdiQrcodeScan" color="primary" />
      </div>
      <div
        class="camara-marco"
        :class="{ 'camara-error': fallo }"
        :style="{ aspectRatio: proporcion }"
      >
        <video
          ref="video"
          id="camera"
          v-show="activa"
          autoplay
          muted
          playsinline
        />
        <div v-if="activa" class="camara-guias" aria-hidden="true">
          <span>Rostro completo</span><span>Carné · QR visible</span>
        </div>
        <div v-else class="camara-vacia">
          <v-icon :icon="mdiCameraOutline" size="36" /><strong
            >Cámara desactivada</strong
          >
          <p>Rostro a la izquierda y carné a la derecha.</p>
        </div>
      </div>
      <div class="camara-controles">
        <p
          class="texto-secundario"
          :class="{ 'camara-estado': buscando }"
          role="status"
        >
          {{
            buscando
              ? enviando
                ? "Analizando la captura…"
                : `Detección automática · hasta ${segundos} s disponibles`
              : "El QR identifica el carné. El rostro confirma la identidad."
          }}
        </p>
        <v-btn
          v-if="!buscando"
          color="primary"
          :prepend-icon="mdiCameraOutline"
          block
          @click="iniciar"
          >Activar cámara</v-btn
        >
        <v-btn
          v-else
          color="secondary"
          variant="tonal"
          :prepend-icon="mdiCameraOffOutline"
          :disabled="enviando"
          block
          @click="cancelar"
          >Apagar cámara</v-btn
        >
      </div>
    </v-card>
    <div class="tw:flex tw:flex-col tw:gap-3 tw:min-w-0">
      <v-card
        class="panel-resultado"
        :class="{
          'resultado-error': fallo,
          'resultado-correcto': resultado && !fallo,
        }"
        role="status"
        aria-live="polite"
      >
        <p class="rotulo">RESULTADO DEL ACCESO</p>
        <h2>{{ titulo }}</h2>
        <p class="indicacion">{{ indicacion }}</p>
        <v-progress-linear
          v-if="buscando"
          indeterminate
          color="primary"
          class="tw:mt-3"
          rounded
        />
        <dl v-if="resultado" class="datos-resumen">
          <dt>Movimiento</dt>
          <dd>{{ resultado.tipo || "Rechazado" }}</dd>
          <dt>Carné</dt>
          <dd class="uuid">{{ resultado.uuid }}</dd>
          <dt>Nodo</dt>
          <dd>{{ resultado.nodo }}</dd>
        </dl>
      </v-card>
      <v-card class="panel-recientes">
        <details>
          <summary>
            Actividad reciente
            <span class="texto-secundario"
              >{{ recientes.length }} registros</span
            >
          </summary>
          <div class="tw:flex tw:items-center tw:justify-between tw:my-2">
            <p class="texto-secundario">
              {{
                sesion.administrador
                  ? "Últimos movimientos de hoy."
                  : "Últimos movimientos de esta sesión."
              }}
            </p>
            <v-btn
              :icon="mdiRefresh"
              size="small"
              variant="text"
              aria-label="Actualizar actividad"
              @click="cargar"
            />
          </div>
          <ListaEventos :eventos="recientes" />
        </details>
      </v-card>
      <v-alert v-if="aviso" :type="falloCarga ? 'error' : 'success'">{{
        aviso
      }}</v-alert>
    </div>
  </div>
</template>
