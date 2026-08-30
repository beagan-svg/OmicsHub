#!/bin/sh
set -eu

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TEST_DATABASE_CONTAINER="omicshub-test-postgres"
TEST_DATABASE_PORT="${TEST_DATABASE_PORT:-55432}"

cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1 || ! docker info >/dev/null 2>&1; then
    echo "Docker is required and must be running." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required. Install it from https://docs.astral.sh/uv/, then run this command again." >&2
    exit 1
fi

if docker container inspect "$TEST_DATABASE_CONTAINER" >/dev/null 2>&1; then
    echo "A container named $TEST_DATABASE_CONTAINER already exists. Stop it before running tests." >&2
    exit 1
fi

cleanup() {
    docker stop "$TEST_DATABASE_CONTAINER" >/dev/null 2>&1 || true
}
trap cleanup EXIT INT TERM

uv sync --frozen --group dev
uv run --group dev playwright install chromium

docker run --detach --rm \
    --name "$TEST_DATABASE_CONTAINER" \
    --env POSTGRES_USER=omicshub \
    --env POSTGRES_PASSWORD=omicshub \
    --env POSTGRES_DB=omicshub \
    --publish "127.0.0.1:${TEST_DATABASE_PORT}:5432" \
    postgres:16 >/dev/null

attempt=0
until docker exec "$TEST_DATABASE_CONTAINER" pg_isready --username omicshub --dbname omicshub >/dev/null 2>&1; do
    attempt=$((attempt + 1))
    if [ "$attempt" -ge 30 ]; then
        echo "The PostgreSQL test database did not become ready." >&2
        exit 1
    fi
    sleep 1
done

export DATABASE_URL="postgres://omicshub:omicshub@127.0.0.1:${TEST_DATABASE_PORT}/omicshub"
export DJANGO_SETTINGS_MODULE="omicshub.settings.test"

uv run --group dev python -m pytest -q --ignore=apps/web_ui/tests/playwright
DJANGO_ALLOW_ASYNC_UNSAFE=true uv run --group dev python -m pytest -q apps/web_ui/tests/playwright
