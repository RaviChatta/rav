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
import os
import tempfile

logger = logging.getLogger(__name__)

TRACE_MOE_KEY = os.getenv("TRACE_MOE_KEY")  # Get from environment
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
        self.handler = None
        self.me = None  # Store bot info
        self.temp_files = set()  # Track temporary files for cleanup

    async def initialize(self):
        """Initialize aiohttp session and register handlers"""
        self.session = aiohttp.ClientSession()
        self.me = await self.bot.get_me()  # Get bot info
        self.register_handlers()
        logger.info("Anime finder initialized successfully")

    async def shutdown(self):
        """Cleanup resources"""
        try:
            if self.session:
                await self.session.close()
                logger.info("Closed aiohttp session")
            
            # Cleanup any remaining temp files
            await self.cleanup_temp_files()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")

    async def cleanup_temp_files(self):
        """Cleanup any temporary files"""
        if not self.temp_files:
            return
            
        logger.info(f"Cleaning up {len(self.temp_files)} temporary files")
        for file_path in self.temp_files:
            try:
                if os.path.exists(file_path):
                    os.unlink(file_path)
            except Exception as e:
                logger.warning(f"Couldn't delete temp file {file_path}: {e}")
        self.temp_files.clear()

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
        """Format anime info in a stylish mobile-friendly design"""
        title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown')
        is_movie = data.get('episodes', 0) == 1
        
        return (
            f"# {data.get('id', '0000')[:4]}\n"
            f"━━━━━━━━━━━━━━━━━━━━\n"
            f"<b>🎌 TITLE</b> 🟧 <i>{title}</i> 🟧\n\n"
            f"<b>▷ EPISODES:</b> ⟨ {data.get('episode', 'N/A')} / {data.get('episodes', '?')} ⟩\n"
            f"<b>◇ MATCH CONFIDENCE:</b> {data.get('confidence', 0):.2f}%\n"
            f"<b>◷ TIMESTAMP:</b> ⏳ {data.get('timestamp', '00:00')} ⏳\n\n"
            f"<a href='{data.get('anilist_url', '#')}'>[MORE INFO] 🌬</a>\n"
            f"━━━━━━━━━━━━━━━━━━━━"
        )
    async def download_image_to_temp(self, file_id: str) -> Optional[bytes]:
        """Download image to temporary file and return bytes"""
        try:
            # Create temp file
            with tempfile.NamedTemporaryFile(delete=False, suffix='.jpg') as temp_file:
                temp_path = temp_file.name
                self.temp_files.add(temp_path)  # Track for cleanup
                
                # Download to temp file
                await self.bot.download_media(file_id, file_name=temp_path)
                
                # Read back into memory
                with open(temp_path, 'rb') as f:
                    return f.read()
        except Exception as e:
            logger.error(f"Error downloading image: {e}")
            return None

    async def process_anime_request(self, task: Dict):
        """Process each anime search request"""
        temp_file_path = None
        try:
            message = await self.bot.get_messages(task['chat_id'], task['message_id'])
            if not message or not message.reply_to_message:
                logger.warning("Original message not found")
                return

            # Delete the queued message if it exists
            if 'queued_message_id' in task:
                try:
                    await self.bot.delete_messages(task['chat_id'], task['queued_message_id'])
                except Exception as e:
                    logger.warning(f"Couldn't delete queued message: {e}")

            # Validate image content
            if not (message.reply_to_message.photo or 
                   (message.reply_to_message.document and 
                    message.reply_to_message.document.mime_type.startswith('image/'))):
                await message.reply_text("❌ Please reply to an image with /findanime")
                return

            # Download image
            await self.bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
            try:
                file_id = (message.reply_to_message.photo.file_id if message.reply_to_message.photo 
                          else message.reply_to_message.document.file_id)
                
                # Download to temp file and read into memory
                image_bytes = await self.download_image_to_temp(file_id)
                if not image_bytes:
                    raise ValueError("Empty image data received")
                    
            except Exception as e:
                logger.error(f"Image download failed: {e}")
                await message.reply_text("❌ Failed to download image")
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
                    sent_msg = await message.reply_video(
                        response_data['video_url'],
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                elif response_data['cover_image']:
                    sent_msg = await message.reply_photo(
                        response_data['cover_image'],
                        caption=caption,
                        parse_mode=ParseMode.HTML
                    )
                else:
                    sent_msg = await message.reply_text(
                        caption,
                        parse_mode=ParseMode.HTML,
                        disable_web_page_preview=True
                    )
                
                # Mention user in groups
                if message.chat.type in ["group", "supergroup"]:
                    await sent_msg.reply_text(
                        f"👆 For {message.from_user.mention_html()}",
                        parse_mode=ParseMode.HTML
                    )
                    
            except Exception as e:
                logger.error(f"Failed to send media: {e}")
                sent_msg = await message.reply_text(
                    caption,
                    parse_mode=ParseMode.HTML,
                    disable_web_page_preview=True
                )
                if message.chat.type in ["group", "supergroup"]:
                    await sent_msg.reply_text(
                        f"👆 For {message.from_user.mention_html()}",
                        parse_mode=ParseMode.HTML
                    )

        except Exception as e:
            logger.error(f"Processing failed: {e}", exc_info=True)
            try:
                await message.reply_text("⚠️ An error occurred while processing your request")
            except:
                pass
        finally:
            # Clean up temporary files
            await self.cleanup_temp_files()
            ACTIVE_TASKS.discard(task['message_id'])

    def register_handlers(self):
        """Register command handlers properly"""
        @self.bot.on_message(filters.command("findanime") & (filters.private | filters.group))
        async def findanime_handler(client: Client, message: Message):
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

                # Send queued message and store its ID
                queued_msg = await message.reply_text("🔄 Your request has been queued. Please wait...")
                
                REQUEST_QUEUE.append({
                    'message_id': message.id,
                    'chat_id': message.chat.id,
                    'reply_to': message.reply_to_message.id,
                    'queued_message_id': queued_msg.id
                })

                await client.send_chat_action(
                    chat_id=message.chat.id,
                    action=ChatAction.TYPING
                )
            except Exception as e:
                logger.error(f"Handler error: {e}", exc_info=True)
                try:
                    await message.reply_text("⚠️ An error occurred while processing your command")
                except:
                    pass
