#!/bin/bash

################################################################################
# CP2104 Hardware Change Monitor
# Monitors USB events for CP2104 device (VID:PID 10c4:ea60) and logs changes
################################################################################

# Configuration
CP2104_VID="10c4"
CP2104_PID="ea60"
LOG_DIR="./logs"
LOG_FILE="${LOG_DIR}/cp2104_monitor_$(date +%Y%m%d_%H%M%S).log"

# Colors for console output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

################################################################################
# Functions
################################################################################

log_message() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S.%3N')

    # Write to log file
    echo "[${timestamp}] [${level}] ${message}" >> "${LOG_FILE}"

    # Write to console with colors
    case "${level}" in
        INFO)
            echo -e "${BLUE}[${timestamp}]${NC} ${message}"
            ;;
        CONNECT)
            echo -e "${GREEN}[${timestamp}] ✅ CONNECTED${NC} ${message}"
            ;;
        DISCONNECT)
            echo -e "${RED}[${timestamp}] ❌ DISCONNECTED${NC} ${message}"
            ;;
        WARNING)
            echo -e "${YELLOW}[${timestamp}] ⚠️  WARNING${NC} ${message}"
            ;;
        ERROR)
            echo -e "${RED}[${timestamp}] ❌ ERROR${NC} ${message}"
            ;;
        *)
            echo "[${timestamp}] ${message}"
            ;;
    esac
}

get_device_details() {
    local devpath="$1"
    local details=""

    if [[ -n "${devpath}" && -d "/sys${devpath}" ]]; then
        local syspath="/sys${devpath}"

        # Try to get product name
        if [[ -f "${syspath}/product" ]]; then
            local product=$(cat "${syspath}/product" 2>/dev/null)
            details="${details}Product: ${product}, "
        fi

        # Try to get serial number
        if [[ -f "${syspath}/serial" ]]; then
            local serial=$(cat "${syspath}/serial" 2>/dev/null)
            details="${details}Serial: ${serial}, "
        fi

        # Try to get manufacturer
        if [[ -f "${syspath}/manufacturer" ]]; then
            local mfg=$(cat "${syspath}/manufacturer" 2>/dev/null)
            details="${details}Manufacturer: ${mfg}, "
        fi

        # Get bus location
        if [[ -f "${syspath}/busnum" && -f "${syspath}/devnum" ]]; then
            local busnum=$(cat "${syspath}/busnum" 2>/dev/null)
            local devnum=$(cat "${syspath}/devnum" 2>/dev/null)
            details="${details}Bus ${busnum} Device ${devnum}"
        fi
    fi

    echo "${details}"
}

get_tty_device() {
    local devpath="$1"
    local tty=""

    if [[ -n "${devpath}" && -d "/sys${devpath}" ]]; then
        # Look for tty devices under this USB device
        local tty_path=$(find "/sys${devpath}" -path "*/tty/ttyUSB*" 2>/dev/null | head -n1)
        if [[ -n "${tty_path}" ]]; then
            tty=$(basename "${tty_path}")
        fi
    fi

    echo "${tty}"
}

monitor_usb_events() {
    log_message "INFO" "Starting CP2104 monitoring..."
    log_message "INFO" "Target device: VID=${CP2104_VID} PID=${CP2104_PID}"
    log_message "INFO" "Log file: ${LOG_FILE}"
    log_message "INFO" "Press Ctrl+C to stop monitoring"
    echo ""

    # Check if CP2104 is currently connected
    if lsusb -d "${CP2104_VID}:${CP2104_PID}" &>/dev/null; then
        local device_info=$(lsusb -d "${CP2104_VID}:${CP2104_PID}")
        log_message "INFO" "CP2104 currently connected: ${device_info}"
    else
        log_message "INFO" "CP2104 not currently connected - waiting for events..."
    fi
    echo ""

    # Monitor udev events
    udevadm monitor --udev --property --subsystem-match=usb --subsystem-match=tty | while read -r line; do
        # Detect event type
        if [[ "${line}" =~ ^UDEV.*add ]]; then
            event_type="add"
            devpath=""
            vid=""
            pid=""
            devname=""
        elif [[ "${line}" =~ ^UDEV.*remove ]]; then
            event_type="remove"
            devpath=""
            vid=""
            pid=""
            devname=""
        fi

        # Parse properties
        if [[ "${line}" =~ ^DEVPATH=(.+)$ ]]; then
            devpath="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ^ID_VENDOR_ID=(.+)$ ]]; then
            vid="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ^ID_MODEL_ID=(.+)$ ]]; then
            pid="${BASH_REMATCH[1]}"
        elif [[ "${line}" =~ ^DEVNAME=(.+)$ ]]; then
            devname="${BASH_REMATCH[1]}"
        fi

        # Check if this is a CP2104 device event
        if [[ "${vid}" == "${CP2104_VID}" && "${pid}" == "${CP2104_PID}" ]]; then
            local details=$(get_device_details "${devpath}")

            if [[ "${event_type}" == "add" ]]; then
                log_message "CONNECT" "CP2104 detected - ${details}"

                # Give the system a moment to create TTY device
                sleep 0.2
                local tty=$(get_tty_device "${devpath}")
                if [[ -n "${tty}" ]]; then
                    log_message "INFO" "  TTY device created: /dev/${tty}"
                fi
            elif [[ "${event_type}" == "remove" ]]; then
                log_message "DISCONNECT" "CP2104 removed - ${details}"
            fi
        fi

        # Also log TTY device events for CP2104
        if [[ -n "${devname}" && "${devname}" =~ ttyUSB ]]; then
            # Check if this TTY belongs to CP2104 by looking at dmesg
            local recent_cp2104=$(dmesg | tail -20 | grep -i "cp210.*${devname##*/}")
            if [[ -n "${recent_cp2104}" ]]; then
                if [[ "${event_type}" == "add" ]]; then
                    log_message "INFO" "  TTY device added: ${devname}"
                elif [[ "${event_type}" == "remove" ]]; then
                    log_message "INFO" "  TTY device removed: ${devname}"
                fi
            fi
        fi
    done
}

detect_rapid_cycling() {
    log_message "INFO" "Analyzing log for rapid connect/disconnect cycles..."

    # Count events in last 10 seconds
    local recent_events=$(tail -50 "${LOG_FILE}" | grep -c "CONNECT\|DISCONNECT")

    if [[ ${recent_events} -gt 10 ]]; then
        log_message "WARNING" "Rapid cycling detected: ${recent_events} events in recent history"
        log_message "WARNING" "This indicates a hardware connection issue (loose connector, power problem, etc.)"
    fi
}

cleanup() {
    echo ""
    log_message "INFO" "Monitoring stopped"
    detect_rapid_cycling
    log_message "INFO" "Full log saved to: ${LOG_FILE}"
    exit 0
}

################################################################################
# Main
################################################################################

# Create log directory
mkdir -p "${LOG_DIR}"

# Set up signal handlers
trap cleanup SIGINT SIGTERM

# Start monitoring
monitor_usb_events
