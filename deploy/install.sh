#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/telegram-userbot}"
sudo apt-get update
sudo apt-get install -y python3 python3-venv python3-pip

sudo useradd --system --create-home --shell /usr/sbin/nologin telegrambot 2>/dev/null || true
sudo mkdir -p "$APP_DIR"
sudo chown -R telegrambot:telegrambot "$APP_DIR"

sudo -u telegrambot python3 -m venv "$APP_DIR/.venv"
sudo -u telegrambot "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

echo "Copy .env to $APP_DIR/.env, then install deploy/telegram-userbot.service."
