#!/bin/bash
# WiFi Module Diagnostic Script for AzureWave AW-CM276NF
# Realtek RTL8822CE chipset

echo "========================================"
echo "WiFi Module Diagnostic - AW-CM276NF"
echo "========================================"
echo ""

echo "1. Checking for PCIe WiFi devices..."
if command -v lspci &> /dev/null; then
    lspci | grep -i network
    lspci | grep -i wireless
    lspci | grep -i realtek
    lspci | grep -i 8822
else
    echo "   lspci not available"
fi
echo ""

echo "2. Checking for WiFi kernel modules..."
lsmod | grep -i rtw
lsmod | grep -i 8822
lsmod | grep -i wifi
lsmod | grep -i wireless
echo ""

echo "3. Checking for WiFi network interfaces..."
ls -la /sys/class/net/ 2>/dev/null | grep -v lo | grep -v eth | grep -v docker | grep -v wwan
echo ""

echo "4. Checking kernel messages for WiFi..."
dmesg | grep -i -E "rtw|8822|wifi|wlan|wireless" | tail -20
echo ""

echo "5. Checking for WiFi devices in different locations..."
find /sys/devices -name "*wifi*" -o -name "*wlan*" 2>/dev/null
echo ""

echo "6. Checking available kernel modules for RTL8822CE..."
find /lib/modules/$(uname -r) -name "*rtw*" -o -name "*8822*" 2>/dev/null
echo ""

echo "7. Checking device tree for WiFi/PCIe..."
find /sys/firmware -name "*wifi*" -o -name "*pci*" 2>/dev/null | head -10
echo ""

echo "8. NetworkManager device status..."
nmcli device status
echo ""

echo "9. Checking for rfkill (WiFi/Bluetooth blocking)..."
if command -v rfkill &> /dev/null; then
    rfkill list all
else
    echo "   rfkill not available"
fi
echo ""

echo "10. Checking USB devices (in case module is USB-connected)..."
lsusb 2>/dev/null | grep -i realtek
echo ""

echo "========================================"
echo "Diagnostic Complete"
echo "========================================"
