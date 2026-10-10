export async function grabarComando(senal) {
  let flujo, contextoAudio, temporizador;
  const fragmentos = [];
  try {
    flujo = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true },
      video: false,
    });
    if (senal.aborted) throw new DOMException("Cancelado", "AbortError");
    contextoAudio = new AudioContext();
    await contextoAudio.audioWorklet.addModule("/asistente/captura-audio.js");
    if (senal.aborted) throw new DOMException("Cancelado", "AbortError");
    const origen = contextoAudio.createMediaStreamSource(flujo);
    const grabador = new AudioWorkletNode(contextoAudio, "captura-pcm");
    const silencio = contextoAudio.createGain();
    silencio.gain.value = 0;
    let cantidad = 0;
    grabador.port.onmessage = ({ data: datos }) => {
      if (cantidad + datos.length <= contextoAudio.sampleRate * 6) {
        fragmentos.push(datos);
        cantidad += datos.length;
      }
    };
    origen
      .connect(grabador)
      .connect(silencio)
      .connect(contextoAudio.destination);
    await contextoAudio.resume();
    await new Promise((resolver, rechazar) => {
      const cancelar = () => {
        clearTimeout(temporizador);
        rechazar(new DOMException("Cancelado", "AbortError"));
      };
      senal.addEventListener("abort", cancelar, { once: true });
      temporizador = setTimeout(() => {
        senal.removeEventListener("abort", cancelar);
        resolver();
      }, 5000);
      if (senal.aborted) cancelar();
    });
    grabador.port.onmessage = null;
    const entrada = new Float32Array(cantidad);
    let posicion = 0;
    for (const fragmento of fragmentos) {
      entrada.set(fragmento, posicion);
      posicion += fragmento.length;
    }
    const proporcion = contextoAudio.sampleRate / 16000;
    const salida = new DataView(
      new ArrayBuffer(Math.floor(cantidad / proporcion) * 2),
    );
    for (let i = 0; i < salida.byteLength / 2; i++) {
      const desde = Math.floor(i * proporcion),
        hasta = Math.max(desde + 1, Math.floor((i + 1) * proporcion));
      let suma = 0;
      for (let j = desde; j < hasta && j < cantidad; j++) suma += entrada[j];
      const valor = Math.max(-1, Math.min(1, suma / (hasta - desde)));
      salida.setInt16(
        i * 2,
        Math.round(valor * (valor < 0 ? 32768 : 32767)),
        true,
      );
    }
    const bytes = new Uint8Array(salida.buffer);
    let binario = "";
    for (const byte of bytes) binario += String.fromCharCode(byte);
    return btoa(binario);
  } finally {
    clearTimeout(temporizador);
    flujo?.getTracks().forEach((pista) => pista.stop());
    if (contextoAudio) await contextoAudio.close();
  }
}
