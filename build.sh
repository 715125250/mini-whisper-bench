#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
for command in cmake g++ python3; do
  command -v "$command" >/dev/null || { echo "Missing $command; install the tools listed in README.md." >&2; exit 1; }
done
python3 - <<'PY'
import hashlib, json, pathlib
receipt=json.loads(pathlib.Path('models/model.json').read_text())
p=pathlib.Path('models/ggml-tiny.bin')
if not p.is_file(): raise SystemExit('Missing bundled model: models/ggml-tiny.bin')
h=hashlib.sha256()
with p.open('rb') as f:
    for b in iter(lambda:f.read(1024*1024),b''): h.update(b)
if h.hexdigest()!=receipt['ggml_sha256']: raise SystemExit('Model checksum mismatch; extract the package again.')
print('Model checksum OK')
PY
cmake -S vendor/whisper.cpp -B build -DCMAKE_BUILD_TYPE=Release \
  -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DWHISPER_BUILD_TESTS=OFF \
  -DWHISPER_BUILD_EXAMPLES=ON -DWHISPER_BUILD_SERVER=ON
cmake --build build --target whisper-server -j "${LAB_BUILD_JOBS:-2}"
echo 'Ready. Run: bash start.sh 4'
