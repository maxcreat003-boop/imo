---
title: IMO Automation Bot
emoji: 🤖
colorFrom: blue
colorTo: green
sdk: docker
app_port: 6080
pinned: false
---

# IMO Cloud Automation Bot (v10.0)

A highly automated, queue-based IMO account registration bot designed for cloud environments.

## Deployment on Hugging Face Spaces
1. Create a **New Space** on Hugging Face.
2. Select **Docker** as the SDK.
3. Choose **GitHub** as the source and link this repository.
4. Go to **Settings > Variables and secrets** in your Space.
5. Add your `BOT_TOKEN` as a secret.

## Features
- **Adaptive Resource Intelligence**: Detects CPU/RAM and switches between Safe/Balanced/Turbo modes.
- **Telegram Command Center**: Control logs, screenshots, and focus directly from Telegram.
- **Auto-Recovery**: Heartbeat system to reconnect ADB if the emulator stalls.
