#!/usr/bin/env sh
set -eu

ENV_FILE="${1:-deploy.env}"
COMPOSE_FILE="${2:-docker-compose.deploy.yml}"
TIMEOUT_SECONDS="${TIMEOUT_SECONDS:-180}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE" >&2
  exit 1
fi

if [ ! -f "$COMPOSE_FILE" ]; then
  echo "Missing compose file: $COMPOSE_FILE" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1090
. "$ENV_FILE"
set +a

compose() {
  docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
}

service_state() {
  container_id="$(compose ps -q "$1")"
  if [ -z "$container_id" ]; then
    echo "missing"
    return 0
  fi
  docker inspect --format='{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id"
}

wait_for_service() {
  service_name="$1"
  deadline=$(( $(date +%s) + TIMEOUT_SECONDS ))

  while [ "$(date +%s)" -lt "$deadline" ]; do
    current_state="$(service_state "$service_name")"
    case "$current_state" in
      healthy|running)
        echo "Service '$service_name' is $current_state."
        return 0
        ;;
      exited|dead)
        echo "Service '$service_name' entered terminal state: $current_state" >&2
        compose ps
        compose logs --no-color "$service_name" >&2 || true
        return 1
        ;;
    esac
    sleep 5
  done

  echo "Timed out waiting for service '$service_name'." >&2
  compose ps >&2
  compose logs --no-color "$service_name" >&2 || true
  return 1
}

wait_for_service db
wait_for_service api
wait_for_service web

compose exec -T api python scripts/seed.py

compose exec -T api python -c "from urllib.request import urlopen; response = urlopen('http://127.0.0.1:8000/api/v1/health', timeout=5); print(response.status)"
compose exec -T web wget -q -O - http://127.0.0.1/healthz
compose exec -T \
  -e BOOTSTRAP_WORKSPACE="$DEFAULT_WORKSPACE_PUBLIC_ID" \
  -e BOOTSTRAP_EMAIL="$DEFAULT_ADMIN_EMAIL" \
  -e BOOTSTRAP_PASSWORD="$DEFAULT_ADMIN_PASSWORD" \
  api \
  python -c "import json, os, urllib.request; payload = json.dumps({'workspace': os.environ['BOOTSTRAP_WORKSPACE'], 'email': os.environ['BOOTSTRAP_EMAIL'], 'password': os.environ['BOOTSTRAP_PASSWORD']}).encode(); request = urllib.request.Request('http://127.0.0.1:8000/api/v1/auth/login', data=payload, headers={'Content-Type': 'application/json'}); response = urllib.request.urlopen(request, timeout=5); print(response.status)"

compose ps
