<script setup>
import { computed, onMounted, ref } from "vue";
import { useDisplay } from "vuetify";
import { mdiRefresh } from "@mdi/js";
import FormularioDatos from "../componentes/FormularioDatos.vue";
import TablaRegistros from "../componentes/TablaRegistros.vue";
import { usarSesion } from "../stores/sesion.js";
import { usarAccion } from "../composables/usarAccion.js";
import { api } from "../servicios/api.js";

const sesion = usarSesion();
const cuentas = ref([]);
const version = ref(0);
const formulario = ref(null);
const { width } = useDisplay();
const movil = computed(() => width.value < 640);
const mostrandoFormulario = ref(false);
const { ocupado, aviso, fallo, ejecutar } = usarAccion();
const columnas = [
  { clave: "cuenta", etiqueta: "Cuenta" },
  { clave: "rol", etiqueta: "Rol" },
  { clave: "activo", etiqueta: "Estado" },
  { clave: "accion", etiqueta: "Acción" },
];
const campos = [
  {
    nombre: "nombres",
    etiqueta: "Nombre de la cuenta",
    ayuda: "De 2 a 100 caracteres.",
  },
  {
    nombre: "usuario",
    etiqueta: "Usuario",
    ayuda: "De 3 a 30 caracteres.",
    autocomplete: "username",
  },
  {
    nombre: "clave",
    etiqueta: "Contraseña",
    tipo: "password",
    ayuda: "De 8 a 64 caracteres; máximo 72 bytes.",
    autocomplete: "new-password",
  },
  {
    nombre: "rol",
    etiqueta: "Rol",
    inicial: "OPERADOR",
    opciones: [
      { valor: "OPERADOR", etiqueta: "Operador" },
      { valor: "ADMINISTRADOR", etiqueta: "Administrador" },
    ],
  },
];
async function cargar() {
  await ejecutar(async () => {
    cuentas.value = await api("/cuentas");
  });
}
async function guardar(valores) {
  const resultado = await api("/cuentas", { method: "POST", body: valores });
  version.value++;
  mostrandoFormulario.value = false;
  await cargar();
  if (!fallo.value) aviso.value = resultado.mensaje;
}
async function alternar(cuenta) {
  await ejecutar(async () => {
    const resultado = await api(`/cuentas/${cuenta.id}`, {
      method: "PATCH",
      body: { activo: !cuenta.activo },
    });
    cuenta.activo = !cuenta.activo;
    return resultado;
  });
}
onMounted(cargar);
</script>

<template>
  <v-alert
    v-if="aviso"
    :type="fallo ? 'error' : 'success'"
    class="tw:mb-3"
    closable
    @click:close="aviso = ''"
    >{{ aviso }}</v-alert
  >
  <div v-if="movil" class="tw:flex tw:gap-2 tw:mb-3">
    <v-btn
      :variant="mostrandoFormulario ? 'text' : 'tonal'"
      color="primary"
      :disabled="formulario?.ocupado"
      @click="mostrandoFormulario = false"
      >Registradas</v-btn
    ><v-btn
      :variant="mostrandoFormulario ? 'tonal' : 'text'"
      color="primary"
      :disabled="formulario?.ocupado"
      @click="mostrandoFormulario = true"
      >Registrar cuenta</v-btn
    >
  </div>
  <div class="administracion-distribucion">
    <v-card v-show="!movil || mostrandoFormulario" class="panel-formulario"
      ><h2>Registrar cuenta</h2>
      <p class="texto-secundario tw:mb-4">Todos los campos son obligatorios.</p>
      <FormularioDatos
        ref="formulario"
        :key="version"
        tipo="cuenta"
        :campos="campos"
        :accion="guardar"
        boton="Registrar cuenta"
    /></v-card>
    <v-card v-show="!movil || !mostrandoFormulario" class="panel-lista">
      <div class="cabecera-panel">
        <h2>Cuentas registradas</h2>
        <v-btn
          :icon="mdiRefresh"
          size="small"
          variant="text"
          aria-label="Actualizar cuentas"
          :disabled="ocupado"
          @click="cargar"
        />
      </div>
      <TablaRegistros :columnas="columnas" :filas="cuentas" :cargando="ocupado">
        <template #cuenta="{ fila }"
          ><strong>{{ fila.nombres }}</strong
          ><small class="texto-secundario tw:block">{{
            fila.usuario
          }}</small></template
        >
        <template #rol="{ fila }">{{
          fila.rol === "ADMINISTRADOR" ? "Administrador" : "Operador"
        }}</template>
        <template #activo="{ fila }"
          ><v-chip size="small" :color="fila.activo ? 'primary' : 'default'">{{
            fila.activo ? "Activa" : "Inactiva"
          }}</v-chip></template
        >
        <template #accion="{ fila }"
          ><v-btn
            size="small"
            variant="text"
            :disabled="ocupado || fila.id === sesion.cuenta.id"
            @click="alternar(fila)"
            >{{ fila.activo ? "Desactivar" : "Activar" }}</v-btn
          ></template
        >
      </TablaRegistros>
    </v-card>
  </div>
</template>
