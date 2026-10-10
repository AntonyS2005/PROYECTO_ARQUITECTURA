<script setup>
import {
  computed,
  defineAsyncComponent,
  nextTick,
  onMounted,
  onUnmounted,
  ref,
  watch,
} from "vue";
import {
  mdiAccountGroupOutline,
  mdiChartBoxOutline,
  mdiBadgeAccountHorizontalOutline,
  mdiServerNetwork,
  mdiQrcodeScan,
  mdiLogout,
} from "@mdi/js";
import { usarSesion } from "./stores/sesion.js";
import { useDisplay } from "vuetify";
import FormularioDatos from "./componentes/FormularioDatos.vue";
import Accesos from "./vistas/Accesos.vue";

const sesion = usarSesion();
const { width } = useDisplay();
const navegacionInferior = computed(() => width.value < 1024);
const vista = ref("operacion");
const pantalla = ref(null);
const Asistente = defineAsyncComponent(
  () => import("./componentes/Asistente.vue"),
);
const secciones = [
  {
    id: "operacion",
    titulo: "Registro de acceso",
    corto: "Accesos",
    icono: mdiQrcodeScan,
    componente: Accesos,
  },
  {
    id: "carnes",
    titulo: "Carnés",
    corto: "Carnés",
    icono: mdiBadgeAccountHorizontalOutline,
    componente: defineAsyncComponent(() => import("./vistas/Carnes.vue")),
  },
  {
    id: "reportes",
    titulo: "Consultas y reportes",
    corto: "Reportes",
    icono: mdiChartBoxOutline,
    componente: defineAsyncComponent(() => import("./vistas/Reportes.vue")),
  },
  {
    id: "cuentas",
    titulo: "Cuentas de usuario",
    corto: "Cuentas",
    icono: mdiAccountGroupOutline,
    componente: defineAsyncComponent(() => import("./vistas/Cuentas.vue")),
  },
  {
    id: "nodo",
    titulo: "Estado del sistema",
    corto: "Sistema",
    icono: mdiServerNetwork,
    componente: defineAsyncComponent(() => import("./vistas/Sistema.vue")),
  },
];
const disponibles = computed(() =>
  sesion.administrador ? secciones : secciones.slice(0, 1),
);
const actual = computed(
  () =>
    disponibles.value.find((seccion) => seccion.id === vista.value) ||
    secciones[0],
);
const camposLogin = [
  {
    nombre: "usuario",
    etiqueta: "Usuario",
    autocomplete: "username",
    ayuda: "De 3 a 30 caracteres.",
  },
  {
    nombre: "clave",
    etiqueta: "Contraseña",
    tipo: "password",
    autocomplete: "current-password",
    ayuda: "Máximo 64 caracteres y 72 bytes.",
  },
];
function navegar(destino) {
  if (!disponibles.value.some((seccion) => seccion.id === destino)) return;
  vista.value = destino;
}
async function capturar() {
  navegar("operacion");
  await nextTick();
  pantalla.value?.iniciar();
}
function finalizar() {
  if (sesion.cuenta)
    sesion.finalizar("La sesión finalizó. Inicie sesión nuevamente.");
}
watch(
  () => sesion.cuenta,
  () => {
    vista.value = "operacion";
  },
);
onMounted(() => {
  window.addEventListener("sesion-finalizada", finalizar);
  for (const evento of ["pointerdown", "keydown", "input"])
    document.addEventListener(evento, sesion.actividad);
  sesion.recuperar();
});
onUnmounted(() => {
  window.removeEventListener("sesion-finalizada", finalizar);
  for (const evento of ["pointerdown", "keydown", "input"])
    document.removeEventListener(evento, sesion.actividad);
});
</script>

<template>
  <v-app>
    <div v-if="!sesion.preparada" class="cargando">
      <v-progress-circular indeterminate color="primary" />
      <p>Cargando aplicación…</p>
    </div>
    <main v-else-if="!sesion.cuenta" class="pantalla-login">
      <v-card class="tarjeta-login">
        <div class="marca-login">
          <span class="sello">CA</span>
          <div>
            <p class="rotulo">TERMINAL LOCAL</p>
            <h1>Control de acceso</h1>
          </div>
        </div>
        <p class="texto-secundario tw:mb-5">Registro de entradas y salidas.</p>
        <h2 class="tw:mb-4">Iniciar sesión</h2>
        <v-alert v-if="sesion.mensaje" type="info" class="tw:mb-4">{{
          sesion.mensaje
        }}</v-alert>
        <FormularioDatos
          tipo="login"
          :campos="camposLogin"
          :accion="sesion.ingresar"
          boton="Iniciar sesión"
        />
        <p class="texto-secundario tw:mt-5">
          Acceso exclusivo para personal autorizado.
        </p>
      </v-card>
    </main>
    <div v-else class="estructura-app">
      <aside v-if="!navegacionInferior" class="barra-lateral">
        <div class="marca">
          <span class="sello">CA</span><strong>Control de acceso</strong>
        </div>
        <v-list
          nav
          bg-color="transparent"
          aria-label="Principal"
          class="tw:p-0"
        >
          <v-list-item
            v-for="seccion in disponibles"
            :key="seccion.id"
            :active="actual.id === seccion.id"
            :prepend-icon="seccion.icono"
            :title="seccion.corto"
            rounded="lg"
            :aria-current="actual.id === seccion.id ? 'page' : undefined"
            @click="navegar(seccion.id)"
          />
        </v-list>
        <p class="estado-local"><span /> Operación local</p>
      </aside>
      <v-bottom-navigation
        v-else
        :model-value="actual.id"
        color="primary"
        grow
        height="62"
        aria-label="Principal"
        @update:model-value="navegar"
      >
        <v-btn
          v-for="seccion in disponibles"
          :key="seccion.id"
          :value="seccion.id"
          :aria-current="actual.id === seccion.id ? 'page' : undefined"
        >
          <v-icon :icon="seccion.icono" />
          <span>{{ seccion.corto }}</span>
        </v-btn>
      </v-bottom-navigation>
      <div class="contenido-app">
        <header class="barra-superior">
          <span class="marca-movil"
            ><span class="sello">CA</span
            ><strong>Control de acceso</strong></span
          >
          <span class="cuenta-nombre"
            >{{ sesion.cuenta.nombres }}
            <small
              >·
              {{ sesion.administrador ? "Administrador" : "Operador" }}</small
            ></span
          >
          <div class="tw:flex tw:items-center tw:gap-1">
            <Asistente
              v-if="sesion.modulos.asistente"
              :voz="sesion.modulos.voz"
              @navegar="navegar"
              @capturar="capturar"
            /><v-btn
              :icon="mdiLogout"
              variant="text"
              size="small"
              aria-label="Cerrar sesión"
              title="Cerrar sesión"
              @click="sesion.cerrar()"
            />
          </div>
        </header>
        <main class="contenido-principal">
          <div class="titulo-pagina">
            <h1>{{ actual.titulo }}</h1>
            <span class="texto-secundario etiqueta-local"
              >Proyecto académico · Red local</span
            >
          </div>
          <v-alert v-if="sesion.mensaje" type="error" class="tw:mb-3">{{
            sesion.mensaje
          }}</v-alert>
          <component :is="actual.componente" ref="pantalla" :key="actual.id" />
        </main>
      </div>
    </div>
  </v-app>
</template>
