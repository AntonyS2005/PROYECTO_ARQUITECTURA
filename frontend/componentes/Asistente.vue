<script setup>
import { onUnmounted, ref } from "vue";
import { mdiMicrophone, mdiMessageTextOutline } from "@mdi/js";
import {
  LIMITE_TEXTO,
  validarConsulta,
  esAudioValido,
} from "../../public/asistente/reglas.js";
import { grabarComando } from "../../public/asistente/microfono.js";
import { api } from "../servicios/api.js";

defineProps({ voz: Boolean });
const emitir = defineEmits(["navegar", "capturar"]);
const abierto = ref(false);
const texto = ref("");
const error = ref("");
const respuesta = ref("");
const ocupado = ref(false);
const leer = ref(false);
const vigencia = new AbortController();

async function consultar() {
  if (ocupado.value) return;
  error.value = validarConsulta(texto.value).texto || "";
  if (error.value) return;
  ocupado.value = true;
  try {
    const resultado = await api("/asistente/consulta", {
      method: "POST",
      body: { texto: texto.value },
    });
    if (vigencia.signal.aborted) return;
    respuesta.value = resultado.mensaje;
    if (resultado.accion?.tipo === "navegar")
      emitir("navegar", resultado.accion.vista);
    if (resultado.accion?.tipo === "capturar") emitir("capturar");
    if (leer.value && window.speechSynthesis) {
      const voz = speechSynthesis
        .getVoices()
        .find((voz) => voz.localService && /^es(?:-|_)/i.test(voz.lang));
      if (voz) {
        speechSynthesis.cancel();
        const locucion = new SpeechSynthesisUtterance(resultado.mensaje);
        locucion.voice = voz;
        locucion.lang = voz.lang;
        speechSynthesis.speak(locucion);
      }
    }
  } catch (fallo) {
    if (!vigencia.signal.aborted) error.value = fallo.message;
  } finally {
    ocupado.value = false;
  }
}

async function grabar() {
  ocupado.value = true;
  error.value = "";
  respuesta.value = "Grabando durante cinco segundos…";
  try {
    const audio = await grabarComando(vigencia.signal);
    if (vigencia.signal.aborted) return;
    if (!esAudioValido(audio))
      throw new Error("Audio no válido. Intente nuevamente.");
    respuesta.value = "Procesando audio…";
    const resultado = await api("/asistente/transcribir", {
      method: "POST",
      body: { audio },
    });
    if (vigencia.signal.aborted) return;
    texto.value = resultado.texto;
    respuesta.value = "Revise el texto y seleccione Consultar.";
  } catch {
    if (!vigencia.signal.aborted)
      error.value = "Voz no disponible. Escriba la consulta.";
  } finally {
    ocupado.value = false;
  }
}
onUnmounted(() => {
  vigencia.abort();
  window.speechSynthesis?.cancel();
});
</script>

<template>
  <v-btn
    variant="text"
    size="small"
    :prepend-icon="mdiMessageTextOutline"
    @click="abierto = true"
    >Asistente</v-btn
  >
  <v-dialog v-model="abierto" max-width="440" scrollable>
    <v-card class="tw:p-5">
      <h2>Asistente opcional</h2>
      <p class="texto-secundario tw:mb-4">
        Escriba «ayuda» para consultar los comandos.
      </p>
      <form novalidate @submit.prevent="consultar">
        <v-text-field
          v-model="texto"
          label="Consulta"
          :maxlength="LIMITE_TEXTO"
          :error-messages="error"
          :disabled="ocupado"
          @update:model-value="error = ''"
        />
        <div class="tw:flex tw:flex-wrap tw:gap-2 tw:mt-3">
          <v-btn type="submit" color="primary" :loading="ocupado"
            >Consultar</v-btn
          ><v-btn
            v-if="voz"
            variant="tonal"
            :prepend-icon="mdiMicrophone"
            :disabled="ocupado"
            @click="grabar"
            >Grabar · 5 s</v-btn
          ><v-btn variant="text" @click="abierto = false">Cerrar</v-btn>
        </div>
      </form>
      <v-checkbox
        v-model="leer"
        label="Leer respuestas con voz local"
        density="compact"
        hide-details
      />
      <p role="status" aria-live="polite">{{ respuesta }}</p>
    </v-card>
  </v-dialog>
</template>
