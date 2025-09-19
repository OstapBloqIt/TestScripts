#!/usr/bin/env bash
set -euo pipefail

# CONFIG
SSH_USER="torizon"
SSH_HOST="192.168.24.22"
SSH_PASS="bloqit"
LOCAL_SRC="/mnt/c/Users/Ostap Kurtash/Documents/github/TestScripts/"
REMOTE_DEST="/tmp"

# Ensure we don't get blocked by stale/changed host keys
ssh-keygen -f "$HOME/.ssh/known_hosts" -R "$SSH_HOST" 2>/dev/null || true

# copy files
sshpass -p "$SSH_PASS" scp -o StrictHostKeyChecking=no -r -- "$LOCAL_SRC" "${SSH_USER}@${SSH_HOST}:$REMOTE_DEST"

# run remote cleanup tasks
sshpass -p "$SSH_PASS" ssh -o StrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}" \
  "printf '%s\n' '$SSH_PASS' | sudo -S pkill -f 'bloq-it-firmware/main.py' || true; \
   printf '%s\n' '$SSH_PASS' | sudo -S pkill -f 'app-ui' || true; \
   printf '%s\n' '$SSH_PASS' | sudo -S $REMOTE_DEST/TestScripts/Watchdog/watchdog -b 3 disable"

# open interactive root shell
echo "$SSH_PASS" | sshpass -p "$SSH_PASS" ssh -tt -o StrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}" 'sudo -S su -'
