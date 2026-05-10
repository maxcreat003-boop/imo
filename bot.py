import os
import asyncio
import logging
import psutil
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)
from dotenv import load_dotenv

# Configuration
load_dotenv()
TOKEN = os.getenv("BOT_TOKEN")
PACKAGE = "com.imo.android.imoimlite"
ACTIVITY = "com.imo.android.imo.activities.HomeActivity"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')

class ImoBotV4:
    def __init__(self):
        self.user_slots = {i: None for i in range(1, 11)}

    async def run_adb(self, command: str) -> str:
        """Asynchronous execution of ADB commands to prevent blocking."""
        process = await asyncio.create_subprocess_shell(
            f"adb {command}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            logging.error(f"ADB Error: {stderr.decode().strip()}")
            return ""
        return stdout.decode().strip()

    async def get_user_id(self, clone_number: int) -> int:
        """Dynamically fetch the Android User ID for a given clone."""
        output = await self.run_adb("shell pm list users")
        for line in output.splitlines():
            if f"Clone_{clone_number}:" in line:
                try:
                    return int(line.split(":")[0].replace("UserInfo{", ""))
                except ValueError:
                    return -1
        return -1

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Dashboard heartbeat to confirm the bot is connected."""
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        
        # Test ADB connection silently
        adb_devices = await self.run_adb("devices")
        adb_status = "✅ Connected" if "emulator" in adb_devices or "localhost:5555" in adb_devices else "❌ Disconnected"

        dashboard = (
            "🤖 **IMO Automation Bot - System Status (v4.0)**\n\n"
            f"📡 **ADB Status**: {adb_status}\n"
            f"💻 **CPU Usage**: {cpu}%\n"
            f"🧠 **RAM Usage**: {ram}%\n"
            f"👥 **Profiles Configured**: 10\n\n"
            "**Commands:**\n"
            "▶️ `/clone <1-10>` - Launch IMO for a profile\n"
            "🔄 `/reset <1-10>` - Close app and clear data for next number"
        )
        await update.message.reply_text(dashboard, parse_mode='Markdown')

    async def cmd_clone(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Launch a specific clone profile."""
        try:
            clone_num = int(context.args[0])
            if clone_num < 1 or clone_num > 10:
                raise ValueError
        except (IndexError, ValueError):
            await update.message.reply_text("❌ Usage: `/clone <1-10>`", parse_mode='Markdown')
            return

        user_id = await self.get_user_id(clone_num)
        if user_id == -1:
            await update.message.reply_text(f"❌ Clone_{clone_num} user profile not found. Did the startup script complete?", parse_mode='Markdown')
            return

        # Start the IMO application for the specific user
        await self.run_adb(f"shell am start --user {user_id} -n {PACKAGE}/{ACTIVITY}")
        self.user_slots[clone_num] = "Active"
        
        await update.message.reply_text(f"✅ Launched IMO for Clone_{clone_num} (Android User ID: {user_id}).")

    async def cmd_reset(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Force stop and clear data for a specific clone to prepare for the next number."""
        try:
            clone_num = int(context.args[0])
            if clone_num < 1 or clone_num > 10:
                raise ValueError
        except (IndexError, ValueError):
            await update.message.reply_text("❌ Usage: `/reset <1-10>`", parse_mode='Markdown')
            return

        user_id = await self.get_user_id(clone_num)
        if user_id == -1:
            await update.message.reply_text(f"❌ Clone_{clone_num} user profile not found.", parse_mode='Markdown')
            return

        # Force stop the app
        await self.run_adb(f"shell am force-stop --user {user_id} {PACKAGE}")
        # Clear app data
        await self.run_adb(f"shell pm clear --user {user_id} {PACKAGE}")
        
        self.user_slots[clone_num] = "Cleared"
        await update.message.reply_text(f"🧹 **Data Cleared!** Clone_{clone_num} is now completely reset and ready for a fresh new number.", parse_mode='Markdown')

async def main():
    if not TOKEN:
        logging.error("BOT_TOKEN is not set in the environment.")
        return

    bot_instance = ImoBotV4()
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", bot_instance.cmd_start))
    app.add_handler(CommandHandler("status", bot_instance.cmd_start))
    app.add_handler(CommandHandler("clone", bot_instance.cmd_clone))
    app.add_handler(CommandHandler("reset", bot_instance.cmd_reset))

    logging.info("Telegram Controller Started Successfully.")
    await app.run_polling()

if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    asyncio.run(main())
