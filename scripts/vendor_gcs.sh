#!/bin/sh
# Copy the genomics-cloud-services packages the `ocs` CLI is built from into vendor/gcs/.
#
# They live outside this repo, and a Docker build can only read files inside its own build
# context, so they have to be brought in before `docker compose build`. This is the step
# that becomes a git submodule once the repo is under version control; the Dockerfile reads
# vendor/gcs/ either way and will not need changing.
#
# Point GCS_SRC at the checkout if it is not in the default place:
#
#     GCS_SRC=/path/to/genomics-cloud-services scripts/vendor_gcs.sh
set -eu

GCS_SRC="${GCS_SRC:-$HOME/Desktop/ocs_assets/genomics-cloud-services}"
DEST="$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)/vendor/gcs"

# gcs-cli depends on the other three by name, so all four have to be present for pip to
# resolve the install without reaching for an index that does not carry them.
PACKAGES="gcs-core gcs-api-client gcs-docker-tools gcs-cli"

for package in $PACKAGES; do
    if [ ! -f "$GCS_SRC/$package/pyproject.toml" ]; then
        echo "No $package at $GCS_SRC. Set GCS_SRC to the genomics-cloud-services checkout." >&2
        exit 1
    fi
done

mkdir -p "$DEST"
for package in $PACKAGES; do
    # --delete so a package removed upstream does not linger in a stale vendored copy.
    # The excludes are things pip does not read. user_documentation is 63MB of screenshots
    # on its own, and every byte here is uploaded to the Docker daemon on each build.
    # --delete-excluded as well as --delete: without it rsync protects excluded paths that
    # already exist in the destination, so widening the exclude list would never take effect.
    rsync -a --delete --delete-excluded \
        --exclude '.venv/' --exclude 'build/' --exclude 'test/' --exclude '__pycache__/' \
        --exclude '*.egg-info/' --exclude 'user_documentation/' --exclude 'docs/' \
        "$GCS_SRC/$package/" "$DEST/$package/"
done

echo "Vendored $PACKAGES from $GCS_SRC into vendor/gcs."
