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

class ImoCommandCenterV8:
    def __init__(self):
        self.number_queue = asyncio.Queue()
        self.clone_status = {i: "Idle" for i in range(1, 11)}
        self.processed_count = 0
        
        # Resource Intel
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        self.kvm_support = os.path.exists("/dev/kvm")
        self.mode = "SAFE" if total_ram_gb < 2 else "BALANCED" if total_ram_gb < 6 else "TURBO"
        self.max_parallel = 1 if total_ram_gb < 2 else 3 if total_ram_gb < 6 else 10
        self.concurrency_limit = asyncio.Semaphore(self.max_parallel)

    async def run_adb(self, command: str) -> str:
        process = await asyncio.create_subprocess_shell(
            f"adb {command}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        return stdout.decode().strip()

    async def get_user_id(self, clone_number: int) -> int:
        output = await self.run_adb("shell pm list users")
        for line in output.splitlines():
            if f"Clone_{clone_number}:" in line:
                try:
                    return int(line.split(":")[0].replace("UserInfo{", ""))
                except ValueError: return -1
        return -1

    async def worker_loop(self):
        while True:
            phone_number = await self.number_queue.get()
            clone_num = next((c for c, s in self.clone_status.items() if s == "Idle"), None)
            
            if not clone_num:
                await asyncio.sleep(5)
                await self.number_queue.put(phone_number)
                self.number_queue.task_done()
                continue

            user_id = await self.get_user_id(clone_num)
            if user_id == -1:
                await self.number_queue.put(phone_number)
                self.number_queue.task_done()
                await asyncio.sleep(10)
                continue

            async with self.concurrency_limit:
                self.clone_status[clone_num] = f"Processing {phone_number}"
                try:
                    if self.max_parallel == 1: await self.run_adb(f"shell am force-stop {PACKAGE}")
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(2)
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    await asyncio.sleep(15)
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

    # --- COMMAND CENTER v8.0 ---
    
    async def cmd_logs(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            if os.path.exists(LOG_FILE):
                with open(LOG_FILE, 'r') as f:
                    logs = f.readlines()[-20:]
                await update.message.reply_text(f"📋 **Last 20 Log Lines:**\n```\n{''.join(logs)}\n```", parse_mode='Markdown')
            else:
                await update.message.reply_text("❌ Log file not found yet.")
        except Exception as e: await update.message.reply_text(f"Error: {e}")

    async def cmd_screen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("📸 Capturing screen... (Software mode is slow)")
        try:
            # Use exec-out for direct pipe (faster)
            os.system(f"adb exec-out screencap -p > /app/screen.png")
            if os.path.getsize("/app/screen.png") > 0:
                with open("/app/screen.png", 'rb') as photo:
                    await update.message.reply_photo(photo, caption=f"🖼️ Emulator Screen (Mode: {self.mode})")
            else:
                await update.message.reply_text("❌ Failed to capture screen (Empty file).")
        except Exception as e: await update.message.reply_text(f"Error: {e}")

    async def cmd_check(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        focus = await self.run_adb("shell dumpsys window windows | grep -E 'mCurrentFocus'")
        if PACKAGE in focus:
            await update.message.reply_text(f"✅ **App State:** OPEN\n`{focus}`", parse_mode='Markdown')
        else:
            await update.message.reply_text(f"❌ **App State:** CLOSED\n`{focus}`", parse_mode='Markdown')

    async def cmd_reboot(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🔄 Rebooting Bot Controller...")
        os._exit(0) # Supervisor will restart the process

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        adb_devices = await self.run_adb("devices")
        adb_status = "✅ Online" if "device" in adb_devices.splitlines()[-1] else "⏳ Booting..."
        dashboard = (
            "🤖 **IMO Command Center (v8.0)**\n\n"
            f"⚙️ **Mode**: `{self.mode}` | 📡 **KVM**: {'✅' if self.kvm_support else '❌'}\n"
            f"📡 **ADB**: {adb_status} | 🧠 **RAM**: {psutil.virtual_memory().percent}%\n"
            f"📊 **Queue**: {self.number_queue.qsize()} | ✅ **Done**: {self.processed_count}\n\n"
            "**Super Commands:**\n"
            "🖼️ `/screen` - View Emulator Screen\n"
            "📋 `/logs` - View Live Logs\n"
            "🔍 `/check` - Check App Focus\n"
            "🔄 `/reboot` - Restart Bot"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        nums = re.findall(r'\b\d{7,15}\b', update.message.text)
        for n in nums: await self.number_queue.put(n)
        if nums: await update.message.reply_text(f"✅ {len(nums)} numbers added to Queue.")

async def post_init(application):
    asyncio.create_task(application.bot_data['bot_instance'].worker_loop())

if __name__ == "__main__":
    if not TOKEN: exit(1)
    bot = ImoCommandCenterV8()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.bot_data['bot_instance'] = bot
    app.add_handler(CommandHandler("start", bot.cmd_start))
    app.add_handler(CommandHandler("status", bot.cmd_start))
    app.add_handler(CommandHandler("logs", bot.cmd_logs))
    app.add_handler(CommandHandler("screen", bot.cmd_screen))
    app.add_handler(CommandHandler("check", bot.cmd_check))
    app.add_handler(CommandHandler("reboot", bot.cmd_reboot))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.run_polling()
