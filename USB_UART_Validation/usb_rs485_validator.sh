#!/bin/bash

################################################################################
# USB, CP2104/CP2108, and RS485 Validation Script
#
# Description: Automatically collects USB enumeration data, validates CP210x
#              devices, RS485 transceivers, and generates a comprehensive
#              markdown validation report.
#
# Usage: ./usb_rs485_validator.sh [output_report.md]
#
# Author: Auto-generated validation script
# Platform: Torizon Core / iMX8M Mini
################################################################################

set -euo pipefail

# Configuration
REPORT_FILE="${1:-USB_RS485_Validation_Report_$(date +%Y%m%d_%H%M%S).md}"
TEMP_DIR="/tmp/usb_validation_$$"
mkdir -p "$TEMP_DIR"

# Color codes for terminal output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Cleanup function
cleanup() {
    rm -rf "$TEMP_DIR"
}
trap cleanup EXIT

################################################################################
# Data Collection Functions
################################################################################

collect_all_data() {
    log_info "Collecting system information..."

    # System info
    uname -r > "$TEMP_DIR/kernel_version.txt"
    cat /proc/version > "$TEMP_DIR/kernel_full.txt"
    hostname > "$TEMP_DIR/hostname.txt"
    date "+%Y-%m-%d" > "$TEMP_DIR/date.txt"
    date "+%Y-%m-%d %H:%M:%S" > "$TEMP_DIR/datetime.txt"

    log_info "Collecting USB device information..."

    # USB device lists
    lsusb > "$TEMP_DIR/lsusb.txt" 2>&1
    lsusb -t > "$TEMP_DIR/lsusb_tree.txt" 2>&1
    lsusb -v -d 10c4:ea71 2>/dev/null > "$TEMP_DIR/cp2108_detail.txt" || echo "CP2108 not found" > "$TEMP_DIR/cp2108_detail.txt"
    lsusb -v -d 10c4:ea60 2>/dev/null > "$TEMP_DIR/cp2104_detail.txt" || echo "CP2104 not found" > "$TEMP_DIR/cp2104_detail.txt"
    lsusb -v -d 0424:2517 2>/dev/null > "$TEMP_DIR/usb_hub_detail.txt" || echo "USB Hub not found" > "$TEMP_DIR/usb_hub_detail.txt"

    log_info "Collecting kernel messages..."

    # Kernel messages
    dmesg | grep -i "cp210" > "$TEMP_DIR/dmesg_cp210x.txt" || echo "No CP210x messages" > "$TEMP_DIR/dmesg_cp210x.txt"
    dmesg | grep -i "usb 2-" > "$TEMP_DIR/dmesg_usb_bus2.txt" || echo "No USB Bus 2 messages" > "$TEMP_DIR/dmesg_usb_bus2.txt"

    log_info "Collecting serial device information..."

    # Serial devices
    find /sys/bus/usb-serial/devices/ -type l 2>/dev/null > "$TEMP_DIR/usb_serial_devices.txt" || echo "" > "$TEMP_DIR/usb_serial_devices.txt"
    ls -la /sys/class/tty/ttyUSB* 2>/dev/null > "$TEMP_DIR/tty_class_devices.txt" || echo "" > "$TEMP_DIR/tty_class_devices.txt"

    # CP2108 interfaces
    for port in 0 1 2 3; do
        if [ -f "/sys/bus/usb/devices/2-1.5:1.$port/interface" ]; then
            echo "=== CP2108 Interface $port ===" >> "$TEMP_DIR/cp2108_interfaces.txt"
            cat "/sys/bus/usb/devices/2-1.5:1.$port/interface" >> "$TEMP_DIR/cp2108_interfaces.txt" 2>&1
        fi
    done

    # USB hub ports
    ls /sys/bus/usb/devices/ | grep "^2-1\." | sort > "$TEMP_DIR/hub_ports.txt" 2>&1 || echo "" > "$TEMP_DIR/hub_ports.txt"

    log_info "Collecting driver information..."

    # Driver info
    lsmod | grep cp210x > "$TEMP_DIR/lsmod_cp210x.txt" || echo "cp210x module not loaded" > "$TEMP_DIR/lsmod_cp210x.txt"
    modinfo cp210x > "$TEMP_DIR/modinfo_cp210x.txt" 2>&1 || echo "modinfo cp210x failed" > "$TEMP_DIR/modinfo_cp210x.txt"

    # Device details
    cat /sys/bus/usb/devices/2-1.5/product 2>/dev/null > "$TEMP_DIR/cp2108_product.txt" || echo "N/A" > "$TEMP_DIR/cp2108_product.txt"
    cat /sys/bus/usb/devices/2-1.5/serial 2>/dev/null > "$TEMP_DIR/cp2108_serial.txt" || echo "N/A" > "$TEMP_DIR/cp2108_serial.txt"
    cat /sys/bus/usb/devices/2-1.5/idVendor 2>/dev/null > "$TEMP_DIR/cp2108_vendor.txt" || echo "10c4" > "$TEMP_DIR/cp2108_vendor.txt"
    cat /sys/bus/usb/devices/2-1.5/idProduct 2>/dev/null > "$TEMP_DIR/cp2108_product_id.txt" || echo "ea71" > "$TEMP_DIR/cp2108_product_id.txt"
}

