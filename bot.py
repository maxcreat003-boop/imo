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

class ImoBotV5:
    def __init__(self):
        self.number_queue = asyncio.Queue()
        self.clone_status = {i: "Idle" for i in range(1, 11)}
        self.screen_lock = asyncio.Lock()
        self.processed_count = 0

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

    def get_available_clone(self):
        for clone_num, status in self.clone_status.items():
            if status == "Idle":
                return clone_num
        return None

    async def automate_ui_flow(self, phone_number: str):
        await asyncio.sleep(5)
        logging.info(f"Typing number: {phone_number}")
        await self.run_adb(f"shell input text {phone_number}")
        await asyncio.sleep(2)
        await self.run_adb("shell input keyevent 66") 
        await asyncio.sleep(3)
        await self.run_adb("shell input keyevent 22") 
        await asyncio.sleep(1)
        await self.run_adb("shell input keyevent 66") 
        await asyncio.sleep(5)

    async def worker_loop(self):
        while True:
            phone_number = await self.number_queue.get()
            clone_num = None
            
            while not clone_num:
                clone_num = self.get_available_clone()
                if not clone_num:
                    await asyncio.sleep(5)
            
            user_id = await self.get_user_id(clone_num)
            if user_id == -1:
                logging.warning(f"Clone_{clone_num} not ready. Re-queuing number.")
                await self.number_queue.put(phone_number)
                self.number_queue.task_done()
                await asyncio.sleep(10)
                continue

            self.clone_status[clone_num] = f"Processing {phone_number}"
            async with self.screen_lock:
                try:
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(2)
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    await self.automate_ui_flow(phone_number)
                except Exception as e:
                    logging.error(f"Error processing {phone_number}: {e}")
                finally:
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
            
            self.processed_count += 1
            self.clone_status[clone_num] = "Idle"
            self.number_queue.task_done()

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        text = update.message.text
        numbers = re.findall(r'\b\d{7,15}\b', text)
        if not numbers: return
        for num in numbers:
            await self.number_queue.put(num)
        await update.message.reply_text(f"✅ Added {len(numbers)} numbers. Total in queue: {self.number_queue.qsize()}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = "temp_numbers.txt"
        await file.download_to_drive(file_path)
        count = 0
        with open(file_path, 'r', encoding='utf-8') as f:
            for line in f:
                numbers = re.findall(r'\b\d{7,15}\b', line)
                for num in numbers:
                    await self.number_queue.put(num); count += 1
        os.remove(file_path)
        await update.message.reply_text(f"📄 Added {count} numbers from file.")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        # ADB Check
        adb_devices = await self.run_adb("devices")
        adb_status = "✅ Online" if "device" in adb_devices.splitlines()[-1] else "⏳ Booting (Software Mode)..."
        
        active_clones = sum(1 for s in self.clone_status.values() if s != "Idle")
        ready_clones = 0
        for i in range(1, 11):
            if await self.get_user_id(i) != -1: ready_clones += 1

        dashboard = (
            "🤖 **IMO Fully Auto Bot (v5.5)**\n\n"
            f"📡 **ADB**: {adb_status}\n"
            f"💻 **CPU**: {cpu}% | 🧠 **RAM**: {ram}%\n"
            f"📊 **Queue**: {self.number_queue.qsize()} | ✅ **Total**: {self.processed_count}\n"
            f"🔥 **Clones Ready**: {ready_clones}/10"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

async def post_init(application):
    bot_instance = application.bot_data['bot_instance']
    asyncio.create_task(bot_instance.worker_loop())

if __name__ == "__main__":
    if not TOKEN:
        print("BOT_TOKEN missing"); exit(1)
    bot_instance = ImoBotV5()
    application = ApplicationBuilder().token(TOKEN).post_init(post_init).build()
    application.bot_data['bot_instance'] = bot_instance
    application.add_handler(CommandHandler("start", bot_instance.cmd_start))
    application.add_handler(CommandHandler("status", bot_instance.cmd_start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_text))
    app.add_handler(MessageHandler(filters.Document.TXT, bot_instance.handle_document))
    application.run_polling()
