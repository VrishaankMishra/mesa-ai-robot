#!/usr/bin/env bash
# Launch the Streamlit dashboard on the LAN (DASH-002).
# On the Pi, phones/laptops on the same Wi-Fi can then reach http://<pi-ip>:8501
set -euo pipefail
cd "$(dirname "$0")/.."
exec streamlit run mesa/dashboard/app.py \
  --server.address 0.0.0.0 \
  --server.port "${MESA_DASHBOARD_PORT:-8501}"