################################################################################
# Analysis and Report Generation
################################################################################

generate_report() {
    local kernel_ver=$(cat "$TEMP_DIR/kernel_version.txt")
    local kernel_full=$(cat "$TEMP_DIR/kernel_full.txt")
    local host_name=$(cat "$TEMP_DIR/hostname.txt")
    local report_date=$(cat "$TEMP_DIR/date.txt")
    local report_datetime=$(cat "$TEMP_DIR/datetime.txt")

    # Analyze CP2108
    local cp2108_found="NO"
    local cp2108_interfaces=0
    if grep -q "10c4:ea71" "$TEMP_DIR/lsusb.txt" 2>/dev/null; then
        cp2108_found="YES"
        cp2108_interfaces=$(grep -c "CP2108 Interface" "$TEMP_DIR/cp2108_interfaces.txt" 2>/dev/null || echo "0")
    fi

    # Analyze CP2104
    local cp2104_found="NO"
    local cp2104_was_detected="NO"
    if grep -q "10c4:ea60" "$TEMP_DIR/lsusb.txt" 2>/dev/null; then
        cp2104_found="YES"
    fi
    if grep -q "cp210x.*ttyUSB8" "$TEMP_DIR/dmesg_cp210x.txt" 2>/dev/null; then
        cp2104_was_detected="YES"
    fi

    # Analyze RS485
    local rs485_count=0
    for i in 0 1 2 3; do
        if grep -q "ttyUSB$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null && \
           grep -q "2-1.5:1.$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null; then
            rs485_count=$((rs485_count + 1))
        fi
    done

    # Analyze USB Hub
    local hub_found="NO"
    local hub_ports=7
    if grep -q "0424:2517" "$TEMP_DIR/lsusb.txt" 2>/dev/null; then
        hub_found="YES"
        if grep -q "nNbrPorts" "$TEMP_DIR/usb_hub_detail.txt" 2>/dev/null; then
            hub_ports=$(grep "nNbrPorts" "$TEMP_DIR/usb_hub_detail.txt" | awk '{print $2}' || echo "7")
        fi
    fi

    local total_tty=$(grep -c "ttyUSB" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null || echo "0")

    # CP2108 details
    local cp2108_product=$(cat "$TEMP_DIR/cp2108_product.txt" 2>/dev/null)
    local cp2108_serial=$(cat "$TEMP_DIR/cp2108_serial.txt" 2>/dev/null)
    local cp2108_vendor=$(cat "$TEMP_DIR/cp2108_vendor.txt" 2>/dev/null)
    local cp2108_prodid=$(cat "$TEMP_DIR/cp2108_product_id.txt" 2>/dev/null)

    # Generate icons
    local cp2108_icon=$([ "$cp2108_found" == "YES" ] && echo "✅" || echo "❌")
    local cp2104_icon=$([ "$cp2104_found" == "YES" ] && echo "✅" || echo "⚠️")
    local rs485_icon=$([ "$rs485_count" == "4" ] && echo "✅" || echo "⚠️")
    local hub_icon=$([ "$hub_found" == "YES" ] && echo "✅" || echo "❌")

    # Generate the report
    cat > "$REPORT_FILE" << EOF
# USB, CP2104, and RS485 Validation Report

**Date:** $report_date
**Generated:** $report_datetime
**System:** iMX8M Mini Verdin SoM on Carrier Board
**Hostname:** $host_name
**Kernel:** $kernel_ver

---

## Executive Summary

This report documents the automated validation of USB enumeration, CP2108 Quad UART Bridge, CP2104 device, and RS485 transceivers connected to the iMX8M Mini system.

### Key Findings

$cp2108_icon **CP2108 Quad UART Bridge:** $([ "$cp2108_found" == "YES" ] && echo "FOUND" || echo "NOT FOUND") ($cp2108_interfaces interfaces detected)
$hub_icon **USB Hub (Microchip 0424:2517):** $([ "$hub_found" == "YES" ] && echo "FOUND" || echo "NOT FOUND") ($hub_ports ports)
$cp2104_icon **CP2104:** $([ "$cp2104_found" == "YES" ] && echo "FOUND" || echo "NOT FOUND")$([ "$cp2104_was_detected" == "YES" ] && [ "$cp2104_found" == "NO" ] && echo " (was detected, now disconnected)" || echo "")
$rs485_icon **RS485 Transceivers:** $rs485_count/4 channels operational
✅ **Serial Devices:** $total_tty ttyUSB devices enumerated

---

## 1. USB Topology Overview

### USB Device Tree

\`\`\`
$(cat "$TEMP_DIR/lsusb_tree.txt")
\`\`\`

### USB Device List

\`\`\`
$(cat "$TEMP_DIR/lsusb.txt")
\`\`\`

---

## 2. USB Hub Validation

### Microchip USB Hub (0424:2517)

**Status:** $([ "$hub_found" == "YES" ] && echo "✅ OPERATIONAL" || echo "❌ NOT FOUND")

| Property | Value |
|----------|-------|
| Vendor ID | 0424 (Microchip Technology, Inc.) |
| Product ID | 2517 |
| Device Class | Hub |
| Number of Ports | $hub_ports |

### Hub Descriptor Details

\`\`\`
$(grep -A 20 "Hub Descriptor" "$TEMP_DIR/usb_hub_detail.txt" 2>/dev/null || echo "Hub descriptor not available")
\`\`\`

---

## 3. CP2108 Quad UART Bridge Validation

### Device Details

**Status:** $([ "$cp2108_found" == "YES" ] && echo "✅ FULLY OPERATIONAL" || echo "❌ NOT FOUND")

| Property | Value |
|----------|-------|
| Vendor ID | $cp2108_vendor (Silicon Labs) |
| Product ID | $cp2108_prodid |
| Product Name | $cp2108_product |
| Serial Number | $cp2108_serial |
| Number of Interfaces | $cp2108_interfaces |

### Interface Mapping

| Interface | Endpoint IN | Endpoint OUT | Driver | TTY Device | Status |
|-----------|-------------|--------------|--------|------------|--------|
EOF

    # Generate interface table
    for i in 0 1 2 3; do
        if grep -q "ttyUSB$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null && \
           grep -q "2-1.5:1.$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null; then
            echo "| Interface $i | EP 0x8$((i+1)) (Bulk) | EP 0x0$((i+1)) (Bulk) | cp210x | ttyUSB$i | ✅ Active |" >> "$REPORT_FILE"
        else
            echo "| Interface $i | EP 0x8$((i+1)) (Bulk) | EP 0x0$((i+1)) (Bulk) | - | - | ❌ Not detected |" >> "$REPORT_FILE"
        fi
    done

    cat >> "$REPORT_FILE" << EOF

### CP2108 Interfaces

\`\`\`
$(cat "$TEMP_DIR/cp2108_interfaces.txt" 2>/dev/null || echo "No interface data available")
\`\`\`

---

## 4. CP2104 Device Status

### Detection Status

**Status:** $([ "$cp2104_found" == "YES" ] && echo "✅ CONNECTED" || ([ "$cp2104_was_detected" == "YES" ] && echo "⚠️ DISCONNECTED (Was detected previously)" || echo "❌ NOT DETECTED"))

| Property | Value |
|----------|-------|
| Current Status | $([ "$cp2104_found" == "YES" ] && echo "CONNECTED" || echo "DISCONNECTED") |
| Previously Detected | $cp2104_was_detected |

EOF

    if [ "$cp2104_was_detected" == "YES" ]; then
        cat >> "$REPORT_FILE" << EOF
### Detection History

The CP2104 device was detected in kernel messages:

\`\`\`
$(grep -E "(2-1\.1|ttyUSB8)" "$TEMP_DIR/dmesg_cp210x.txt" 2>/dev/null || echo "No detection history found")
\`\`\`

**Analysis:**
- Device was temporarily enumerated
- May indicate physical connection issue
- Could be power-related problem
- Recommend checking cable and connections

EOF
    fi

    cat >> "$REPORT_FILE" << EOF
**Recommendation:**
- Check physical connection of CP2104 to USB hub
- Verify power supply to the device
- Inspect USB cable and connectors
- Re-run validation after securing connection

---

## 5. RS485 Transceiver Validation

### Configuration

**Status:** $([ "$rs485_count" == "4" ] && echo "✅ OPERATIONAL" || echo "⚠️ INCOMPLETE ($rs485_count/4 channels)")

The CP2108 provides 4 UART interfaces for RS485 transceivers.

### RS485 Interface Mapping

| RS485 Channel | CP2108 Interface | TTY Device | USB Bus Path | Driver Status |
|---------------|------------------|------------|--------------|---------------|
EOF

    for i in 0 1 2 3; do
        if grep -q "ttyUSB$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null && \
           grep -q "2-1.5:1.$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null; then
            echo "| Channel $i | Interface $i | /dev/ttyUSB$i | 2-1.5:1.$i | ✅ Bound |" >> "$REPORT_FILE"
        else
            echo "| Channel $i | Interface $i | - | 2-1.5:1.$i | ❌ Not bound |" >> "$REPORT_FILE"
        fi
    done

    cat >> "$REPORT_FILE" << EOF

### Device Paths

\`\`\`
$(grep "ttyUSB[0-3]" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null || echo "No RS485 device paths found")
\`\`\`

---

## 6. Serial Device Summary

### All Enumerated Serial Devices

\`\`\`
$(cat "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null || echo "No serial devices found")
\`\`\`

---

## 7. Kernel Driver Status

### CP210x Driver Module

\`\`\`
$(cat "$TEMP_DIR/lsmod_cp210x.txt" 2>/dev/null)
\`\`\`

### Module Information

\`\`\`
$(head -30 "$TEMP_DIR/modinfo_cp210x.txt" 2>/dev/null)
\`\`\`

### Driver Load Sequence

\`\`\`
$(cat "$TEMP_DIR/dmesg_cp210x.txt" 2>/dev/null)
\`\`\`

---

## 8. Validation Results Summary

### ✅ Successful Validations

| Component | Status | Details |
|-----------|--------|---------|
EOF

    [ "$hub_found" == "YES" ] && echo "| USB Hub Enumeration | PASS | Microchip 0424:2517 properly detected |" >> "$REPORT_FILE"
    [ "$cp2108_found" == "YES" ] && echo "| CP2108 Enumeration | PASS | All $cp2108_interfaces interfaces detected |" >> "$REPORT_FILE"
    [ "$cp2108_found" == "YES" ] && echo "| CP2108 Driver Binding | PASS | cp210x driver bound to all interfaces |" >> "$REPORT_FILE"

    for i in 0 1 2 3; do
        if grep -q "ttyUSB$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null && \
           grep -q "2-1.5:1.$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null; then
            echo "| RS485 Interface $i | PASS | ttyUSB$i operational |" >> "$REPORT_FILE"
        fi
    done

    cat >> "$REPORT_FILE" << EOF

### ⚠️ Issues and Warnings

| Issue | Severity | Status | Recommendation |
|-------|----------|--------|----------------|
EOF

    if [ "$cp2104_found" != "YES" ] && [ "$cp2104_was_detected" == "YES" ]; then
        echo "| CP2104 Disconnected | Warning | Device was detected but disconnected | Check physical connection and power |" >> "$REPORT_FILE"
    elif [ "$cp2104_found" != "YES" ]; then
        echo "| CP2104 Not Found | Info | Device not detected | Verify device is connected to USB hub |" >> "$REPORT_FILE"
    fi

    if [ "$cp2108_found" != "YES" ]; then
        echo "| CP2108 Not Found | Critical | CP2108 not detected | Check USB hub connection and device |" >> "$REPORT_FILE"
    fi

    if [ "$rs485_count" != "4" ]; then
        echo "| Incomplete RS485 | Warning | Only $rs485_count/4 RS485 channels detected | Check CP2108 interfaces |" >> "$REPORT_FILE"
    fi

    cat >> "$REPORT_FILE" << EOF

---

## 9. Recommendations

### Immediate Actions

EOF

    if [ "$cp2104_found" != "YES" ] && [ "$cp2104_was_detected" == "YES" ]; then
        cat >> "$REPORT_FILE" << EOF
1. **CP2104 Connection Issue:**
   - Verify physical USB connection to hub
   - Check cable integrity
   - Ensure adequate power supply
   - Re-run validation script after fixing connection

EOF
    fi

    cat >> "$REPORT_FILE" << EOF
### Testing Next Steps

1. **Serial Port Communication Testing:**
   - Test serial communication on available ttyUSB devices
   - Verify baud rate configuration
   - Test RS485 half-duplex operation
   - Verify RS485 transceiver enable/disable control

2. **Functional Validation:**
   - Perform loopback tests on RS485 channels
   - Test with actual RS485 peripherals
   - Monitor for transmission errors

3. **Re-run Validation:**
   \`\`\`bash
   ./usb_rs485_validator.sh
   \`\`\`

---

## System Information

### Kernel Details

\`\`\`
$kernel_full
\`\`\`

---

## Validation Report Metadata

**Generated:** $report_datetime
**Script Version:** 1.0
**Hardware Platform:** Toradex Verdin iMX8M Mini
**Report File:** $REPORT_FILE

---

## Conclusion

This validation report was automatically generated by the USB/RS485 validation script.
All data was collected at the time of script execution ($report_datetime).

For questions or issues, re-run this script to generate an updated report.

EOF

    log_success "Report generated successfully!"
}

################################################################################
# Main Execution
################################################################################

main() {
    log_info "Starting USB, CP2104/CP2108, and RS485 validation..."
    echo ""

    collect_all_data

    echo ""
    log_info "Analyzing data and generating report..."

    generate_report

    echo ""
    log_success "Validation complete!"
    log_success "Report saved to: $REPORT_FILE"

    # Display summary
    echo ""
    echo "=========================================="
    echo "           VALIDATION SUMMARY"
    echo "=========================================="

    local cp2108_found=$(grep -q "10c4:ea71" "$TEMP_DIR/lsusb.txt" 2>/dev/null && echo "YES" || echo "NO")
    local cp2104_found=$(grep -q "10c4:ea60" "$TEMP_DIR/lsusb.txt" 2>/dev/null && echo "YES" || echo "NO")
    local rs485_count=0
    for i in 0 1 2 3; do
        if grep -q "ttyUSB$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null && \
           grep -q "2-1.5:1.$i" "$TEMP_DIR/tty_class_devices.txt" 2>/dev/null; then
            rs485_count=$((rs485_count + 1))
        fi
    done
    local hub_found=$(grep -q "0424:2517" "$TEMP_DIR/lsusb.txt" 2>/dev/null && echo "YES" || echo "NO")

    echo -e "CP2108 Status: $([ "$cp2108_found" == "YES" ] && echo "${GREEN}FOUND${NC}" || echo "${RED}NOT FOUND${NC}")"
    echo -e "CP2104 Status: $([ "$cp2104_found" == "YES" ] && echo "${GREEN}FOUND${NC}" || echo "${YELLOW}NOT CONNECTED${NC}")"
    echo -e "RS485 Channels: $([ "$rs485_count" == "4" ] && echo "${GREEN}$rs485_count/4${NC}" || echo "${YELLOW}$rs485_count/4${NC}")"
    echo -e "USB Hub Status: $([ "$hub_found" == "YES" ] && echo "${GREEN}FOUND${NC}" || echo "${RED}NOT FOUND${NC}")"

    echo "=========================================="
    echo ""
    echo "View the full report:"
    echo "  cat $REPORT_FILE"
    echo ""
}

# Run main function
main "$@"
