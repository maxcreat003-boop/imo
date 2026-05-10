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

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ImoAdaptiveBotV7:
    def __init__(self):
        self.number_queue = asyncio.Queue()
        self.clone_status = {i: "Idle" for i in range(1, 11)}
        self.processed_count = 0
        
        # --- Adaptive Resource Intelligence ---
        total_ram_gb = psutil.virtual_memory().total / (1024**3)
        self.kvm_support = os.path.exists("/dev/kvm")
        
        if total_ram_gb < 2:
            self.mode = "SAFE (Low Resource)"
            self.max_parallel = 1
            self.boot_delay = 15
        elif total_ram_gb < 6:
            self.mode = "BALANCED"
            self.max_parallel = 3
            self.boot_delay = 5
        else:
            self.mode = "TURBO (High Performance)"
            self.max_parallel = 10
            self.boot_delay = 2

        self.concurrency_limit = asyncio.Semaphore(self.max_parallel)
        logging.info(f"[v7.0] Detected {total_ram_gb:.2f}GB RAM. Mode: {self.mode}. KVM: {self.kvm_support}")

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
                except ValueError:
                    return -1
        return -1

    async def worker_loop(self):
        while True:
            phone_number = await self.number_queue.get()
            
            # Find an available clone
            clone_num = None
            for c, s in self.clone_status.items():
                if s == "Idle":
                    clone_num = c
                    break
            
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
                    # In SAFE mode, force stop everything else before starting
                    if self.max_parallel == 1:
                        await self.run_adb(f"shell am force-stop {PACKAGE}")
                    
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(2)
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    
                    # UI Automation (Staggered by mode)
                    await asyncio.sleep(self.boot_delay + 5)
                    await self.run_adb(f"shell input text {phone_number}")
                    await asyncio.sleep(2)
                    await self.run_adb("shell input keyevent 66") # ENTER
                    await asyncio.sleep(5)
                    
                except Exception as e:
                    logging.error(f"Error: {e}")
                finally:
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
                    self.clone_status[clone_num] = "Idle"
                    self.processed_count += 1
                    self.number_queue.task_done()

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        numbers = re.findall(r'\b\d{7,15}\b', update.message.text)
        for num in numbers: await self.number_queue.put(num)
        if numbers: await update.message.reply_text(f"✅ Added {len(numbers)} numbers. Mode: {self.mode}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = "numbers.txt"
        await file.download_to_drive(file_path)
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                nums = re.findall(r'\b\d{7,15}\b', line)
                for n in nums: await self.number_queue.put(n); count += 1
        os.remove(file_path)
        await update.message.reply_text(f"📄 {count} numbers queued. System running in {self.mode} mode.")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cpu = psutil.cpu_percent()
        ram_perc = psutil.virtual_memory().percent
        adb_devices = await self.run_adb("devices")
        adb_status = "✅ Online" if "device" in adb_devices.splitlines()[-1] else "⏳ Booting..."
        
        dashboard = (
            "🤖 **IMO Adaptive Intelligence (v7.0)**\n\n"
            f"⚙️ **System Mode**: `{self.mode}`\n"
            f"📡 **KVM Hardware**: {'✅ Supported' if self.kvm_support else '❌ Software Emulation'}\n"
            f"📱 **Max Parallel**: {self.max_parallel} clones\n\n"
            f"📡 **ADB Status**: {adb_status}\n"
            f"💻 **CPU**: {cpu}% | 🧠 **RAM**: {ram_perc}%\n"
            f"📊 **Queue**: {self.number_queue.qsize()} | ✅ **Total**: {self.processed_count}"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

async def post_init(application):
    asyncio.create_task(application.bot_data['bot_instance'].worker_loop())

if __name__ == "__main__":
    if not TOKEN: exit(1)
    bot = ImoAdaptiveBotV7()
    app = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    app.bot_data['bot_instance'] = bot
    app.add_handler(CommandHandler("start", bot.cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot.handle_text))
    app.add_handler(MessageHandler(filters.Document.TXT, bot.handle_document))
    app.run_polling()
