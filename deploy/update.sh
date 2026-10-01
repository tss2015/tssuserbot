#!/usr/bin/env bash
set -euo pipefail
APP_DIR="${APP_DIR:-/opt/telegram-userbot}"
cd "$APP_DIR"
sudo -u telegrambot git pull
sudo -u telegrambot "$APP_DIR/.venv/bin/pip" install -r requirements.txt
sudo systemctl restart telegram-userbot
sudo systemctl status telegram-userbot --no-pager
