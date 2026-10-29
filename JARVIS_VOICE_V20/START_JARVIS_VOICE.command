#!/bin/bash
set -e
cd "$(dirname "$0")"
printf '\n=== JARVIS V2.0 - LOCAL VOICE COMMANDS ===\n'
if [[ "$(uname -s)" != "Darwin" ]]; then
  echo 'This launcher requires macOS.'
  exit 1
fi
if [[ ! -f settings.json || ! -f voice_service.py ]]; then
  echo 'Voice files missing. Extract/install the entire package.'
  exit 1
fi
if [[ ! -d .venv ]]; then
  echo 'First setup: creating a private Python environment...'
  python3 -m venv .venv
fi
source .venv/bin/activate
if ! python -c 'import sounddevice, faster_whisper, numpy' >/dev/null 2>&1; then
  echo 'Installing the local speech-recognition packages (requires internet the first time)...'
  python -m pip install -r requirements.txt
fi
printf '\nStarting local speech recognition.\n'
printf 'First launch also downloads the tiny.en Whisper model (~75 MB).\n'
printf 'macOS may ask Terminal for microphone access.\n\n'
python voice_service.py --activation panel "$@"
read -r -p 'Press Enter to close this window... ' _
