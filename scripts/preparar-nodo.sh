#!/usr/bin/env bash
set -euo pipefail
fallar() { printf '%s\n' "$1" >&2; exit 1; }
rol=${1:-}
case "$rol" in
  master) reloj=master ;;
  worker-01|worker-02) reloj=worker ;;
  *) fallar 'Uso: sudo bash scripts/preparar-nodo.sh master|worker-01|worker-02' ;;
esac
[[ "$EUID" -eq 0 ]] || fallar 'Ejecute con sudo en el nodo de destino.'
[[ "$(uname -s)" == Linux && "$(getconf LONG_BIT)" == 64 ]] || fallar 'Se requiere Linux de 64 bits.'
directorio_raiz=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd -P)
[[ "$directorio_raiz" == /opt/edge-access ]] || fallar 'Extraiga el paquete primero en /opt/edge-access.'
command -v apt-get >/dev/null || fallar 'Se requiere Raspberry Pi OS o Ubuntu con apt-get.'
command -v systemctl >/dev/null || fallar 'Se requiere systemd.'
cd -- "$directorio_raiz"

apt-get update
apt-get install -y ca-certificates chrony iproute2 python3 python3-venv

bash scripts/instalar-linux.sh "$rol"

if [[ -f /etc/chrony/chrony.conf && ! -e /etc/chrony/chrony.conf.before-edge ]]; then
  cp -p /etc/chrony/chrony.conf /etc/chrony/chrony.conf.before-edge
fi
install -m 0644 "deploy/chrony-$reloj.conf.example" /etc/chrony/chrony.conf
systemctl enable chrony
systemctl restart chrony
printf '\nPreparación terminada para %s. El servicio arrancará también al encender el nodo.\n' "$rol"
printf 'Abra http://localhost:3000 en la Raspberry y compruebe el estado de los nodos.\n'
