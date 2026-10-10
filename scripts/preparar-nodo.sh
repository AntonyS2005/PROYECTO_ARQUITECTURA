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
apt-get install -y ca-certificates chrony iproute2
if [[ "$rol" == master ]]; then
  apt-get install -y curl xz-utils
else
  apt-get install -y python3 python3-venv
fi

if [[ "$rol" == master ]]; then
  if command -v node >/dev/null && command -v npm >/dev/null && \
    node -e 'if(Number(process.versions.node.split(".")[0])<24)process.exit(1)'; then
    printf 'Se conserva Node.js existente: %s\n' "$(node --version)"
  else
    [[ "$(uname -m)" == aarch64 ]] || fallar 'La instalación automática de Node está preparada para la Raspberry ARM64.'
    for ejecutable in node npm npx; do
      [[ ! -e "/usr/local/bin/$ejecutable" && ! -L "/usr/local/bin/$ejecutable" ]] || \
        fallar "Ya existe /usr/local/bin/$ejecutable. Instale Node.js 24 sin reemplazarlo automáticamente."
    done
    entorno_node=/opt/node-v24.21.0-linux-arm64
    [[ ! -e "$entorno_node" ]] || fallar 'Ya existe el directorio del runtime. Revisar la instalación anterior.'
    temporal=$(mktemp -d)
    trap 'rm -f -- "$temporal/node.tar.xz"; rmdir -- "$temporal"' EXIT
    curl --fail --location --proto '=https' --tlsv1.2 \
      https://nodejs.org/dist/v24.21.0/node-v24.21.0-linux-arm64.tar.xz \
      --output "$temporal/node.tar.xz"
    printf '6ad1325edbdb5649c379b75a237147a666c95d4f9ae8d340fef2d1575d289ad2  %s\n' \
      "$temporal/node.tar.xz" | sha256sum --check --status || fallar 'La descarga de Node no pasó la comprobación SHA-256.'
    install -d -m 0755 "$entorno_node"
    tar --extract --xz --file "$temporal/node.tar.xz" --directory "$entorno_node" \
      --strip-components=1 --no-same-owner
    for ejecutable in node npm npx; do
      ln -s "$entorno_node/bin/$ejecutable" "/usr/local/bin/$ejecutable"
    done
    export PATH="/usr/local/bin:$PATH"
    hash -r
    node --version
  fi
fi

bash scripts/instalar-linux.sh "$rol"

if [[ -f /etc/chrony/chrony.conf && ! -e /etc/chrony/chrony.conf.before-edge ]]; then
  cp -p /etc/chrony/chrony.conf /etc/chrony/chrony.conf.before-edge
fi
install -m 0644 "deploy/chrony-$reloj.conf.example" /etc/chrony/chrony.conf
systemctl enable chrony
systemctl restart chrony
printf '\nPreparación terminada para %s. El servicio arrancará también al encender el nodo.\n' "$rol"
printf 'Abra http://localhost:3000 en la Raspberry y compruebe el estado de los nodos.\n'
