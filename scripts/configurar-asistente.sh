#!/usr/bin/env bash
set -euo pipefail
fallar() { printf '%s\n' "$1" >&2; exit 1; }
modo=${1:-}
case "$modo" in text|voice|off) ;; *) fallar 'Uso: sudo bash scripts/configurar-asistente.sh text|voice|off' ;; esac
[[ "$EUID" -eq 0 && "$(uname -s)" == Linux ]] || fallar 'Ejecute con sudo en la Raspberry.'
directorio_raiz=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ "$directorio_raiz" == /opt/edge-access && -f /etc/edge-access/master.env ]] || fallar 'Instale primero el nodo master en /opt/edge-access.'
cd -- "$directorio_raiz"

establecer_opcion() {
  local clave=$1 valor=$2 linea temporal
  temporal=$(mktemp /etc/edge-access/master.env.XXXXXX)
  while IFS= read -r linea || [[ -n "$linea" ]]; do
    [[ "$linea" == "$clave="* ]] || printf '%s\n' "$linea"
  done < /etc/edge-access/master.env > "$temporal"
  printf '%s=%s\n' "$clave" "$valor" >> "$temporal"
  chmod 600 "$temporal"
  mv -- "$temporal" /etc/edge-access/master.env
}

if [[ "$modo" == voice ]]; then
  apt-get update
  apt-get install -y python3-venv
  python3 -m venv backend/modulos/asistente/.venv
  backend/modulos/asistente/.venv/bin/python -m pip install -r backend/modulos/asistente/requirements.txt
  python3 scripts/descargar-voz.py
  python3 - <<'PY'
import hashlib, json, pathlib, zipfile
directorio_raiz = pathlib.Path("backend/modulos/asistente")
manifiesto = json.loads((directorio_raiz / "modelo.json").read_text())
paquete = directorio_raiz / "modelos" / (manifiesto["nombre"] + ".zip")
contenido_original = paquete.read_bytes()
if len(contenido_original) != manifiesto["bytes"] or hashlib.sha256(contenido_original).hexdigest() != manifiesto["sha256"]:
    raise SystemExit("Modelo de voz no válido.")
destino = (directorio_raiz / "modelos").resolve()
with zipfile.ZipFile(paquete) as origen:
    for nombre in origen.namelist():
        if not (destino / nombre).resolve().is_relative_to(destino):
            raise SystemExit("Ruta no válida en el modelo.")
    origen.extractall(destino)
PY
  clave_voz=''
  if [[ -f /etc/edge-access/voice.env ]]; then
    while IFS= read -r linea; do
      [[ "$linea" == CLAVE_VOZ=* ]] && clave_voz=${linea#CLAVE_VOZ=}
    done < /etc/edge-access/voice.env
  fi
  if [[ -z "$clave_voz" ]]; then clave_voz=$(python3 -c 'import secrets;print(secrets.token_hex(32))'); fi
  [[ "$clave_voz" =~ ^[0-9a-fA-F]{64}$ ]] || fallar 'CLAVE_VOZ existente no válida.'
  (
    umask 077
    printf 'CLAVE_VOZ=%s\nDIRECTORIO_MODELO_VOZ=/opt/edge-access/backend/modulos/asistente/modelos/vosk-model-small-es-0.42\n' "$clave_voz" > /etc/edge-access/voice.env
  )
  chmod 600 /etc/edge-access/voice.env
  establecer_opcion CLAVE_VOZ "$clave_voz"
  unset clave_voz
  install -m 0644 deploy/edge-voice.service /etc/systemd/system/edge-voice.service
  systemctl daemon-reload
  systemctl enable edge-voice
  systemctl restart edge-voice
else
  if [[ -f /etc/systemd/system/edge-voice.service ]]; then systemctl disable --now edge-voice; fi
fi
if [[ "$modo" == off ]]; then establecer_opcion ASISTENTE_HABILITADO false; else establecer_opcion ASISTENTE_HABILITADO true; fi
if [[ "$modo" == voice ]]; then establecer_opcion VOZ_HABILITADA true; else establecer_opcion VOZ_HABILITADA false; fi
systemctl restart edge-master
printf 'Modo de asistente configurado: %s. Inicie sesión nuevamente y compruebe su funcionamiento.\n' "$modo"
