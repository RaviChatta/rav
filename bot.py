import aiohttp
import asyncio
import pytz
import time
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client
from aiohttp import web
from route import web_server
from config import settings
from database.data import hyoshcoder
from dotenv import load_dotenv

load_dotenv()

Config = settings
SUPPORT_CHAT = -1002072871676

async def initialize_database():
    """Initialize the database connection"""
    try:
        await hyoshcoder.connect()
        print("✅ Database connection established")
    except Exception as e:
        print(f"❌ Failed to connect to database: {e}")
        raise

class Bot(Client):
    def __init__(self):
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
        """Starts the bot and initializes the database"""
        await initialize_database()

        # Start the bot normally
        await super().start()

        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        print(f"{me.first_name} has started... ✨️")

        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        await hyoshcoder.clear_all_user_channels()

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')

                await self.send_photo(
                    chat_id=chat_id,
                    photo="https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg",
                    caption=(f"**Oops! The bot has restarted.**\n\n"
                              f"I haven't slept since: `{uptime_string}`")
                )
            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")

    async def stop(self):
        """Gracefully stop the bot"""
        try:
            print(f"Stopping bot {self.username}...")
            await super().stop()  # Ensure proper bot shutdown
        except Exception as e:
            print(f"Error during bot shutdown: {e}")

async def start_services():
    """Start the bot and the web server if necessary"""
    bot = Bot()
    await bot.start()

    if Config.WEBHOOK:
        # Set up the web server if needed
        app = web.AppRunner(await web_server())
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", 8080)
        await site.start()

    # Keep the bot running (this line keeps it alive indefinitely)
    await asyncio.Event().wait()

async def graceful_shutdown(bot: Bot):
    """Handle graceful shutdown of the bot"""
    print("Gracefully shutting down...")
    await bot.stop()

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    bot = None
    try:
        # Run the bot and server
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        # Handle graceful shutdown on KeyboardInterrupt
        print("Shutting down bot due to KeyboardInterrupt...")
    except Exception as e:
        print(f"Bot crashed with error: {e}")
    finally:
        # Ensure graceful shutdown if the bot was initialized
        if bot:
            loop.run_until_complete(graceful_shutdown(bot))
        loop.close()  # Close the event loop properly after shutdown
