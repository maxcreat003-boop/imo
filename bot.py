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
        self.screen_lock = asyncio.Lock()  # Android can only have 1 foreground app at a time
        self.processed_count = 0

    async def run_adb(self, command: str) -> str:
        """Asynchronous execution of ADB commands."""
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
        """
        Executes the UI taps. 
        NOTE: These input keyevents/taps are generic placeholders. 
        We will refine them once we see the exact IMO app screen.
        """
        # Wait for app to fully load
        await asyncio.sleep(5)
        
        # Example UI Flow (Using D-PAD and Keyboard emulation for maximum compatibility)
        logging.info(f"Typing number: {phone_number}")
        
        # 1. Type the phone number
        await self.run_adb(f"shell input text {phone_number}")
        await asyncio.sleep(1)
        
        # 2. Press Enter/Next
        await self.run_adb("shell input keyevent 66") # KEYCODE_ENTER
        await asyncio.sleep(2)
        
        # 3. Handle 'Confirm Number' popup if it exists (Press TAB then ENTER to click OK)
        await self.run_adb("shell input keyevent 22") # KEYCODE_DPAD_RIGHT
        await asyncio.sleep(0.5)
        await self.run_adb("shell input keyevent 66") # KEYCODE_ENTER
        
        # 4. Wait for OTP page to load
        await asyncio.sleep(4)

    async def worker_loop(self):
        """Background worker that continuously processes the queue."""
        while True:
            phone_number = await self.number_queue.get()
            
            # Find an available clone
            clone_num = None
            while not clone_num:
                clone_num = self.get_available_clone()
                if not clone_num:
                    await asyncio.sleep(2) # Wait for a clone to become free
            
            user_id = await self.get_user_id(clone_num)
            if user_id == -1:
                self.number_queue.task_done()
                continue

            self.clone_status[clone_num] = f"Processing {phone_number}"
            logging.info(f"Clone_{clone_num} took number {phone_number}")

            # Because Android only has ONE screen, we must lock the foreground interaction
            async with self.screen_lock:
                try:
                    # 1. Clear Data before starting
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
                    await asyncio.sleep(1)
                    
                    # 2. Open IMO
                    await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
                    
                    # 3. Perform UI Automation
                    await self.automate_ui_flow(phone_number)
                    
                except Exception as e:
                    logging.error(f"Error processing {phone_number}: {e}")
                finally:
                    # 4. Force Stop and Clear Data immediately after reaching OTP page
                    await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
                    await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
            
            self.processed_count += 1
            self.clone_status[clone_num] = "Idle"
            self.number_queue.task_done()
            logging.info(f"Successfully processed and cleared number {phone_number} on Clone_{clone_num}")

    async def handle_text(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extracts numbers from plain text messages."""
        text = update.message.text
        # Extract all sequences of 7 to 15 digits
        numbers = re.findall(r'\b\d{7,15}\b', text)
        
        if not numbers:
            return

        for num in numbers:
            await self.number_queue.put(num)
            
        await update.message.reply_text(f"✅ Added {len(numbers)} numbers to the automation queue.\nTotal in queue: {self.number_queue.qsize()}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Extracts numbers from uploaded .txt files."""
        file = await context.bot.get_file(update.message.document.file_id)
        file_path = "temp_numbers.txt"
        await file.download_to_drive(file_path)
        
        count = 0
        with open(file_path, 'r') as f:
            for line in f:
                numbers = re.findall(r'\b\d{7,15}\b', line)
                for num in numbers:
                    await self.number_queue.put(num)
                    count += 1
                    
        os.remove(file_path)
        await update.message.reply_text(f"📄 File processed! Added {count} numbers to the queue.\nTotal in queue: {self.number_queue.qsize()}")

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        active_clones = sum(1 for s in self.clone_status.values() if s != "Idle")
        
        dashboard = (
            "🤖 **IMO Fully Auto Bot (v5.0)**\n\n"
            f"💻 **CPU**: {cpu}% | 🧠 **RAM**: {ram}%\n"
            f"📊 **Queue Size**: {self.number_queue.qsize()} numbers pending\n"
            f"✅ **Total Processed**: {self.processed_count}\n"
            f"🔥 **Active Clones**: {active_clones}/10\n\n"
            "**How to use:**\n"
            "1. Just type numbers here: `9876543210`\n"
            "2. Or upload a `.txt` file with numbers.\n"
            "The bot will automatically pick them up, enter them, reach OTP, and clear data."
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

    # Keep manual commands for debugging
    async def cmd_clone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            clone_num = int(context.args[0])
            user_id = await self.get_user_id(clone_num)
            await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
            await update.message.reply_text(f"✅ Launched Clone_{clone_num} manually.")
        except:
            await update.message.reply_text("❌ Usage: `/clone <1-10>`")

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            clone_num = int(context.args[0])
            user_id = await self.get_user_id(clone_num)
            await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
            await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
            await update.message.reply_text(f"🧹 Manually cleared Clone_{clone_num}.")
        except:
            await update.message.reply_text("❌ Usage: `/reset <1-10>`")


async def main():
    if not TOKEN:
        logging.error("BOT_TOKEN is not set.")
        return

    bot_instance = ImoBotV5()
    
    # Start the background worker
    asyncio.create_task(bot_instance.worker_loop())

    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", bot_instance.cmd_start))
    app.add_handler(CommandHandler("status", bot_instance.cmd_start))
    app.add_handler(CommandHandler("clone", bot_instance.cmd_clone))
    app.add_handler(CommandHandler("reset", bot_instance.cmd_reset))
    
    # Fully automatic handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, bot_instance.handle_text))
    app.add_handler(MessageHandler(filters.Document.TXT, bot_instance.handle_document))

    logging.info("Telegram Controller Started Successfully.")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
