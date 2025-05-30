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
from database.data import initialize_database, hyoshcoder
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)
load_dotenv()

Config = settings
SUPPORT_CHAT = -1002072871676

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
        await super().start()
        await initialize_database()

        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        print(f"{me.first_name} has started... ✨️")

        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
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

        # Start auto-refresh leaderboard task
        asyncio.create_task(self.auto_refresh_leaderboards())

    async def auto_refresh_leaderboards(self):
        while True:
            try:
                await hyoshcoder.update_leaderboards()
                await asyncio.sleep(3600)  # Refresh every hour
            except Exception as e:
                logger.error(f"Error refreshing leaderboards: {e}")
                await asyncio.sleep(300)  # Retry after 5 minutes


async def start_services():
    bot = Bot()
    await bot.start()

    if Config.WEBHOOK:
        app = web.AppRunner(await web_server())
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", 8000)
        await site.start()

    try:
        await asyncio.Event().wait()  # Keep bot running
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("Shutting down...")
    finally:
        if Config.WEBHOOK:
            await site.stop()
            await app.cleanup()
        await bot.stop()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        pass
    finally:
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()
