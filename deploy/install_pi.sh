#!/usr/bin/env bash
# Install MeSA as a systemd service on the Raspberry Pi (HW-003).
# Run on the Pi, from the repo root:  sudo bash deploy/install_pi.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
SERVICE_SRC="$REPO_DIR/deploy/mesa.service"
SERVICE_DST="/etc/systemd/system/mesa.service"

echo "==> Installing $SERVICE_DST (from $SERVICE_SRC)"
# Rewrite User/paths to the actual invoking user + repo location.
RUN_USER="${SUDO_USER:-pi}"
sed -e "s|^User=.*|User=${RUN_USER}|" \
    -e "s|^WorkingDirectory=.*|WorkingDirectory=${REPO_DIR}|" \
    -e "s|^ExecStart=.*|ExecStart=${REPO_DIR}/.venv/bin/python ${REPO_DIR}/main.py|" \
    "$SERVICE_SRC" > "$SERVICE_DST"

echo "==> Enabling I2C (servos + OLED) — ensure 'dtparam=i2c_arm=on' in /boot/config.txt"
echo "==> Reloading systemd + enabling MeSA on boot"
systemctl daemon-reload
systemctl enable mesa.service
systemctl restart mesa.service
echo "==> Done. Follow logs with:  journalctl -u mesa -f"
