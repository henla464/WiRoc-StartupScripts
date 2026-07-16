#!/bin/sh
# Persist a known-good system clock into the battery-backed pcf8563 RTC, so a reboot in the
# field doesn't lose it. Runs opportunistically: it only writes when the system clock is
# NTP-synced (e.g. at a wifi-equipped control) and is a NO-OP otherwise - so it never touches
# units with no internet, and never fights a clock set another way (e.g. the app). Finds the
# pcf8563 by driver name, not by rtc number (which is not guaranteed).
if command -v timedatectl >/dev/null 2>&1; then
    [ "$(timedatectl show -p NTPSynchronized --value 2>/dev/null)" = "yes" ] || exit 0
fi
rtcdev=""
for namefile in /sys/class/rtc/rtc*/name; do
    [ -e "$namefile" ] || continue
    if grep -q "rtc-pcf8563" "$namefile" 2>/dev/null; then
        rtcdev="/dev/$(basename "$(dirname "$namefile")")"
        break
    fi
done
[ -n "$rtcdev" ] || { echo "wiroc-rtc-writeback: pcf8563 rtc not found" >&2; exit 0; }
hwclock -f "$rtcdev" --systohc
