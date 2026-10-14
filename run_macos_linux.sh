#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt
printf '\nECHO Guestbook: http://127.0.0.1:8000\n\n'
python3 app.py
