#!/bin/bash

echo "[BOOT] Automation logic initiated. Waiting 160 seconds for emulator stabilization..."
sleep 160

echo "[ADB] Establishing connection to localhost:5555..."
adb connect localhost:5555
adb wait-for-device

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

echo "[BOT] Launching Telegram Controller..."
/opt/venv/bin/python3 /app/bot.py
