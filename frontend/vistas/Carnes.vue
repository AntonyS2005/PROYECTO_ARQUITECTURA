<script setup>
import { computed, onMounted, ref } from "vue";
import { useDisplay } from "vuetify";
import { mdiRefresh } from "@mdi/js";
import FormularioDatos from "../componentes/FormularioDatos.vue";
import TablaRegistros from "../componentes/TablaRegistros.vue";
import { usarAccion } from "../composables/usarAccion.js";
import { api } from "../servicios/api.js";

const personas = ref([]);
const editando = ref(null);
const formulario = ref(null);
const version = ref(0);
const busqueda = ref("");
const { width } = useDisplay();
const movil = computed(() => width.value < 640);
const mostrandoFormulario = ref(false);
const { ocupado, aviso, fallo, ejecutar } = usarAccion();
const columnas = [
  { clave: "persona", etiqueta: "Persona" },
  { clave: "activo", etiqueta: "Estado" },
  { clave: "acciones", etiqueta: "Acciones" },
];
const campos = [
  { nombre: "nombres", etiqueta: "Nombres", ayuda: "De 2 a 100 caracteres." },
  {
    nombre: "apellidos",
    etiqueta: "Apellidos",
    ayuda: "De 2 a 100 caracteres.",
  },
  {
    nombre: "foto",
    etiqueta: "Fotografía del rostro",
    tipo: "file",
    ayuda: "JPEG o PNG, hasta 5 MB. Una persona, de frente.",
  },
];

async function cargar() {
  await ejecutar(async () => {
    personas.value = await api("/carnes");
  });
}
function editar(persona = null) {
  if (formulario.value?.ocupado) return;
  editando.value = persona;
  mostrandoFormulario.value = true;
  version.value++;
}
async function guardar(valores) {
  const uuid = editando.value?.uuid;
  const resultado = await api(uuid ? `/carnes/${uuid}/foto` : "/carnes", {
    method: uuid ? "PATCH" : "POST",
    body: uuid ? { foto: valores.foto } : valores,
  });
  editando.value = null;
  mostrandoFormulario.value = false;
  version.value++;
  await cargar();
  if (!fallo.value) aviso.value = resultado.mensaje;
}
async function alternar(persona) {
  await ejecutar(async () => {
    const resultado = await api(`/carnes/${persona.uuid}`, {
      method: "PATCH",
      body: { activo: !persona.activo },
    });
    persona.activo = !persona.activo;
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
      >Registrados</v-btn
    ><v-btn
      :variant="mostrandoFormulario ? 'tonal' : 'text'"
      color="primary"
      :disabled="formulario?.ocupado"
      @click="editar()"
      >Crear carné</v-btn
    >
  </div>
  <div class="administracion-distribucion">
    <v-card v-show="!movil || mostrandoFormulario" class="panel-formulario">
      <h2>{{ editando ? "Actualizar fotografía" : "Crear carné" }}</h2>
      <p class="texto-secundario tw:mb-4">
        {{
          editando
            ? "El UUID y el QR se conservan."
            : "El UUID se genera automáticamente."
        }}
      </p>
      <FormularioDatos
        ref="formulario"
        :key="version"
        :tipo="editando ? 'fotografia' : 'carne'"
        :campos="campos"
        :inicial="editando || {}"
        :bloquear-nombres="Boolean(editando)"
        :accion="guardar"
        :boton="editando ? 'Guardar fotografía' : 'Crear carné'"
      >
        <template #default="{ ocupado: guardando }"
          ><v-btn
            v-if="editando"
            variant="text"
            :disabled="guardando"
            @click="
              editar();
              mostrandoFormulario = !movil;
            "
            >Cancelar</v-btn
          ></template
        >
      </FormularioDatos>
    </v-card>
    <v-card v-show="!movil || !mostrandoFormulario" class="panel-lista">
      <div class="cabecera-panel">
        <h2>Carnés registrados</h2>
        <v-btn
          :icon="mdiRefresh"
          size="small"
          variant="text"
          aria-label="Actualizar carnés"
          :disabled="ocupado"
          @click="cargar"
        />
      </div>
      <v-text-field
        v-model="busqueda"
        label="Buscar por nombre o UUID"
        maxlength="100"
        clearable
        class="tw:mb-3"
      />
      <TablaRegistros
        :columnas="columnas"
        :cargando="ocupado"
        :filas="
          personas.filter((p) =>
            `${p.nombres} ${p.apellidos} ${p.uuid}`
              .toLocaleLowerCase()
              .includes((busqueda || '').toLocaleLowerCase()),
          )
        "
        clave="uuid"
      >
        <template #persona="{ fila }"
          ><strong>{{ fila.nombres }} {{ fila.apellidos }}</strong
          ><small class="uuid">{{ fila.uuid }}</small></template
        >
        <template #activo="{ fila }"
          ><v-chip size="small" :color="fila.activo ? 'primary' : 'default'">{{
            fila.activo ? "Activo" : "Inactivo"
          }}</v-chip></template
        >
        <template #acciones="{ fila }"
          ><div class="acciones-fila">
            <v-btn
              size="small"
              variant="text"
              color="primary"
              :href="`/carne.html?uuid=${fila.uuid}`"
              target="_blank"
              rel="noopener"
              >Ver carné</v-btn
            >
            <v-btn
              size="small"
              variant="text"
              :disabled="formulario?.ocupado"
              @click="editar(fila)"
              >Editar foto</v-btn
            >
            <v-btn
              size="small"
              variant="text"
              :disabled="ocupado"
              @click="alternar(fila)"
              >{{ fila.activo ? "Desactivar" : "Activar" }}</v-btn
            >
          </div></template
        >
      </TablaRegistros>
    </v-card>
  </div>
</template>
