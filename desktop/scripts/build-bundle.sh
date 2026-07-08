#!/usr/bin/env bash
# Assemble desktop/bundle/ (backend wheel + uv, standalone UI) for electron-builder.
set -euo pipefail

DESKTOP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$DESKTOP_DIR/.." && pwd)"
BUNDLE="$DESKTOP_DIR/bundle"

command -v uv >/dev/null || { echo "uv is required (https://docs.astral.sh/uv/)"; exit 1; }

echo "==> backend wheel"
rm -rf "$BUNDLE"
mkdir -p "$BUNDLE/backend"
(cd "$REPO_ROOT" && uv build --wheel --out-dir "$BUNDLE/backend")

echo "==> uv binary"
cp "$(command -v uv)" "$BUNDLE/backend/uv"
chmod +x "$BUNDLE/backend/uv"

# Voice fixture so `--self-test` works in the packaged app too.
cp "$REPO_ROOT/tests/fixtures/voice_query.mp3" "$BUNDLE/backend/voice_query.mp3"

echo "==> UI (standalone, tarred — electron-builder strips node_modules/dot-dirs from extraResources)"
if [ ! -f "$REPO_ROOT/frontend/.next/standalone/server.js" ]; then
  echo "UI build missing — running npm run build:ui first"
  (cd "$DESKTOP_DIR" && npm run build:ui)
fi
tar -cf "$BUNDLE/ui.tar" -C "$REPO_ROOT/frontend/.next/standalone" .

echo "==> bundle ready:"
du -sh "$BUNDLE"/backend "$BUNDLE"/ui.tar
