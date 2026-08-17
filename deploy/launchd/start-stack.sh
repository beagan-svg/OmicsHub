#!/bin/bash
# Bring the compose stack up, once, at login. Run by the LaunchAgent beside this file.
#
# The waiting is the whole reason this is a script rather than a plist calling `docker`
# directly. At login launchd starts agents immediately, while Docker Desktop is still
# coming up, so `docker compose` would fail on a socket that is not listening yet and the
# stack would silently never start.
set -euo pipefail

# launchd gives an agent a minimal PATH that has none of these.
export PATH="/usr/local/bin:/opt/homebrew/bin:/Applications/Docker.app/Contents/Resources/bin:$PATH"

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO"

log() { printf '%s %s\n' "$(date -u '+%Y-%m-%dT%H:%M:%SZ')" "$*"; }

# Docker Desktop takes tens of seconds from login. Bounded so a machine without it
# installed fails visibly in the log rather than looping forever.
for _ in $(seq 1 60); do
    if docker info >/dev/null 2>&1; then
        break
    fi
    sleep 5
done

if ! docker info >/dev/null 2>&1; then
    log "docker is not responding after 5 minutes; not starting the stack"
    exit 1
fi

# --wait blocks until the healthchecks pass, so the log line below reports what actually
# happened rather than what was asked for. No --wait-timeout: compose v2.3, which is what
# is installed here, does not have that flag, and rejects the whole command. Check this with
# running this script rather than assumed.
log "starting the stack"
if docker compose --env-file .env.docker up -d --wait; then
    log "stack is up"
else
    log "stack did not come up healthy; see: docker compose --env-file .env.docker ps"
    exit 1
fi
