#!/usr/bin/env bash
set -euo pipefail

fallar() { printf '%s\n' "$1" >&2; exit 1; }
rol="${1:-}"
case "$rol" in
  master) ip_esperada=192.168.50.10; servicio=edge-master; configuracion=master ;;
  worker-01) ip_esperada=192.168.50.11; servicio=edge-worker; configuracion=worker ;;
  worker-02) ip_esperada=192.168.50.12; servicio=edge-worker; configuracion=worker ;;
  *) fallar 'Uso: sudo bash scripts/instalar-linux.sh master|worker-01|worker-02' ;;
esac
[[ "$EUID" -eq 0 ]] || fallar 'Ejecute el instalador con sudo sobre el nodo de destino.'
[[ "$(uname -s)" == Linux && "$(getconf LONG_BIT)" == 64 ]] || fallar 'Se requiere Linux de 64 bits.'
directorio_proyecto="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)"
[[ "$directorio_proyecto" == /opt/edge-access ]] || fallar 'Extraiga primero el paquete en /opt/edge-access.'
cd -- "$directorio_proyecto"
command -v systemctl >/dev/null || fallar 'Se requiere systemd.'
command -v ip >/dev/null || fallar 'Se requiere iproute2.'
asignada=false
while read -r direccion; do
  [[ "$direccion" == "$ip_esperada/24" ]] && asignada=true
done < <(ip -o -4 address show | awk '{print $4}')
[[ "$asignada" == true ]] || fallar "Configure primero $ip_esperada/24 en el nodo. No se modificó la red."

command -v python3 >/dev/null || fallar 'Instale Python 3.12 y python3-venv antes de continuar.'
python3 -c 'import sys;sys.exit(0 if sys.version_info >= (3,10) else 1)' || fallar 'Python debe ser 3.10 o posterior; se recomienda 3.12.'
command -v chronyc >/dev/null || fallar 'Ejecute primero scripts/preparar-nodo.sh para configurar la hora.'
install -d -m 0750 /etc/edge-access
archivo_entorno="/etc/edge-access/$configuracion.env"
if [[ ! -e "$archivo_entorno" ]]; then
  read -r -s -p 'Clave CLAVE_NODOS compartida (64 caracteres hexadecimales): ' clave_nodos
  printf '\n'
  [[ "$clave_nodos" =~ ^[0-9a-fA-F]{64}$ ]] || fallar 'La clave debe tener 64 caracteres hexadecimales.'
  plantilla="deploy/$rol.env.example"
  (
    umask 077
    while IFS= read -r linea || [[ -n "$linea" ]]; do
      if [[ "$linea" == CLAVE_NODOS=* ]]; then printf 'CLAVE_NODOS=%s\n' "$clave_nodos"
      else printf '%s\n' "$linea"; fi
    done < "$plantilla" > "$archivo_entorno"
  )
  unset clave_nodos
fi
chmod 600 "$archivo_entorno"
chown root:root "$archivo_entorno"
id -u edge >/dev/null 2>&1 || useradd --system --user-group --home-dir /opt/edge-access --shell /usr/sbin/nologin edge

if [[ "$rol" == master ]]; then
  install -d -m 0750 -o edge -g edge data
  python3 -m venv backend/.venv
  backend/.venv/bin/python -m pip install -r backend/requirements.txt
  if [[ -f data/access.sqlite ]] && runuser -u edge -- backend/.venv/bin/python -c '
from backend.repositorios.conexion import abrir_base_datos
base_datos=abrir_base_datos("data/access.sqlite")
encontrado=base_datos.execute("SELECT id FROM usuarios LIMIT 1").fetchone()
base_datos.close()
raise SystemExit(0 if encontrado else 1)
  ' 2>/dev/null; then
    printf 'Se conservan las cuentas existentes.\n'
  else
    read -r -s -p 'Contraseña inicial de administración: ' CLAVE_ADMIN
    printf '\n'
    export CLAVE_ADMIN
    runuser -u edge --preserve-environment -- backend/.venv/bin/python -m backend.configurar_admin
    unset CLAVE_ADMIN
  fi
else
  python3 -m venv worker/.venv
  worker/.venv/bin/python -m pip uninstall -y opencv-python-headless
  worker/.venv/bin/python -m pip install -r worker/requirements.txt
  worker/.venv/bin/python -c '
import hashlib,json,pathlib
directorio_raiz=pathlib.Path("worker")
for modelo in json.loads((directorio_raiz/"modelos.json").read_text())["modelos"]:
    contenido_original=(directorio_raiz/"modelos"/modelo["archivo"]).read_bytes()
    if len(contenido_original)!=modelo["bytes"] or hashlib.sha256(contenido_original).hexdigest()!=modelo["sha256"]:
        raise SystemExit("Modelo ausente o con integridad no válida.")
print("Modelos verificados; todavía no se ha probado inferencia.")
'
fi

install -m 0644 "deploy/$servicio.service" "/etc/systemd/system/$servicio.service"
systemctl daemon-reload
systemctl enable "$servicio"
systemctl restart "$servicio"
printf 'Servicio configurado: %s. Consultar: systemctl status %s --no-pager\n' "$servicio" "$servicio"
