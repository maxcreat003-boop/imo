#!/bin/bash

# Start the Telegram Bot IMMEDIATELY
echo "[BOT] Launching Telegram Controller..."
/opt/venv/bin/python3 /app/bot.py &

echo "[BOOT] Software Emulation mode. Waiting 300 seconds (5 mins) for kernel initialization..."
sleep 300

echo "[ADB] Establishing connection to localhost:5555..."
adb connect localhost:5555

# Boot Check Loop: Wait until ADB reports the device is actually ready
echo "[ADB] Waiting for device to reach 'device' state..."
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    STATUS=$(adb get-state 2>&1)
    if [ "$STATUS" == "device" ]; then
        echo "[SUCCESS] Emulator is now ONLINE and ready."
        break
    fi
    echo "[WAIT] Device status: $STATUS. Retrying in 20 seconds ($RETRY_COUNT/$MAX_RETRIES)..."
    sleep 20
    RETRY_COUNT=$((RETRY_COUNT+1))
    adb connect localhost:5555
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "[ERROR] Emulator failed to boot within time limit. Check Railway logs for RAM/CPU issues."
    exit 1
fi

echo "[SYSTEM] Creating 10 Isolated User Profiles (Clone_1 to Clone_10)..."
for i in {1..10}
do
    echo "[USER] Provisioning profile Clone_$i..."
    USER_ID=$(adb shell pm create-user Clone_$i | grep -oE '[0-9]+')
    
    if [ ! -z "$USER_ID" ]; then
        echo "[USER] Successfully created Clone_$i with ID: $USER_ID"
        echo "[APP] Enabling imo Lite for Clone_$i (ID: $USER_ID)..."
        adb shell pm install-existing --user $USER_ID com.imo.android.imoimlite
    else
        echo "[ERROR] Failed to create Clone_$i"
    fi
done

echo "[READY] System is fully operational in Software Mode."
wait
