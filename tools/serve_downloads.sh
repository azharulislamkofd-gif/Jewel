#!/usr/bin/env bash
# Rebuild the media folder and serve it for download.
#
# Media files are tracked in git under media/ so they survive a sandbox restart.
# This script (re)installs deps, (re)renders the videos if missing, and starts
# the HTTP server on 0.0.0.0:8000.
#
#   bash tools/serve_downloads.sh            # build (if needed) + serve
#   bash tools/serve_downloads.sh --build    # build only, no server
#   bash tools/serve_downloads.sh --force    # re-render videos even if present
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
MODE="${1:-}"
MEDIA_DIR="media"

echo "[1/4] installing deps (Pillow + bundled ffmpeg)"
python3 -m pip install --quiet --break-system-packages Pillow imageio-ffmpeg \
  || python3 -m pip install --quiet --user Pillow imageio-ffmpeg

echo "[2/4] preparing ${MEDIA_DIR}/"
mkdir -p "$MEDIA_DIR"
cp -f images/*.png "$MEDIA_DIR"/ 2>/dev/null || true

echo "[3/4] rendering videos"
for spec in "tech_review_studio:tech_review_cinematic" "rock_singer_stage:rock_singer_cinematic"; do
  src="images/${spec%%:*}.png"
  out="${MEDIA_DIR}/${spec##*:}.mp4"
  if [[ ! -f "$src" ]]; then
    echo "  skip: $src not found"
    continue
  fi
  if [[ -f "$out" && "$MODE" != "--force" ]]; then
    echo "  exists: $out (use --force to re-render)"
    continue
  fi
  python3 tools/make_video.py "$src" "$out" --w 1920 --h 1080 --fps 30 --crf 19
done

ls -lh "$MEDIA_DIR"/

if [[ "$MODE" == "--build" ]]; then
  echo "[4/4] build only — not starting the server"
  exit 0
fi

echo "[4/4] serving ${MEDIA_DIR}/ on 0.0.0.0:${PORT}"
cd "$MEDIA_DIR"
exec python3 -u -m http.server "$PORT" --bind 0.0.0.0
