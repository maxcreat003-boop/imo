#!/bin/bash

# [v10.0 HUGGING FACE INITIALIZATION]
LOG_FILE="/app/bot_logs.txt"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "[v10.0] Hugging Face Deployment starting..."

# Start Bot
/opt/venv/bin/python3 /app/bot.py &

# Hugging Face provides 16GB RAM, so boot is much faster even in TCG mode.
echo "[BOOT] High-RAM environment detected. Waiting 120s (2 mins) for initialization..."
sleep 120

adb connect localhost:5555

# Boot Check Loop
MAX_RETRIES=40
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    STATUS=$(adb get-state 2>&1)
    if [ "$STATUS" == "device" ]; then
        echo "[SUCCESS] Emulator online."
        break
    fi
    echo "[WAIT] ADB Status: $STATUS. Retrying..."
    sleep 20
    RETRY_COUNT=$((RETRY_COUNT+1))
    adb connect localhost:5555
done

if [ ! -f "/app/.users_created" ] && [ "$STATUS" == "device" ]; then
    echo "[SYSTEM] Provisioning Profiles..."
    for i in {1..10}; do
        USER_ID=$(adb shell pm create-user Clone_$i | grep -oE '[0-9]+')
        if [ ! -z "$USER_ID" ]; then
            adb shell pm install-existing --user $USER_ID com.imo.android.imoimlite
        fi
        sleep 2
    done
    touch /app/.users_created
fi

echo "[READY] v10.0 Hugging Face System Online."
wait
