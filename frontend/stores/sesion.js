import { computed, ref } from "vue";
import { defineStore } from "pinia";
import { api } from "../servicios/api.js";

export const usarSesion = defineStore("sesion", () => {
  const cuenta = ref(null);
  const modulos = ref({});
  const preparada = ref(false);
  const mensaje = ref("");
  const administrador = computed(() => cuenta.value?.rol === "ADMINISTRADOR");
  let minutosInactividad = 15;
  let temporizador;
  let ultimaRenovacion = 0;

  function finalizar(texto = "Sesión finalizada.") {
    clearTimeout(temporizador);
    cuenta.value = null;
    modulos.value = {};
    mensaje.value = texto;
  }

  function actividad() {
    if (!cuenta.value) return;
    clearTimeout(temporizador);
    temporizador = setTimeout(async () => {
      await cerrar();
      finalizar("Sesión finalizada por inactividad.");
    }, minutosInactividad * 60000);
    if (Date.now() - ultimaRenovacion > 60000) {
      ultimaRenovacion = Date.now();
      api("/me").catch(() => {});
    }
  }

  function establecer(datos) {
    cuenta.value = datos.cuenta;
    modulos.value = datos.modulos || {};
    minutosInactividad = datos.minutosInactividad;
    ultimaRenovacion = Date.now();
    mensaje.value = "";
    actividad();
  }

  async function recuperar() {
    try {
      establecer(await api("/me"));
    } catch (error) {
      if (error.status !== 401) mensaje.value = error.message;
    } finally {
      preparada.value = true;
    }
  }

  async function ingresar(valores) {
    establecer(await api("/login", { method: "POST", body: valores }));
  }

  async function cerrar(texto = "Sesión finalizada.") {
    try {
      await api("/logout", { method: "POST", body: {} });
      finalizar(texto);
    } catch (error) {
      mensaje.value = error.message;
    }
  }

  return {
    cuenta,
    modulos,
    preparada,
    mensaje,
    administrador,
    recuperar,
    ingresar,
    cerrar,
    finalizar,
    actividad,
  };
});
