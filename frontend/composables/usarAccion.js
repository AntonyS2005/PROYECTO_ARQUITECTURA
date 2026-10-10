import { ref } from "vue";

export function usarAccion() {
  const ocupado = ref(false);
  const aviso = ref("");
  const fallo = ref(false);

  async function ejecutar(accion) {
    if (ocupado.value) return;
    ocupado.value = true;
    aviso.value = "";
    fallo.value = false;
    try {
      const resultado = await accion();
      if (resultado?.mensaje) aviso.value = resultado.mensaje;
      return resultado;
    } catch (error) {
      aviso.value = error.message;
      fallo.value = true;
    } finally {
      ocupado.value = false;
    }
  }

  return { ocupado, aviso, fallo, ejecutar };
}
