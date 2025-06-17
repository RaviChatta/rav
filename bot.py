import aiohttp
import asyncio
import pytz
import time
import logging
import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from pytz import timezone
from pyrogram import Client
from pyrogram.errors import FloodWait
from aiohttp import web
from route import web_server
from config import settings
from database.data import initialize_database, hyoshcoder
from findanime import AnimeFinder
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

Config = settings
SUPPORT_CHAT = -1002563598431

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
            max_concurrent_transmissions=4,
            in_memory=True,
            takeout=True
        )
        self.start_time = time.time()
        self.mention: Optional[str] = None
        self.username: Optional[str] = None
        self.uptime: Optional[str] = None
        self.web_app = None
        self.runner = None
        self.anime_finder: Optional[AnimeFinder] = None
        self.is_anime_finder_enabled = Config.ANIME_FINDER_ENABLED if hasattr(Config, 'ANIME_FINDER_ENABLED') else True
        self._flood_wait_times = {}
        self._last_request_time = 0
        self._request_interval = 0.1  # Start with 100ms between requests

    async def _smart_request(self, method, *args, **kwargs):
        """Smart request handler with auto flood control"""
        while True:
            try:
                # Enforce minimum interval between requests
                since_last = time.time() - self._last_request_time
                if since_last < self._request_interval:
                    await asyncio.sleep(self._request_interval - since_last)
                
                self._last_request_time = time.time()
                return await method(*args, **kwargs)
                
            except FloodWait as e:
                wait_time = e.value + 1  # Add 1 second buffer
                self._flood_wait_times[time.time()] = wait_time
                
                # Calculate new safe interval based on recent waits
                recent_waits = [t for ts, t in self._flood_wait_times.items() 
                              if time.time() - ts < 300]  # Last 5 minutes
                if recent_waits:
                    self._request_interval = max(0.1, min(recent_waits) / 2)
                
                await asyncio.sleep(wait_time)
                continue
                
            except Exception as e:
                raise e

    async def turbo_download(self, message, file_path, progress_callback=None):
        """Flood-protected turbo download"""
        async def _download():
            return await super().download_media(
                message,
                file_name=file_path,
                block=False,
                chunk_size=1024*1024*8,  # 8MB chunks
                max_retries=3,
                read_timeout=30,
                write_timeout=30,
                no_progress=True
            )
        
        return await self._smart_request(_download)

    async def turbo_upload(self, chat_id, file_path, **kwargs):
        """Flood-protected turbo upload"""
        async def _upload():
            return await super().send_document(
                chat_id,
                document=file_path,
                chunk_size=1024*1024*8,  # 8MB chunks
                disable_notification=True,
                disable_content_type_detection=True,
                allow_cache=False,
                read_timeout=30,
                write_timeout=30,
                **kwargs
            )
        
        return await self._smart_request(_upload)

    async def startup_tasks(self):
        """Run background tasks"""
        while True:
            try:
                await asyncio.sleep(3600)  # Run every hour
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

    async def monitor_flood_limits(self):
        """Continuously adjust request rates based on flood history"""
        while True:
            recent_waits = [t for ts, t in self._flood_wait_times.items()
                          if time.time() - ts < 600]
            
            if recent_waits:
                avg_wait = sum(recent_waits) / len(recent_waits)
                self._request_interval = min(2, max(0.1, avg_wait / 2))
            
            await asyncio.sleep(60)

    async def initialize_anime_finder(self):
        if not self.is_anime_finder_enabled:
            return
    
        self.anime_finder = AnimeFinder(self)
        await self.anime_finder.initialize()
        asyncio.create_task(self.anime_finder.adaptive_queue_processor())
        return True

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
                    "**Oops! The bot has restarted.**\n\n"
                    f"I haven't slept since: `{uptime_string}`\n"
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
        asyncio.create_task(self.monitor_flood_limits())

    async def stop(self, *args):
        """Cleanup before shutdown"""
        logger.info("Starting cleanup process...")
        
        if self.anime_finder:
            try:
                await self.anime_finder.shutdown()
                logger.info("Anime finder shutdown successfully")
            except Exception as e:
                logger.error(f"Error shutting down anime finder: {e}", exc_info=True)
        
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

        await asyncio.Event().wait()

    except (asyncio.CancelledError, KeyboardInterrupt):
        logger.info("Shutdown signal received")
    except Exception as e:
        logger.error(f"Fatal error in main loop: {e}", exc_info=True)
    finally:
        await bot.stop()

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('bot.log', encoding='utf-8')
        ]
    )

    sys.setrecursionlimit(10000)

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
        pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
        for task in pending:
            task.cancel()
        
        try:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        except Exception:
            pass
        
        loop.close()
        logger.info("Event loop closed. Bot shutdown complete.")
