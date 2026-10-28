#!/usr/bin/env bash
# Fetch Django and aiogram docs into docs/vendor/ for the coding agent.
# Keeps only plain-text docs (.rst/.md/.txt), drops everything else.
# Re-run any time to refresh. Run from anywhere; paths are relative to the project root
# (assumed to be the parent folder of the folder this script lives in, e.g. scripts/).

set -euo pipefail

# ---- config -----------------------------------------------------------------
DJANGO_REPO="https://github.com/django/django.git"
DJANGO_REF="stable/5.2.x"

AIOGRAM_REPO="https://github.com/aiogram/aiogram.git"
AIOGRAM_REF="dev-3.x"

DEST="docs/vendor"          # relative to project root
KEEP_DJANGO_RELEASE_NOTES=0 # 1 = keep docs/releases (large, rarely useful)
# -----------------------------------------------------------------------------

cd "$(dirname "$0")/.."
mkdir -p "$DEST"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fetch() {
  local name="$1" repo="$2" ref="$3"
  local clone="$TMP/$name" out="$DEST/$name"

  echo ">> $name ($ref)"
  git clone --quiet --depth 1 --branch "$ref" \
    --filter=blob:none --sparse "$repo" "$clone"
  git -C "$clone" sparse-checkout set docs

  rm -rf "$out"
  mkdir -p "$out"
  cp -r "$clone/docs/." "$out/"

  # Keep only readable text docs.
  find "$out" -type f ! \( -name '*.rst' -o -name '*.md' -o -name '*.txt' \) -delete
  # Not documentation: pip requirements files and translation folders.
  find "$out" -type f -name 'requirements*.txt' -delete
  find "$out" -type d -name locale -prune -exec rm -rf {} +

  # Remove folders left empty by the cleanup.
  find "$out" -type d -empty -delete

  # Record where this copy came from.
  {
    echo "source: $repo"
    echo "ref:    $ref"
    echo "commit: $(git -C "$clone" rev-parse HEAD)"
    echo "date:   $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  } > "$out/_SOURCE.txt"
}

fetch django  "$DJANGO_REPO"  "$DJANGO_REF"
fetch aiogram "$AIOGRAM_REPO" "$AIOGRAM_REF"

if [ "$KEEP_DJANGO_RELEASE_NOTES" -eq 0 ]; then
  rm -rf "$DEST/django/releases"
fi

echo
echo "Done. Sizes:"
du -sh "$DEST"/*
echo "Files:"
find "$DEST" -type f | wc -l
