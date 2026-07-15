#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
threads=${1:-4}
case "$threads" in ''|*[!0-9]*) echo 'Thread count must be an integer from 1 to 64.' >&2; exit 1;; esac
if [ "$threads" -lt 1 ] || [ "$threads" -gt 64 ]; then
  echo 'Thread count must be from 1 to 64.' >&2; exit 1
fi
if [ ! -x build/bin/whisper-server ]; then
  echo 'Run bash build.sh first.' >&2; exit 1
fi
exec build/bin/whisper-server -m models/ggml-tiny.bin \
  --host 127.0.0.1 --port 8080 -t "$threads" -l zh -ng -nc -nt -bs 1 -bo 1 -nf
