import aiohttp
import asyncio
import pytz
import time
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client
from pyrogram.types import User
from aiohttp import web
from route import web_server
from config import settings
from database.data import initialize_database, hyoshcoder
from dotenv import load_dotenv
import logging
from typing import Optional
from findanime import setup_anime_finder

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
        self.mention: Optional[str] = None
        self.username: Optional[str] = None
        self.uptime: Optional[str] = None
        self.web_app = None  # Add web app reference

    async def cleanup_tasks(self):
        """Handle periodic cleanup tasks"""
        while True:
            try:
                # Add your cleanup logic here
                await asyncio.sleep(3600)  # Run every hour
            except Exception as e:
                logger.error(f"Cleanup task error: {e}")
                await asyncio.sleep(300)

    async def auto_refresh_leaderboards(self):
        """Periodically refresh leaderboard data"""
        while True:
            try:
                await hyoshcoder.update_leaderboards()
                logger.info("Leaderboards refreshed successfully")
                await asyncio.sleep(3600)  # Refresh every hour
            except Exception as e:
                logger.error(f"Error refreshing leaderboards: {e}")
                await asyncio.sleep(300)  # Retry after 5 minutes

    async def start(self):
        await super().start()
        
        # Initialize database with the client reference
        await initialize_database()
        hyoshcoder.set_client(self)  # Pass the Pyrogram client to database

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
                    photo="https://files.catbox.moe/px9br5.png",
                    caption=(
                        "**Oops! The bot has restarted.**\n\n"
                        f"I haven't slept since: `{uptime_string}`"
                    )
                )
            except Exception as e:
                logger.error(f"Failed to send message in chat {chat_id}: {e}")

        # Start background tasks
        asyncio.create_task(self.auto_refresh_leaderboards())
        asyncio.create_task(self.cleanup_tasks())

async def post_init(bot):
    """Initialize additional services"""
    try:
        # Initialize anime finder with the bot instance
        await setup_anime_finder(bot)
        logger.info("Anime finder initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize anime finder: {e}")
        raise

async def start_services():
    """Start all bot services"""
    bot = Bot()
    await bot.start()

    if Config.WEBHOOK:
        try:
            app = web.Application()
            app.router.add_routes(await web_server())
            runner = web.AppRunner(app)
            await runner.setup()
            site = web.TCPSite(runner, "0.0.0.0", 8000)
            await site.start()
            bot.web_app = app  # Store reference
            logger.info("Web server started successfully")
        except Exception as e:
            logger.error(f"Failed to start web server: {e}")

    try:
        await post_init(bot)  # Initialize additional services
        await asyncio.Event().wait()  # Keep bot running
    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received")
    finally:
        logger.info("Cleaning up before shutdown...")
        if Config.WEBHOOK and bot.web_app:
            try:
                await runner.cleanup()
            except Exception as e:
                logger.error(f"Error during web server cleanup: {e}")
        await bot.stop()
        logger.info("Bot shutdown complete")

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log')
        ]
    )

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        logger.info("Starting bot services...")
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.critical(f"Fatal error: {e}", exc_info=True)
    finally:
        logger.info("Shutting down event loop...")
        # Cancel all pending tasks
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()
        
        # Gather all tasks and handle exceptions
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception as e:
            logger.error(f"Error during task cancellation: {e}")
        
        loop.close()
        logger.info("Event loop closed. Bot shutdown complete.")
