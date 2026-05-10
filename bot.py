import os
import re
import asyncio
import logging
import psutil
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
from dotenv import load_dotenv

# Configuration
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PACKAGE = "com.imo.android.imoimlite"
ACTIVITY = "com.imo.android.imo.activities.HomeActivity"
LOG_FILE = "/app/bot_logs.txt"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ImoBulletproofV9:
    def __init__(self):
        self.number_queue = asyncio.Queue()
        self.clone_status = {i: "Idle" for i in range(1, 11)}
        self.processed_count = 0
        self.adb_online = False
        
        # Adaptive Resource Logic
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        self.mode = "SAFE (1GB)" if total_ram_gb < 1.5 else "NORMAL"
        self.max_parallel = 1 if total_ram_gb < 1.5 else 3
        self.concurrency_limit = asyncio.Semaphore(self.max_parallel)

    async def run_adb(self, command: str) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                f"adb {command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            return stdout.decode().strip()
        except Exception: return ""

    async def adb_heartbeat(self):
        """v9.0 Heartbeat: Ensures ADB stays connected to the emulator."""
        while True:
            devices = await self.run_adb("devices")
            if "device" not in devices.splitlines()[-1]:
                logging.warning("ADB Offline. Attempting auto-recovery...")
                self.adb_online = False
                await self.run_adb("connect localhost:5555")
            else:
                self.adb_online = True
            await asyncio.sleep(30)

    async def get_user_id(self, clone_number: int) -> int:
        output = await self.run_adb("shell pm list users")
        for line in output.splitlines():
            if f"Clone_{clone_number}:" in line:
                try: return int(line.split(":")[0].replace("UserInfo{", ""))
                except: return -1
        return -1

    async def worker_loop(self):
        while True:
            # v9.0 Safety: Wait if ADB is offline
            if not self.adb_online:
                await asyncio.sleep(10)
                continue

            phone_number = await self.number_queue.get()
            clone_num = next((c for c, s in self.clone_status.items() if s == "Idle"), None)
            
            if not clone_num:
                await asyncio.sleep(5)
                await self.number_queue.put(phone_number)
                self.number_queue.task_done()
                continue

            async with self.concurrency_limit:
                user_id = await self.get_user_id(clone_num)
                if user_id == -1:
                    await self.number_queue.put(phone_number)
                    self.number_queue.task_done()
                    continue

                self.clone_status[clone_num] = f"Processing {phone_number}"
                try:
                    # Keep-Alive: Ensure app is focus
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(2)
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    await asyncio.sleep(15)
                    await self.run_adb(f"shell input text {phone_number}")
                    await asyncio.sleep(2)
                    await self.run_adb("shell input keyevent 66") 
                    await asyncio.sleep(10) # Wait for OTP page
                except Exception as e: logging.error(f"Worker Error: {e}")
                finally:
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
                    self.clone_status[clone_num] = "Idle"
                    self.processed_count += 1
                    self.number_queue.task_done()

    # --- Commands ---
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        status = "✅ ONLINE" if self.adb_online else "⏳ RECONNECTING..."
        dashboard = (
            "🤖 **IMO Bulletproof (v9.0)**\n\n"
            f"⚙️ **Mode**: `{self.mode}`\n"
            f"📡 **ADB Status**: `{status}`\n"
            f"🧠 **RAM**: {psutil.virtual_memory().percent}%\n"
            f"📊 **Queue**: {self.number_queue.qsize()} | ✅ **Total**: {self.processed_count}\n\n"
            "**Tools:**\n/screen | /logs | /check | /reboot"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

    async def cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not self.adb_online: return await update.message.reply_text("❌ ADB is Offline.")
        await update.message.reply_text("📸 Capturing...")
        try:
            os.system("adb exec-out screencap -p > /app/screen.png")
            if os.path.exists("/app/screen.png") and os.path.getsize("/app/screen.png") > 0:
                with open("/app/screen.png", 'rb') as f: await update.message.reply_photo(f)
            else: await update.message.reply_text("❌ Empty screenshot. Emulator might be slow.")
        except Exception as e: await update.message.reply_text(f"Error: {e}")

    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f: logs = "".join(f.readlines()[-20:])
            await update.message.reply_text(f"📋 **Logs:**\n```\n{logs}\n```", parse_mode='Markdown')
        else: await update.message.reply_text("❌ No logs yet.")

    async def cmd_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔄 Rebooting Controller...")
        os._exit(0)

async def post_init(application):
    bot_data = application.bot_data['instance']
    asyncio.create_task(bot_data.worker_loop())
    asyncio.create_task(bot_data.adb_heartbeat())

if __name__ == "__main__":
    if not TOKEN: exit(1)
    bot_instance = ImoBulletproofV9()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.bot_data['instance'] = bot_instance
    app.add_handler(CommandHandler("start", bot_instance.cmd_start))
    app.add_handler(CommandHandler("logs", bot_instance.cmd_logs))
    app.add_handler(CommandHandler("screen", bot_instance.cmd_screen))
    app.add_handler(CommandHandler("reboot", bot_instance.cmd_reboot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: [asyncio.create_task(bot_instance.number_queue.put(n)) for n in re.findall(r'\b\d{7,15}\b', u.message.text)] and u.message.reply_text("✅ Numbers added.")))
    
    print("Bot v9.0 starting...")
    # v9.0 Conflict Fix: drop_pending_updates=True
    app.run_polling(drop_pending_updates=True)
