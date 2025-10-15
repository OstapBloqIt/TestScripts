#!/bin/bash
# WiFi Hardware and Device Tree Diagnostic

echo "========================================"
echo "WiFi Hardware Detection"
echo "========================================"
echo ""

echo "1. Checking MMC/SDIO host controllers..."
cat /sys/kernel/debug/mmc*/ios 2>/dev/null
echo ""

echo "2. Checking device tree for WiFi configuration..."
echo "WiFi power enable pins:"
find /sys/firmware/devicetree/base -name "*wifi*" 2>/dev/null | while read path; do
    echo "  $path"
    if [ -f "$path" ]; then
        xxd "$path" 2>/dev/null | head -3
    fi
done
echo ""

echo "3. Checking GPIO exports and states..."
if [ -d /sys/class/gpio ]; then
    ls -la /sys/class/gpio/
    for gpio in /sys/class/gpio/gpio*/; do
        if [ -d "$gpio" ]; then
            echo "  $(basename $gpio): direction=$(cat ${gpio}direction 2>/dev/null), value=$(cat ${gpio}value 2>/dev/null)"
        fi
    done
fi
echo ""

echo "4. Checking regulators..."
if [ -d /sys/class/regulator ]; then
    for reg in /sys/class/regulator/regulator*/; do
        if [ -d "$reg" ]; then
            name=$(cat ${reg}name 2>/dev/null)
            state=$(cat ${reg}state 2>/dev/null)
            if [[ $name == *"wifi"* ]] || [[ $name == *"sd"* ]]; then
                echo "  $name: $state"
            fi
        fi
    done
fi
echo ""

echo "5. Checking device tree overlays..."
if [ -f /proc/device-tree/chosen/overlays ]; then
    echo "Loaded overlays:"
    cat /proc/device-tree/chosen/overlays 2>/dev/null
else
    echo "No overlay information available"
fi
echo ""

echo "6. Checking for SDIO/MMC in device tree..."
find /proc/device-tree -name "*mmc*" -o -name "*sdio*" -o -name "*wifi*" 2>/dev/null | head -20
echo ""

echo "7. Detailed MMC host information..."
for mmc in /sys/class/mmc_host/mmc*; do
    if [ -d "$mmc" ]; then
        echo "Host: $(basename $mmc)"
        echo "  Max freq: $(cat $mmc/max_frequency 2>/dev/null) Hz"
        echo "  Capabilities: $(cat $mmc/caps 2>/dev/null)"
        echo "  Capabilities2: $(cat $mmc/caps2 2>/dev/null)"
    fi
done
echo ""

echo "8. Checking dmesg for SDIO/MMC initialization..."
dmesg | grep -i -E "mmc[0-9]|sdio|sdhci" | tail -30
echo ""

echo "9. Checking boot log for WiFi..."
journalctl -b | grep -i wifi 2>/dev/null | head -20
echo ""

echo "10. Listing available device tree overlays..."
ls -la /boot/overlays/ 2>/dev/null | grep -i wifi
ls -la /boot/dtb/overlays/ 2>/dev/null | grep -i wifi
echo ""

echo "========================================"
echo "Diagnostic Complete"
echo "========================================"
