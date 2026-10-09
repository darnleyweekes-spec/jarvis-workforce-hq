#!/usr/bin/env bash
# Run on an Ubuntu/Debian Compute Engine VM from the checked-out repository root.
# Never opens the API to the public internet.
set -Eeuo pipefail

cd "$(dirname "$0")/.."
[[ -f alpha-runtime/Dockerfile && -f alpha-runtime/api_server.py ]] || { echo "Run from an ALPHA repository checkout" >&2; exit 1; }

if [[ "${EUID}" -ne 0 ]]; then
  echo "Run: sudo bash alpha-runtime/deploy_gce.sh" >&2
  exit 1
fi
command -v apt-get >/dev/null || { echo "Requires an apt-based Linux VM" >&2; exit 1; }
export DEBIAN_FRONTEND=noninteractive
if ! command -v docker >/dev/null; then
  apt-get update
  apt-get install -y docker.io
fi
systemctl enable --now docker

install -d -m 700 /etc/alpha-operator
if [[ ! -f /etc/alpha-operator/runtime.env ]]; then
  command -v python3 >/dev/null || { apt-get update; apt-get install -y python3; }
  token="$(python3 -c 'import secrets; print(secrets.token_urlsafe(48))')"
  (umask 077; printf 'ALPHA_API_TOKEN=%s\n' "$token" > /etc/alpha-operator/runtime.env)
  unset token
fi
chmod 600 /etc/alpha-operator/runtime.env
chown root:root /etc/alpha-operator/runtime.env

docker build -f alpha-runtime/Dockerfile -t prime24ai-alpha-operator:local .
docker volume inspect alpha_data >/dev/null 2>&1 || docker volume create alpha_data >/dev/null

# Container image runs as UID 10001. Ensure the persistent Docker volume is writable.
docker run --rm --user 0:0 --mount source=alpha_data,target=/data \
  --entrypoint /bin/sh prime24ai-alpha-operator:local -c 'chown 10001:10001 /data && chmod 700 /data'

# Preserve the existing running container if the replacement cannot start.
if docker container inspect alpha-operator >/dev/null 2>&1; then
  docker rename alpha-operator alpha-operator-previous
  docker stop alpha-operator-previous >/dev/null
fi
if ! docker run -d --name alpha-operator --restart unless-stopped \
  --env-file /etc/alpha-operator/runtime.env \
  --env ALPHA_BIND=0.0.0.0 --env ALPHA_PORT=8080 --env ALPHA_DB_PATH=/data/alpha.sqlite3 \
  --publish 127.0.0.1:8080:8080 \
  --mount source=alpha_data,target=/data \
  --read-only --tmpfs /tmp:rw,noexec,nosuid,size=16m \
  --security-opt no-new-privileges --cap-drop ALL --pids-limit 64 --memory 512m \
  prime24ai-alpha-operator:local; then
  docker rm -f alpha-operator >/dev/null 2>&1 || true
  if docker container inspect alpha-operator-previous >/dev/null 2>&1; then
    docker rename alpha-operator-previous alpha-operator
    docker start alpha-operator >/dev/null
  fi
  exit 1
fi

ok=0
for i in $(seq 1 20); do
  if python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/healthz', timeout=2)" >/dev/null 2>&1; then
    ok=1; break
  fi
  sleep 1
done
if [[ "$ok" != 1 ]]; then
  echo "Health check failed; inspect: sudo docker logs alpha-operator" >&2
  docker rm -f alpha-operator >/dev/null 2>&1 || true
  if docker container inspect alpha-operator-previous >/dev/null 2>&1; then
    docker rename alpha-operator-previous alpha-operator
    docker start alpha-operator >/dev/null
  fi
  exit 1
fi
docker rm -f alpha-operator-previous >/dev/null 2>&1 || true
echo "ALPHA running. API bound to VM localhost only. SSH tunnel required."
echo "Health: http://127.0.0.1:8080/healthz"
