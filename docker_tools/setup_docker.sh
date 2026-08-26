#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="$ROOT_DIR/.env.docker"
EXAMPLE_FILE="$ROOT_DIR/.env.docker.example"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
    echo "Docker is required. Install Docker Desktop or Docker Engine, then run this command again." >&2
    exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose is required. Install the Docker Compose plugin, then run this command again." >&2
    exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
    cp "$EXAMPLE_FILE" "$ENV_FILE"
    chmod 600 "$ENV_FILE"
    echo "Created .env.docker from .env.docker.example."
    echo "Fill in SECRET_KEY, POSTGRES_PASSWORD, CREDENTIAL_ENCRYPTION_KEY, and AWS_CREDENTIALS_FILE, then run this command again."
    exit 1
fi

chmod 600 "$ENV_FILE"

read_env_value() {
    key=$1
    awk -F= -v key="$key" '$1 == key {sub(/^[^=]*=/, ""); print; exit}' "$ENV_FILE"
}

credentials_file=$(read_env_value AWS_CREDENTIALS_FILE)
aws_profile=$(read_env_value AWS_PROFILE)
web_port=$(read_env_value WEB_PORT)
web_port=${web_port:-8000}

require_env_value() {
    key=$1
    value=$(read_env_value "$key")
    if [ -z "$value" ]; then
        echo "$key is required in .env.docker." >&2
        exit 1
    fi
}

require_env_value SECRET_KEY
require_env_value POSTGRES_PASSWORD
require_env_value CREDENTIAL_ENCRYPTION_KEY

credential_encryption_key=$(read_env_value CREDENTIAL_ENCRYPTION_KEY)
if ! printf '%s\n' "$credential_encryption_key" | awk 'length($0) == 44 && $0 ~ /^[A-Za-z0-9_-]+=$/ { valid = 1 } END { exit !valid }'; then
    echo "CREDENTIAL_ENCRYPTION_KEY must be a Fernet key." >&2
    echo "Generate one with: docker run --rm python:3.12-slim python -c 'import base64,secrets; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'" >&2
    exit 1
fi

if [ -z "${credentials_file:-}" ]; then
    echo "AWS_CREDENTIALS_FILE is required in .env.docker." >&2
    exit 1
fi

if [ ! -f "$credentials_file" ]; then
    echo "AWS credentials file not found: $credentials_file" >&2
    echo "Create an app-scoped credentials file and set its path in .env.docker." >&2
    exit 1
fi

if [ ! -r "$credentials_file" ]; then
    echo "AWS credentials file is not readable: $credentials_file" >&2
    exit 1
fi

if [ -z "${aws_profile:-}" ]; then
    echo "AWS_PROFILE is required in .env.docker." >&2
    exit 1
fi

if ! command -v git >/dev/null 2>&1; then
    echo "Git is required to prepare the OCS packages." >&2
    exit 1
fi

echo "Preparing the OCS CLI packages for the Docker build."
docker_tools/vendor_gcs.sh

docker compose --env-file "$ENV_FILE" config --quiet
docker compose --env-file "$ENV_FILE" up -d --build --wait

echo "OmicsHub is running at http://127.0.0.1:$web_port"
echo "Use 'docker compose --env-file .env.docker logs -f web-ui' to view web UI logs."
