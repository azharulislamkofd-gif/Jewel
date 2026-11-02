#!/usr/bin/env bash
# Rebuild the media folder and serve it for download.
#
# Media files are tracked in git under media/ so they survive a sandbox restart.
# This script (re)installs deps, (re)renders the videos ONLY if missing, and
# starts tools/serve_downloads.py on 0.0.0.0:8000.  That server sends
# Content-Disposition: attachment + Range/206 support, so Android Chrome saves
# the MP4 instead of opening it in a video player.
#
#   bash tools/serve_downloads.sh            # build (if needed) + serve
#   bash tools/serve_downloads.sh --build    # build only, no server
#   bash tools/serve_downloads.sh --force    # re-render videos even if present
set -euo pipefail

cd "$(dirname "$0")/.."
PORT="${PORT:-8000}"
MODE="${1:-}"
MEDIA_DIR="media"
CONCERT_SRC="images/rock_singer_concert.jpg"
CONCERT_OUT="${MEDIA_DIR}/rock_singer_live_concert.mp4"
CONCERT_4K="${MEDIA_DIR}/rock_singer_live_concert_4k.mp4"

echo "[1/4] installing deps (Pillow + bundled ffmpeg + OpenCV)"
python3 -m pip install --quiet --break-system-packages \
  Pillow imageio-ffmpeg numpy opencv-python-headless \
  || python3 -m pip install --quiet --user \
     Pillow imageio-ffmpeg numpy opencv-python-headless

echo "[2/4] preparing ${MEDIA_DIR}/"
mkdir -p "$MEDIA_DIR"
cp -f images/*.png "$MEDIA_DIR"/ 2>/dev/null || true
cp -f "$CONCERT_SRC" "${MEDIA_DIR}/rock_singer_concert_still.jpg" 2>/dev/null || true

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

# Concert brief: procedural animation from the portrait still (1080p master + 4K).
if [[ -f "$CONCERT_SRC" ]]; then
  if [[ -s "$CONCERT_OUT" && -s "$CONCERT_4K" && "$MODE" != "--force" ]]; then
    echo "  existing MP4 found: $(realpath "$CONCERT_OUT")"
    echo "    $(stat -c '%s bytes' "$CONCERT_OUT") · script already executed — NOT regenerating"
    echo "  existing 4K found: $(realpath "$CONCERT_4K") ($(stat -c '%s bytes' "$CONCERT_4K"))"
  else
    python3 tools/make_concert_video.py "$CONCERT_SRC" "$CONCERT_OUT" \
      --seconds 20 --fps 30 --crf 18 --preset fast \
      --fourk "$CONCERT_4K" --fourk-crf 22 \
      --poster "${MEDIA_DIR}/rock_singer_live_concert_poster.jpg"
  fi
else
  echo "  skip: $CONCERT_SRC not found"
fi

ls -lh "$MEDIA_DIR"/

if [[ "$MODE" == "--build" ]]; then
  echo "[4/4] build only — not starting the server"
  exit 0
fi

echo "[4/4] serving ${MEDIA_DIR}/ on 0.0.0.0:${PORT} (Android-safe downloads)"
exec python3 -u tools/serve_downloads.py --dir "$MEDIA_DIR" --host 0.0.0.0 --port "$PORT"
