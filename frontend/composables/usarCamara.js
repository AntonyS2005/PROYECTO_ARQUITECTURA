import { onScopeDispose, ref } from "vue";
import { validar } from "../../public/validaciones.js";
import { api } from "../servicios/api.js";
import { crearCaptura } from "../servicios/imagenes.js";

const indicaciones = {
  QR_NO_LEIBLE: "Acerque el carné. Mantenga el QR completo y nítido.",
  ROSTRO_NO_DETECTADO:
    "Coloque el rostro de frente, completo y con buena iluminación.",
  VARIOS_ROSTROS: "Debe aparecer una sola persona en el área del rostro.",
};
const erroresCamara = {
  NotAllowedError: "Permita el uso de la cámara en el navegador.",
  NotFoundError: "No se encontró una cámara conectada.",
  NotReadableError:
    "La cámara está ocupada. Cierre otras aplicaciones que la utilicen.",
};

export function usarCamara(video, alRegistrar) {
  const activa = ref(false);
  const buscando = ref(false);
  const enviando = ref(false);
  const segundos = ref(45);
  const proporcion = ref("16 / 9");
  const resultado = ref(null);
  const titulo = ref("En espera");
  const indicacion = ref(
    "Active la cámara y coloque el rostro y el carné en sus áreas.",
  );
  const fallo = ref(false);
  let flujo;
  let captura;
  let secuencia = 0;

  function detener() {
    secuencia++;
    captura?.cerrar();
    captura = null;
    flujo?.getTracks().forEach((pista) => pista.stop());
    flujo = null;
    if (video.value) video.value.srcObject = null;
    activa.value = false;
    buscando.value = false;
    enviando.value = false;
  }

  function cancelar() {
    if (enviando.value) return;
    detener();
    titulo.value = "Captura cancelada";
    indicacion.value = "Active la cámara para volver a intentar.";
  }

  async function iniciar() {
    if (buscando.value) return;
    const turno = ++secuencia;
    buscando.value = true;
    fallo.value = false;
    resultado.value = null;
    titulo.value = "Buscando carné y rostro";
    indicacion.value = "Rostro a la izquierda y carné a la derecha.";
    segundos.value = 45;
    try {
      if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Abra la aplicación mediante HTTPS para utilizar la cámara.",
        );
      const nuevoFlujo = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 1920 },
          height: { ideal: 1080 },
          frameRate: { ideal: 15, max: 20 },
        },
        audio: false,
      });
      if (turno !== secuencia) {
        nuevoFlujo.getTracks().forEach((pista) => pista.stop());
        return;
      }
      flujo = nuevoFlujo;
      video.value.srcObject = flujo;
      await video.value.play();
      if (turno !== secuencia) return;
      proporcion.value = `${video.value.videoWidth} / ${video.value.videoHeight}`;
      activa.value = true;
      captura = crearCaptura();
      const limite = Date.now() + 45000;
      while (Date.now() < limite && turno === secuencia) {
        segundos.value = Math.ceil((limite - Date.now()) / 1000);
        const fotografias = captura.obtener(video.value);
        if (turno !== secuencia) return;
        const errores = validar("acceso", fotografias);
        if (Object.keys(errores).length)
          throw new Error(Object.values(errores)[0]);
        try {
          enviando.value = true;
          const respuesta = await api("/accesos", {
            method: "POST",
            body: fotografias,
          });
          if (turno !== secuencia) return;
          resultado.value = respuesta.evento;
          titulo.value = respuesta.mensaje;
          fallo.value = respuesta.evento.estado === "RECHAZADO";
          indicacion.value = `${respuesta.evento.nombres} ${respuesta.evento.apellidos}`;
          alRegistrar();
          return;
        } catch (error) {
          if (turno !== secuencia) return;
          if (error.status !== 422 || !indicaciones[error.codigo]) throw error;
          indicacion.value = indicaciones[error.codigo];
        } finally {
          enviando.value = false;
        }
        await new Promise((resolver) => setTimeout(resolver, 400));
      }
      if (turno === secuencia)
        throw new Error(
          "Tiempo de captura agotado. Vuelva a activar la cámara.",
        );
    } catch (error) {
      if (turno !== secuencia) return;
      titulo.value = "Acceso no registrado";
      indicacion.value = erroresCamara[error.name] || error.message;
      fallo.value = true;
    } finally {
      if (turno === secuencia) detener();
    }
  }

  onScopeDispose(detener);
  return {
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
  };
}
