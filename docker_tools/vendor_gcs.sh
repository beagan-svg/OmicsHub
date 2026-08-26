#!/bin/sh
set -eu

ROOT_DIR=$(CDPATH='' cd -- "$(dirname -- "$0")/.." && pwd)
DEST="$ROOT_DIR/vendor/gcs"
GCS_REPOSITORY_URL=https://github.com/AllenInstitute/genomics-cloud-services.git
GCS_REVISION=3406beb0fab426ac1eacdefc8feb411249f849e5
PACKAGES="gcs-core gcs-api-client gcs-docker-tools gcs-cli"

work_dir=$(mktemp -d)
cleanup() {
    find "$work_dir" -depth -delete
}
trap cleanup EXIT HUP INT TERM

if [ -n "${GCS_SRC:-}" ]; then
    source_dir=$GCS_SRC
    if ! git -C "$source_dir" cat-file -e "$GCS_REVISION^{commit}" 2>/dev/null; then
        echo "GCS revision $GCS_REVISION is not available in $source_dir." >&2
        exit 1
    fi
else
    source_dir=$work_dir/source
    mkdir "$source_dir"
    git -C "$source_dir" init --quiet
    git -C "$source_dir" remote add origin "$GCS_REPOSITORY_URL"
    git -C "$source_dir" fetch --quiet --depth 1 origin "$GCS_REVISION"
fi

archive_dir=$work_dir/archive
mkdir "$archive_dir"
git -C "$source_dir" archive "$GCS_REVISION" $PACKAGES | tar -x -C "$archive_dir"

if [ -d "$DEST" ]; then
    find "$DEST" -depth -delete
fi
mkdir -p "$DEST"
for package in $PACKAGES; do
    mv "$archive_dir/$package" "$DEST/$package"
done

printf '%s\n' "$GCS_REVISION" > "$DEST/REVISION"
echo "Prepared GCS revision $GCS_REVISION in vendor/gcs."
