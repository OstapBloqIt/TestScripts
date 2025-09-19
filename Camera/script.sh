#!/usr/bin/env bash
set -euo pipefail

sshpass -p ‘bloqit’ scp -r /mnt/c/Users/Ostap Kurtash/Documents/github/TestScripts/ torizon@192.168.24.22:/tmp

echo ‘bloqit’ | sshpass -p ‘bloqit’ ssh -t torizon@192.168.24.22 ‘sudo -S su -’

pkill -f "bloq-it-firmware/main.py"

pkill -f "app-ui"

/tmp/TestScripts/Watchdog/watchdog -b 3 disable
