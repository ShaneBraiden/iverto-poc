#!/usr/bin/env bash
# Simulates an IP camera: MediaMTX serves an RTSP endpoint and FFmpeg loops a clip into it.
# Requires `mediamtx` and `ffmpeg` on PATH (or mediamtx in rtsp/bin).
#   ./rtsp/serve.sh [video] [path]   -> rtsp://localhost:8554/cam1
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
video="${1:-$here/../data/samples/people-walking.mp4}"
path="${2:-cam1}"
mediamtx="$(command -v mediamtx || echo "$here/bin/mediamtx")"

"$mediamtx" "$here/mediamtx.yml" &
server=$!
trap 'kill $server 2>/dev/null' EXIT
sleep 1
echo "Streaming $video -> rtsp://localhost:8554/$path  (Ctrl+C to stop)"
ffmpeg -hide_banner -loglevel warning -re -stream_loop -1 -i "$video" -c copy -f rtsp -rtsp_transport tcp "rtsp://localhost:8554/$path"
