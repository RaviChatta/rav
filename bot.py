import aiohttp
import asyncio
import pytz
import time
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client, filters
from pyrogram.types import Message
from aiohttp import web
from route import web_server
from config import settings
#from plugins.callback import start_cleanup
#from plugins.rename import startup_tasks
from database.data import initialize_database, hyoshcoder
from dotenv import load_dotenv
import logging
from typing import Optional
from findanime import AnimeFinder
import os
import sys


logger = logging.getLogger(__name__)
load_dotenv()

Config = settings
pyrogram.utils.MIN_CHANNEL_ID = -1009147483647

# Setting SUPPORT_CHAT properly
SUPPORT_CHAT = int(os.environ.get("SUPPORT_CHAT", str(Config.LOG_CHANNEL)))


class Bot(Client):
    def __init__(self):
        super().__init__(
            name="autorename",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=8,
            plugins={"root": "plugins"},
            sleep_threshold=30,
        )
        self.start_time = time.time()
        self.mention: Optional[str] = None
        self.username: Optional[str] = None
        self.uptime: Optional[str] = None
        self.web_app = None
        self.runner = None
        self.anime_finder: Optional[AnimeFinder] = None
        self.is_anime_finder_enabled = Config.ANIME_FINDER_ENABLED if hasattr(Config, 'ANIME_FINDER_ENABLED') else True

    async def startup_tasks(self):
        """Run background tasks"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
                # Add your cleanup tasks here
                logger.info("Running periodic cleanup tasks")
            except Exception as e:
                logger.error(f"Error in startup tasks: {e}")
                await asyncio.sleep(300)

    async def cleanup_tasks(self):
        """Handle periodic cleanup tasks"""
        while True:
            try:
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Cleanup task error: {e}", exc_info=False)
                await asyncio.sleep(300)

    async def auto_refresh_leaderboards(self):
        """Periodically refresh leaderboard data"""
        while True:
            try:
                await hyoshcoder.update_leaderboards()
                logger.info("Leaderboards refreshed successfully")
                await asyncio.sleep(3600)
            except Exception as e:
                logger.error(f"Error refreshing leaderboards: {e}", exc_info=False)
                await asyncio.sleep(300)
    async def check_premium_expiry_task(client: Client):
        """Background task to check for expired premium users"""
        while True:
            try:
                await hyoshcoder.check_premium_expiry()
                await asyncio.sleep(3600)  # Check every hour
            except Exception as e:
                logger.error(f"Premium expiry check error: {e}")
                await asyncio.sleep(600)  # Wait 10 minutes before retrying if error occurs
    async def initialize_anime_finder(self):
        if not self.is_anime_finder_enabled:
            return
    
        self.anime_finder = AnimeFinder(self)
        await self.anime_finder.initialize()
        asyncio.create_task(self.anime_finder.adaptive_queue_processor())

    async def start(self):
        await super().start()
        
        await initialize_database()
        hyoshcoder.set_client(self)
        me = await self.get_me()
        self.mention = me.mention
        self.username = me.username
        self.uptime = Config.BOT_UPTIME

        logger.info(f"{me.first_name} has started... ✨️")

        # Initialize anime finder
        anime_finder_status = await self.initialize_anime_finder()

        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                curr = datetime.now(timezone("Asia/Kolkata"))
                caption = (
                     "**ʜᴀɴᴄᴏᴄᴋ ɪs ʀᴇsᴛᴀʀᴛᴇᴅ ᴀɢᴀɪɴ  !**\n\n"
                     f"ɪ ᴅɪᴅɴ'ᴛ sʟᴇᴘᴛ sɪɴᴄᴇ​: `{uptime_string}`"
                ),
                reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("ᴜᴘᴅᴀᴛᴇs", url="https://t.me/TFIBOTS")
                        ]]
                )
                
                if hasattr(Config, 'ANIME_FINDER_ENABLED'):
                    caption += f"Anime Finder: {'✅ Enabled' if anime_finder_status else '❌ Disabled'}\n"
                
                await self.send_photo(
                    chat_id=chat_id,
                    photo="https://files.catbox.moe/px9br5.png",
                    caption=caption
                )
            except Exception as e:
                logger.error(f"Failed to send message in chat {chat_id}: {e}", exc_info=False)

        # Start background tasks
        asyncio.create_task(self.auto_refresh_leaderboards())
        asyncio.create_task(self.cleanup_tasks())
        asyncio.create_task(self.check_premium_expiry_task())  # Changed this line
        logger.info("Premium expiry checker started")

     #   asyncio.create_task(self.startup_tasks())

    async def stop(self, *args):
        """Cleanup before shutdown"""
        logger.info("Starting cleanup process...")
        
        # Cleanup anime finder
        if self.anime_finder:
            try:
                await self.anime_finder.shutdown()
                logger.info("Anime finder shutdown successfully")
            except Exception as e:
                logger.error(f"Error shutting down anime finder: {e}", exc_info=True)
        
        # Cleanup web server if running
        if Config.WEBHOOK and self.runner:
            try:
                await self.runner.cleanup()
                logger.info("Web server shutdown successfully")
            except Exception as e:
                logger.error(f"Error during web server cleanup: {e}", exc_info=False)
        
        await super().stop()
        logger.info("Bot shutdown complete")

async def start_services():
    """Start all bot services"""
    bot = Bot()
    
    try:
        await bot.start()

        if Config.WEBHOOK:
            try:
                app = web.Application()
                app.router.add_routes(await web_server())
                bot.runner = web.AppRunner(app)
                await bot.runner.setup()
                site = web.TCPSite(bot.runner, "0.0.0.0", 8000)
                await site.start()
                bot.web_app = app
                logger.info("Web server started successfully")
            except Exception as e:
                logger.error(f"Failed to start web server: {e}", exc_info=False)

        # Keep the bot running
        await asyncio.Event().wait()

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        await bot.stop()

if __name__ == "__main__":
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )

    # Set recursion limit
    sys.setrecursionlimit(10000)

    # Create and run event loop
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    try:
        logger.info("Starting bot services...")
        loop.run_until_complete(start_services())
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup tasks
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()
        
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        
        loop.close()
        logger.info("Event loop closed. Bot shutdown complete.")
