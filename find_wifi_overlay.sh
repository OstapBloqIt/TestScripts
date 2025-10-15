#!/bin/bash
# WiFi Device Tree Overlay Configuration Helper

echo "========================================"
echo "WiFi Device Tree Overlay Configuration"
echo "========================================"
echo ""

# Find the current deployment
DEPLOY_DIR=$(find /boot/ostree -maxdepth 1 -name "torizon-*" -type d | head -1)
echo "Current deployment: $DEPLOY_DIR"
echo ""

# List all available overlays
echo "Available device tree overlays:"
if [ -d "$DEPLOY_DIR/dtb/overlays" ]; then
    ls -1 "$DEPLOY_DIR/dtb/overlays/" | grep -v "^$"
    echo ""
    
    echo "WiFi-related overlays:"
    ls -1 "$DEPLOY_DIR/dtb/overlays/" | grep -i wifi
    echo ""
    
    echo "Verdin overlays:"
    ls -1 "$DEPLOY_DIR/dtb/overlays/" | grep -i verdin | head -20
else
    echo "Overlay directory not found!"
fi
echo ""

# Check current overlay configuration
echo "Current overlay configuration:"
OVERLAY_FILE="/boot/loader/entries/ostree-1-torizon.conf"
if [ -f "$OVERLAY_FILE" ]; then
    echo "File: $OVERLAY_FILE"
    grep -i "devicetree" "$OVERLAY_FILE"
else
    echo "Checking alternative locations..."
    find /boot/loader -name "*.conf" -exec grep -l "torizon" {} \;
    find /boot/loader -name "*.conf" | while read f; do
        echo "--- $f ---"
        cat "$f"
    done
fi
echo ""

# Check for overlays.txt
echo "Checking for overlays.txt configuration:"
find /boot -name "overlays.txt" -exec echo "Found: {}" \; -exec cat {} \;
echo ""

# Check device tree compatible string
echo "Device tree compatible string:"
cat /proc/device-tree/compatible 2>/dev/null | tr '\0' '\n'
echo ""

echo "========================================"
echo "Configuration Instructions"
echo "========================================"
echo ""
echo "To enable WiFi overlay on Torizon, you need to:"
echo "1. Identify the correct WiFi overlay file"
echo "2. Add it to the device tree overlay configuration"
echo ""
echo "For Toradex Verdin iMX8MM with SDIO WiFi, you typically need:"
echo "  - verdin-imx8mm_wifi_overlay.dtbo (for SDIO WiFi)"
echo ""
echo "Configuration methods:"
echo "A. Using TorizonCore Builder (recommended for production)"
echo "B. Using ostree admin commands (for testing)"
echo ""
echo "========================================"
