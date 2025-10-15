#!/bin/bash
# SDIO WiFi Troubleshooting Script

echo "========================================"
echo "SDIO WiFi Module Check"
echo "========================================"
echo ""

echo "1. Checking mwifiex driver details..."
modinfo mwifiex_sdio 2>/dev/null
echo ""

echo "2. Checking SDIO devices..."
ls -la /sys/bus/sdio/devices/ 2>/dev/null
echo ""

echo "3. Checking mmc (SDIO host) devices..."
ls -la /sys/bus/mmc/devices/ 2>/dev/null
echo ""

echo "4. Checking kernel ring buffer for mwifiex errors..."
dmesg | grep -i mwifiex | tail -30
echo ""

echo "5. Checking for WiFi firmware..."
ls -la /lib/firmware/mrvl/ 2>/dev/null
ls -la /lib/firmware/*wifi* 2>/dev/null
echo ""

echo "6. Checking all network interfaces (including down)..."
ip link show 2>/dev/null || ifconfig -a 2>/dev/null
echo ""

echo "7. Checking GPIO/regulator status..."
cat /sys/kernel/debug/gpio 2>/dev/null | grep -i wifi
echo ""

echo "8. Checking device power state..."
find /sys/devices -name "*mmc*" -o -name "*sdio*" 2>/dev/null | head -20
echo ""

echo "9. Try to manually probe WiFi..."
echo "Reloading mwifiex modules..."
sudo rmmod mwifiex_sdio 2>/dev/null
sudo rmmod mwifiex 2>/dev/null
sleep 1
sudo modprobe mwifiex_sdio
sleep 2
dmesg | tail -20
echo ""

echo "========================================"
