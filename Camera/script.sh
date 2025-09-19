#!/usr/bin/env bash
set -euo pipefail

# CONFIG
SSH_USER="torizon"
SSH_HOST="192.168.24.22"
SSH_PASS="bloqit"           # <-- convenient but insecure. consider ssh keys.
LOCAL_SRC="/mnt/c/Users/Ostap Kurtash/Documents/github/TestScripts/"
REMOTE_DEST="/tmp"

# copy files (note quotes for paths with spaces)
sshpass -p "$SSH_PASS" scp -r -- "$LOCAL_SRC" "${SSH_USER}@${SSH_HOST}:$REMOTE_DEST"

# run remote cleanup tasks (non-interactive)
# we pipe the sudo password into sudo -S so it won't prompt.
sshpass -p "$SSH_PASS" ssh -oStrictHostKeyChecking=no "${SSH_USER}@${SSH_HOST}" \
  "printf '%s\n' '$SSH_PASS' | sudo -S pkill -f 'bloq-it-firmware/main.py' || true; \
   printf '%s\n' '$SSH_PASS' | sudo -S pkill -f 'app-ui' || true; \
   printf '%s\n' '$SSH_PASS' | sudo -S $REMOTE_DEST/TestScripts/Watchdog/watchdog -b 3 disable"

# finally, open an interactive root shell on the remote host
# the echo feeds the sudo password to sudo -S, sshpass handles the SSH auth
echo "$SSH_PASS" | sshpass -p "$SSH_PASS" ssh -tt "${SSH_USER}@${SSH_HOST}" 'sudo -S su -'
