#!/usr/bin/env bash
# Launch the Streamlit dashboard on the LAN (DASH-002).
# On the Pi, phones/laptops on the same Wi-Fi can then reach http://<pi-ip>:8501
set -euo pipefail
cd "$(dirname "$0")/.."
# Prefer the project venv so this works from a bare shell (no `source .venv/bin/activate`);
# fall back to whatever `streamlit` is on PATH.
if [ -x .venv/bin/streamlit ]; then
  STREAMLIT=.venv/bin/streamlit
else
  STREAMLIT=streamlit
fi
exec "$STREAMLIT" run mesa/dashboard/app.py \
  --server.address 0.0.0.0 \
  --server.port "${MESA_DASHBOARD_PORT:-8501}"
