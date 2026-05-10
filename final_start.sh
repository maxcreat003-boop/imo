#!/bin/bash

# [v7.0 ADAPTIVE INITIALIZATION]
TOTAL_RAM=$(free -g | awk '/^Mem:/{print $2}')
KVM_EXISTS=$(ls /dev/kvm 2>/dev/null)

# Start Bot Immediately
/opt/venv/bin/python3 /app/bot.py &

if [ "$TOTAL_RAM" -lt 2 ]; then
    echo "[ADAPTIVE] Low RAM detected (${TOTAL_RAM}GB). Slow boot mode (600s)..."
    BOOT_WAIT=600
else
    echo "[ADAPTIVE] High RAM detected (${TOTAL_RAM}GB). Fast boot mode (160s)..."
    BOOT_WAIT=160
fi

sleep $BOOT_WAIT

echo "[ADB] Establishing connection..."
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
    echo "[WAIT] Status: $STATUS. Retrying ($RETRY_COUNT/$MAX_RETRIES)..."
    sleep 30
    RETRY_COUNT=$((RETRY_COUNT+1))
    adb connect localhost:5555
done

echo "[SYSTEM] Creating 10 Profiles..."
for i in {1..10}
do
    USER_ID=$(adb shell pm create-user Clone_$i | grep -oE '[0-9]+')
    if [ ! -z "$USER_ID" ]; then
        adb shell pm install-existing --user $USER_ID com.imo.android.imoimlite
    fi
    # Adaptive delay between user creations
    if [ "$TOTAL_RAM" -lt 2 ]; then sleep 15; else sleep 2; fi
done

echo "[READY] Adaptive System v7.0 is online."
wait
