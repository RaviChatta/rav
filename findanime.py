import asyncio
import psutil
from collections import deque
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.enums import ParseMode, ChatAction
from typing import Dict, Optional
import logging
import aiohttp
from io import BytesIO

logger = logging.getLogger(__name__)

TRACE_MOE_KEY = None  # Set your API key if needed
ANILIST_API = "https://graphql.anilist.co"
CPU_THRESHOLD = 80
MAX_QUEUE_SIZE = 20
REQUEST_TIMEOUT = 30

REQUEST_QUEUE = deque(maxlen=MAX_QUEUE_SIZE)
ACTIVE_TASKS = set()

class AnimeFinder:
    def __init__(self, bot: Client):
        self.bot = bot
        self.session = None
        self._handler = None  # To keep reference to the handler

    async def initialize(self):
        """Initialize aiohttp session"""
        self.session = aiohttp.ClientSession()
        self.register_handlers()

    async def shutdown(self):
        """Cleanup resources"""
        if self.session:
            await self.session.close()
        if self._handler:
            self.bot.remove_handler(*self._handler)

    def get_system_load(self) -> float:
        """Get current system CPU load"""
        return psutil.cpu_percent(interval=1)

    async def adaptive_queue_processor(self):
        """Smart queue that adjusts based on system load"""
        logger.info("Starting anime finder queue processor")
        while True:
            try:
                if REQUEST_QUEUE:
                    current_load = self.get_system_load()
                    
                    if current_load < CPU_THRESHOLD:
                        task = REQUEST_QUEUE.popleft()
                        if task['message_id'] not in ACTIVE_TASKS:
                            ACTIVE_TASKS.add(task['message_id'])
                            asyncio.create_task(self.process_anime_request(task))
                    
                    await asyncio.sleep(0.5 if current_load > CPU_THRESHOLD else 0.1)
                else:
                    await asyncio.sleep(1)
            except Exception as e:
                logger.error(f"Queue processor error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def turbo_search(self, image_data: bytes) -> Optional[Dict]:
        """Anime detection with retries and timeout"""
        headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
        
        for attempt in range(3):
            try:
                form_data = aiohttp.FormData()
                form_data.add_field('image', image_data, filename='image.jpg')
                
                async with self.session.post(
                    "https://api.trace.moe/search",
                    data=form_data,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Attempt {attempt+1} failed: HTTP {resp.status}")
            except Exception as e:
                logger.error(f"Attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    return None
                await asyncio.sleep(1)
        return None

    async def fetch_anilist(self, anilist_id: int) -> Dict:
        """Fetch anime metadata from AniList"""
        query = """query($id: Int) {
            Media(id: $id, type: ANIME) {
                title { romaji english }
                episodes
                siteUrl
                coverImage { large }
            }
        }"""
        
        for attempt in range(3):
            try:
                async with self.session.post(
                    ANILIST_API,
                    json={'query': query, 'variables': {'id': anilist_id}},
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('data', {}).get('Media', {})
                    logger.error(f"AniList attempt {attempt+1} failed: HTTP {resp.status}")
            except Exception as e:
                logger.error(f"AniList attempt {attempt+1} failed: {e}")
                if attempt == 2:
                    return {}
                await asyncio.sleep(1)
        return {}

    def format_response(self, data: Dict) -> str:
        """Format the anime information into a nice message"""
        title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown')
        is_movie = data.get('episodes', 0) == 1
        
        return (
            f"╔══════════════════════════╗\n"
            f"  🎬 <b>{title}</b>\n"
            f"╚══════════════════════════╝\n"
            f"• {'🎥 Movie' if is_movie else f'📺 Episode: {data.get("episode", "N/A")}'}\n"
            f"• ⏱ <b>Timestamp:</b> {data.get('timestamp', '00:00')}\n"
            f"• 📊 <b>Confidence:</b> {data.get('confidence', 0):.1f}%\n"
            f"• 🔗 <a href='{data.get('anilist_url', '#')}'>More Info</a>"
        )

    async def process_anime_request(self, task: Dict):
        """Process each anime search request"""
        try:
            message = await self.bot.get_messages(task['chat_id'], task['message_id'])
            if not message or not message.reply_to_message:
                logger.warning("Original message not found")
                return

            # Validate image content
            if not (message.reply_to_message.photo or 
                   (message.reply_to_message.document and 
                    message.reply_to_message.document.mime_type.startswith('image/'))):
                await message.reply_text("❌ Please reply to an image with /findanime")
                return

            # Download image
            await self.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
            try:
                image_data = BytesIO()
                file_id = (message.reply_to_message.photo.file_id if message.reply_to_message.photo 
                          else message.reply_to_message.document.file_id)
                await self.bot.download_media(file_id, file_name=image_data)
                image_bytes = image_data.getvalue()
            except Exception as e:
                logger.error(f"Image download failed: {e}")
                await message.reply_text("❌ Failed to download image")
                return

            if not image_bytes:
                await message.reply_text("❌ Empty image received")
                return

            # Search for anime
            trace_data = await self.turbo_search(image_bytes)
            if not trace_data or not trace_data.get('result'):
                await message.reply_text("❌ Couldn't identify the anime. Try a clearer image.")
                return

            best_match = trace_data['result'][0]
            anilist_data = await self.fetch_anilist(best_match['anilist'])

            # Prepare response
            from_time = best_match.get('from', 0)
            timestamp = f"{int(from_time // 60):02}:{int(from_time % 60):02}"

            response_data = {
                'title': anilist_data.get('title', {}),
                'episode': best_match.get('episode', 'N/A'),
                'episodes': anilist_data.get('episodes', 0),
                'timestamp': timestamp,
                'confidence': float(best_match.get('similarity', 0)) * 100,
                'anilist_url': anilist_data.get('siteUrl', '#'),
                'video_url': f"{best_match.get('video', '')}&size=l" if best_match.get('video') else None,
                'cover_image': anilist_data.get('coverImage', {}).get('large', None),
            }

            caption = self.format_response(response_data)

            # Send results with fallback
            try:
                if response_data['video_url']:
                    await message.reply_video(
                        response_data['video_url'],
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif response_data['cover_image']:
                    await message.reply_photo(
                        response_data['cover_image'],
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    await message.reply_text(
                        caption,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
            except Exception as e:
                logger.error(f"Failed to send media: {e}")
                await message.reply_text(
                    caption,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            try:
                await message.reply_text("⚠️ An error occurred while processing your request")
            except:
                pass
        finally:
            ACTIVE_TASKS.discard(task['message_id'])

    def register_handlers(self):
        """Register command handlers properly"""
        @self.bot.on_message(filters.command("findanime") & (filters.private | filters.group))
        async def findanime_wrapper(client: Client, message: Message):
            try:
                if not message.reply_to_message or not (
                    message.reply_to_message.photo or 
                    (message.reply_to_message.document and 
                     message.reply_to_message.document.mime_type.startswith('image/'))
                ):
                    await message.reply_text("🔍 Reply to an anime screenshot with /findanime")
                    return

                if len(REQUEST_QUEUE) >= MAX_QUEUE_SIZE:
                    await message.reply_text("🚧 Queue is full. Please try again later.")
                    return

                REQUEST_QUEUE.append({
                    'message_id': message.id,
                    'chat_id': message.chat.id,
                    'reply_to': message.reply_to_message.id
                })

                await client.send_chat_action(
                    chat_id=message.chat.id,
                    action=ChatAction.TYPING
                )
                await message.reply_text("🔄 Your request has been queued. Please wait...")
            except Exception as e:
                logger.error(f"Handler error: {e}", exc_info=True)
                try:
                    await message.reply_text("⚠️ An error occurred while processing your command")
                except:
                    pass

        # Store handler reference for proper cleanup
        self._handler = self.bot.dispatcher.get_handler_by_func(findanime_wrapper.__name__)
