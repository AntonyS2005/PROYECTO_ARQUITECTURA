class ProcesadorCaptura extends AudioWorkletProcessor {
  process(entradas) {
    const muestras = entradas[0]?.[0];
    if (muestras) this.port.postMessage(muestras.slice());
    return true;
  }
}
registerProcessor("captura-pcm", ProcesadorCaptura);
