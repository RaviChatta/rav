import aiohttp
import asyncio
import pytz
import time
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client
from aiohttp import web
from route import web_server  # Import web server
from config import settings  # Configuration settings
from database.data import hyoshcoder  # Database functions
from dotenv import load_dotenv

load_dotenv()  # Load environment variables

# Load configuration
Config = settings
SUPPORT_CHAT = -1002072871676  # Support chat ID

class Bot(Client):
    def __init__(self):
        """Initialize the bot with Pyrogram settings."""
        super().__init__(
            name="autorename",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=20,
            plugins={"root": "plugins"},
            sleep_threshold=15,
        )
        self.start_time = time.time()

    async def start(self):
        """Start the bot and send restart notifications."""
        await super().start()
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        print(f"{me.first_name} has started... ✨️")

        # Uptime calculation
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        # Clear old user channel data
        await hyoshcoder.clear_all_user_channels()

        # Send restart message to log and support channels
        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')

                await self.send_photo(
                    chat_id=chat_id,
                    photo="https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg",
                    caption=(
                        "**Oops! The bot has restarted.**\n\n"
                        f"I haven't slept since: `{uptime_string}`"
                    )
                )
            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")

# Function to start services
async def start_services():
    bot = Bot()
    await bot.start()

    if Config.WEBHOOK:
        app = web.AppRunner(await web_server())
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", 8080)
        await site.start()

# Entry point
async def main():
    await start_services()

if __name__ == "__main__":
    asyncio.run(main())
