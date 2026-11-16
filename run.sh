#!/usr/bin/env bash
set -euo pipefail

cd -- "$(dirname -- "${BASH_SOURCE[0]}")"

if [[ -x "venv/bin/python" ]]; then
    cairnmark_python="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
    cairnmark_python="$(command -v python3)"
else
    echo "Cairnmark could not find venv/bin/python or python3." >&2
    exit 1
fi

port="${PORT:-5000}"
echo "Starting Cairnmark at http://127.0.0.1:${port}"
echo "Press Ctrl+C or close this terminal to stop the server."
echo

exec "${cairnmark_python}" app.py
