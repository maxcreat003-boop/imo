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

class ImoTurboV10:
    def __init__(self):
        self.number_queue = asyncio.Queue()
        self.clone_status = {i: "Idle" for i in range(1, 11)}
        self.processed_count = 0
        self.adb_online = False
        
        # --- HUGGING FACE TURBO LOGIC ---
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        # Force TURBO if RAM > 8GB (HFS has 16GB)
        self.mode = "TURBO (16GB Optimized)" if total_ram_gb > 8 else "ADAPTIVE"
        self.max_parallel = 10 if total_ram_gb > 8 else 1
        self.concurrency_limit = asyncio.Semaphore(self.max_parallel)
        logging.info(f"[v10.0] High Performance Mode: {self.mode}")

    async def run_adb(self, command: str) -> str:
        try:
            process = await asyncio.create_subprocess_shell(
                f"adb {command}",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
            return stdout.decode().strip()
        except: return ""

    async def adb_heartbeat(self):
        while True:
            devices = await self.run_adb("devices")
            self.adb_online = "device" in devices.splitlines()[-1]
            if not self.adb_online: await self.run_adb("connect localhost:5555")
            await asyncio.sleep(20)

    async def get_user_id(self, clone_number: int) -> int:
        output = await self.run_adb("shell pm list users")
        for line in output.splitlines():
            if f"Clone_{clone_number}:" in line:
                try: return int(line.split(":")[0].replace("UserInfo{", ""))
                except: return -1
        return -1

    async def worker_loop(self):
        while True:
            phone_number = await self.number_queue.get()
            if not self.adb_online:
                await asyncio.sleep(5); await self.number_queue.put(phone_number); self.number_queue.task_done(); continue

            clone_num = next((c for c, s in self.clone_status.items() if s == "Idle"), None)
            if not clone_num:
                await asyncio.sleep(2); await self.number_queue.put(phone_number); self.number_queue.task_done(); continue

            async with self.concurrency_limit:
                user_id = await self.get_user_id(clone_num)
                if user_id == -1:
                    await self.number_queue.put(phone_number); self.number_queue.task_done(); continue

                self.clone_status[clone_num] = f"Processing {phone_number}"
                try:
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(1)
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    await asyncio.sleep(10) # Fast boot on 16GB
                    await self.run_adb(f"shell input text {phone_number}")
                    await asyncio.sleep(2)
                    await self.run_adb("shell input keyevent 66") 
                    await asyncio.sleep(5)
                except Exception as e: logging.error(f"Error: {e}")
                finally:
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
                    self.clone_status[clone_num] = "Idle"
                    self.processed_count += 1
                    self.number_queue.task_done()

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        dashboard = (
            "🚀 **IMO Turbo Bot (v10.0)**\n\n"
            f"⚡ **Environment**: `Hugging Face (16GB)`\n"
            f"⚙️ **System Mode**: `{self.mode}`\n"
            f"📡 **ADB Status**: `{'✅ ONLINE' if self.adb_online else '⏳ BOOTING'}`\n"
            f"📊 **Queue**: {self.number_queue.qsize()} | ✅ **Total**: {self.processed_count}\n\n"
            "**Control Center:**\n/screen | /logs | /check | /reboot"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

    async def cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        os.system("adb exec-out screencap -p > /app/screen.png")
        if os.path.exists("/app/screen.png"):
            with open("/app/screen.png", 'rb') as f: await update.message.reply_photo(f)

    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        if os.path.exists(LOG_FILE):
            with open(LOG_FILE, 'r') as f: logs = "".join(f.readlines()[-20:])
            await update.message.reply_text(f"📋 **Live Logs:**\n```\n{logs}\n```", parse_mode='Markdown')

async def post_init(application):
    bot_data = application.bot_data['instance']
    asyncio.create_task(bot_data.worker_loop())
    asyncio.create_task(bot_data.adb_heartbeat())

if __name__ == "__main__":
    if not TOKEN: exit(1)
    bot_inst = ImoTurboV10()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.bot_data['instance'] = bot_inst
    app.add_handler(CommandHandler("start", bot_inst.cmd_start))
    app.add_handler(CommandHandler("logs", bot_inst.cmd_logs))
    app.add_handler(CommandHandler("screen", bot_inst.cmd_screen))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u,c: [asyncio.create_task(bot_inst.number_queue.put(n)) for n in re.findall(r'\b\d{7,15}\b', u.message.text)] and u.message.reply_text("✅ Added to Turbo Queue.")))
    app.run_polling(drop_pending_updates=True)
