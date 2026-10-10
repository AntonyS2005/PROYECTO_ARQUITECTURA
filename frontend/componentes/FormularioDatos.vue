<script setup>
import { nextTick, reactive, ref } from "vue";
import { limites, validar } from "../../public/validaciones.js";
import { normalizarFoto } from "../servicios/imagenes.js";

const props = defineProps({
  tipo: { type: String, required: true },
  campos: { type: Array, required: true },
  accion: { type: Function, required: true },
  boton: { type: String, required: true },
  inicial: { type: Object, default: () => ({}) },
  bloquearNombres: Boolean,
});
const valores = reactive(
  Object.fromEntries(
    props.campos.map((campo) => [
      campo.nombre,
      props.inicial[campo.nombre] ?? campo.inicial ?? "",
    ]),
  ),
);
const errores = ref({});
const mensaje = ref("");
const ocupado = ref(false);
const procesandoFoto = ref(false);
const archivo = ref(null);
const entradaFoto = ref(null);
const formulario = ref(null);
let seleccion = 0;

function revisar(nombre) {
  errores.value = { ...errores.value, [nombre]: undefined };
  mensaje.value = "";
  if (nombre === "foto") entradaFoto.value?.validate();
}

const reglas = Object.fromEntries(
  props.campos.map((campo) => [
    campo.nombre,
    [() => validar(props.tipo, valores)[campo.nombre] || true],
  ]),
);

async function seleccionarFoto(valor) {
  const turno = ++seleccion;
  valores.foto = "";
  const foto = Array.isArray(valor) ? valor[0] : valor;
  if (!foto) {
    procesandoFoto.value = false;
    revisar("foto");
    return;
  }
  procesandoFoto.value = true;
  try {
    const resultado = await normalizarFoto(foto);
    if (seleccion !== turno) return;
    valores.foto = resultado;
    revisar("foto");
  } catch (error) {
    if (seleccion === turno)
      errores.value = { ...errores.value, foto: error.message };
  } finally {
    if (seleccion === turno) procesandoFoto.value = false;
  }
}

async function enviar(evento) {
  if (ocupado.value || procesandoFoto.value) return;
  ocupado.value = true;
  errores.value = {};
  mensaje.value = "";
  try {
    const resultado = await (evento || formulario.value.validate());
    if (!resultado.valid) {
      mensaje.value = "Revise los campos indicados.";
      ocupado.value = false;
      await nextTick();
      formulario.value.$el.querySelector(".v-input--error input")?.focus();
      return;
    }
    await props.accion({ ...valores });
  } catch (error) {
    errores.value = error.errores || {};
    mensaje.value = error.message;
  } finally {
    ocupado.value = false;
  }
}

defineExpose({ valores, ocupado, enviar });
</script>

<template>
  <v-form
    ref="formulario"
    novalidate
    class="formulario-datos"
    validate-on="blur"
    @submit.prevent="enviar"
  >
    <template v-for="campo in campos" :key="campo.nombre">
      <v-file-input
        v-if="campo.tipo === 'file'"
        :ref="(entrada) => (entradaFoto = entrada)"
        v-model="archivo"
        :label="campo.etiqueta"
        :name="campo.nombre"
        required
        accept="image/jpeg,image/png"
        :error-messages="errores[campo.nombre]"
        :rules="reglas[campo.nombre]"
        validate-on="submit"
        :hint="campo.ayuda"
        persistent-hint
        :disabled="ocupado"
        prepend-icon=""
        @update:model-value="seleccionarFoto"
      />
      <v-select
        v-else-if="campo.opciones"
        v-model="valores[campo.nombre]"
        :label="campo.etiqueta"
        required
        :items="campo.opciones"
        item-title="etiqueta"
        item-value="valor"
        :error-messages="errores[campo.nombre]"
        :rules="reglas[campo.nombre]"
        :disabled="ocupado"
        @update:model-value="revisar(campo.nombre)"
      />
      <v-text-field
        v-else
        v-model="valores[campo.nombre]"
        :name="campo.nombre"
        :label="campo.etiqueta"
        required
        :type="campo.tipo || 'text'"
        :autocomplete="campo.autocomplete || 'off'"
        :maxlength="limites[campo.nombre]"
        :counter="limites[campo.nombre]"
        :error-messages="errores[campo.nombre]"
        :rules="reglas[campo.nombre]"
        :hint="campo.ayuda"
        persistent-hint
        :readonly="
          bloquearNombres && ['nombres', 'apellidos'].includes(campo.nombre)
        "
        :disabled="ocupado"
        @update:model-value="revisar(campo.nombre)"
      />
    </template>
    <img
      v-if="valores.foto"
      :src="valores.foto"
      alt="Fotografía seleccionada"
      class="vista-foto"
    />
    <v-alert
      v-if="mensaje"
      type="error"
      density="compact"
      variant="tonal"
      role="alert"
      >{{ mensaje }}</v-alert
    >
    <div class="tw:flex tw:flex-wrap tw:gap-2">
      <v-btn
        type="submit"
        color="primary"
        :loading="ocupado || procesandoFoto"
        >{{ boton }}</v-btn
      >
      <slot :ocupado="ocupado" />
    </div>
  </v-form>
</template>
