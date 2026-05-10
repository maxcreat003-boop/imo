#!/bin/bash

# Start the Telegram Bot IMMEDIATELY so it responds to commands while waiting for the emulator
echo "[BOT] Launching Telegram Controller in background..."
/opt/venv/bin/python3 /app/bot.py &

echo "[BOOT] Automation logic initiated. Waiting 160 seconds for emulator stabilization..."
sleep 160

echo "[ADB] Establishing connection to localhost:5555..."
adb connect localhost:5555

# Only wait up to 120 seconds for the device so it doesn't hang forever if software emulation is slow
timeout 120 adb wait-for-device

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

# Keep script running to prevent supervisor from restarting it
wait
