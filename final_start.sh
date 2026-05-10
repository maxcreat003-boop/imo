#!/bin/bash

# [v8.0 COMMAND CENTER]
LOG_FILE="/app/bot_logs.txt"

# Redirect all standard and error output to the log file for /logs command
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[v8.0] Command Center Initialization..."

TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')

# Start Bot Immediately
/opt/venv/bin/python3 /app/bot.py &

if [ "$TOTAL_RAM" -lt 2 ]; then
    echo "[ADAPTIVE] Safe Mode (1GB RAM). 600s Wait."
    BOOT_WAIT=600
else
    echo "[ADAPTIVE] Performance Mode. 160s Wait."
    BOOT_WAIT=160
fi

sleep $BOOT_WAIT

adb connect localhost:5555

MAX_RETRIES=40
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    STATUS=$(adb get-state 2>&1)
    if [ "$STATUS" == "device" ]; then
        echo "[SUCCESS] Emulator online."
        break
    fi
    echo "[WAIT] Status: $STATUS. Retrying..."
    sleep 30
    RETRY_COUNT=$((RETRY_COUNT+1))
    adb connect localhost:5555
done

echo "[SYSTEM] Provisioning Profiles..."
for i in {1..10}
do
    USER_ID=$(adb shell pm create-user Clone_$i | grep -oE '[0-9]+')
    if [ ! -z "$USER_ID" ]; then
        adb shell pm install-existing --user $USER_ID com.imo.android.imoimlite
    fi
    if [ "$TOTAL_RAM" -lt 2 ]; then sleep 15; else sleep 2; fi
done

echo "[READY] Command Center v8.0 is operational."
wait
