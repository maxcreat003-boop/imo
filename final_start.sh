#!/bin/bash

# [v9.0 EMERGENCY REPAIR]
LOG_FILE="/app/bot_logs.txt"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[v9.0] Emergency Repair Initialization..."

# Start Bot IMMEDIATELY (v9.0 handles own ADB reconnects)
/opt/venv/bin/python3 /app/bot.py &

# Stripping even more system load
echo "[SYSTEM] Optimizing Android for 1GB RAM..."
# Disable Google Play Services if possible (generic attempt)
adb shell pm disable-user --user 0 com.google.android.gms >/dev/null 2>&1

echo "[BOOT] Waiting 600s for Software TCG boot..."
sleep 600

adb connect localhost:5555

# Auto-Recovery Loop in Shell
while true; do
    STATUS=$(adb get-state 2>&1)
    if [ "$STATUS" != "device" ]; then
        echo "[RECOVERY] ADB Offline. Status: $STATUS. Reconnecting..."
        adb connect localhost:5555
    fi
    
    # Check if we need to create users (only once)
    if [ ! -f "/app/.users_created" ] && [ "$STATUS" == "device" ]; then
        echo "[SYSTEM] Provisioning Profiles..."
        for i in {1..10}; do
            USER_ID=$(adb shell pm create-user Clone_$i | grep -oE '[0-9]+')
            if [ ! -z "$USER_ID" ]; then
                adb shell pm install-existing --user $USER_ID com.imo.android.imoimlite
            fi
            sleep 15
        done
        touch /app/.users_created
    fi
    
    sleep 60
done
