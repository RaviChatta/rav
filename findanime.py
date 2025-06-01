import asyncio
import psutil
from collections import deque
from pyrogram import filters, Client
from pyrogram.types import Message
from pyrogram.enums import ParseMode, ChatAction
from typing import Dict, Optional
import logging
import aiohttp

logger = logging.getLogger(__name__)

TRACE_MOE_KEY = None  # Set your API key if needed
ANILIST_API = "https://graphql.anilist.co"
CPU_THRESHOLD = 80

REQUEST_QUEUE = deque()
ACTIVE_TASKS = set()

def get_system_load() -> float:
    return psutil.cpu_percent(interval=1)

async def adaptive_queue_processor(bot: Client):
    """Smart queue that adjusts based on system load"""
    while True:
        if REQUEST_QUEUE:
            current_load = get_system_load()
            
            if current_load < CPU_THRESHOLD:
                task = REQUEST_QUEUE.popleft()
                ACTIVE_TASKS.add(task['message_id'])
                asyncio.create_task(process_anime_request(bot, task))
            
            await asyncio.sleep(0.5 if current_load > CPU_THRESHOLD else 0.1)
        else:
            await asyncio.sleep(1)

async def turbo_search(image_data: bytes) -> Optional[Dict]:
    """Anime detection with retries"""
    headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
    
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as session:
                form_data = aiohttp.FormData()
                form_data.add_field('image', image_data, filename='image.jpg')
                
                async with session.post(
                    "https://api.trace.moe/search",
                    data=form_data,
                    headers=headers,
                    timeout=15
                ) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Attempt {attempt+1} failed: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"Attempt {attempt+1} failed: {str(e)}")
            if attempt == 2:
                return None
            await asyncio.sleep(1)
    return None

async def fetch_anilist(anilist_id: int) -> Dict:
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
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    ANILIST_API,
                    json={'query': query, 'variables': {'id': anilist_id}},
                    timeout=15
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get('data', {}).get('Media', {})
                    logger.error(f"AniList attempt {attempt+1} failed: HTTP {resp.status}")
        except Exception as e:
            logger.error(f"AniList attempt {attempt+1} failed: {str(e)}")
            if attempt == 2:
                return {}
            await asyncio.sleep(1)
    return {}

def format_response(data: Dict) -> str:
    """Format the anime information"""
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

async def process_anime_request(bot: Client, task: Dict):
    """Process each anime search request"""
    try:
        message = await bot.get_messages(task['chat_id'], task['message_id'])
        if not message or not message.reply_to_message:
            return

        # Get the image file ID
        if message.reply_to_message.photo:
            file_id = message.reply_to_message.photo.file_id
        elif (message.reply_to_message.document and 
              message.reply_to_message.document.mime_type.startswith('image/')):
            file_id = message.reply_to_message.document.file_id
        else:
            await message.reply_text("❌ Please reply to an image with /findanime")
            return

        # Download the image directly as bytes
        await bot.send_chat_action(message.chat.id, ChatAction.UPLOAD_PHOTO)
        image_data = await bot.download_media(file_id, in_memory=True)
        
        if not image_data:
            await message.reply_text("❌ Failed to download image")
            return

        # Search for anime
        trace_data = await turbo_search(image_data)
        if not trace_data or not trace_data.get('result'):
            await message.reply_text("❌ Couldn't identify the anime. Try a clearer image.")
            return

        best_match = trace_data['result'][0]
        anilist_data = await fetch_anilist(best_match['anilist'])

        # Prepare response data
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

        caption = format_response(response_data)

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
                    parse_mode=ParseMode.HTML
                )
        except Exception as e:
            logger.error(f"Failed to send results: {str(e)}")
            await message.reply_text(caption, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Processing failed: {str(e)}", exc_info=True)
        try:
            await message.reply_text("⚠️ An error occurred while processing your request")
        except:
            pass
    finally:
        ACTIVE_TASKS.discard(task['message_id'])

def register_handlers(bot: Client):
    @bot.on_message(filters.command("findanime") & (filters.private | filters.group))
    async def findanime_handler(bot: Client, message: Message):
        try:
            if not message.reply_to_message or not (
                message.reply_to_message.photo or 
                (message.reply_to_message.document and 
                 message.reply_to_message.document.mime_type.startswith('image/'))
            ):
                await message.reply_text("🔍 Reply to an anime screenshot with /findanime")
                return

            REQUEST_QUEUE.append({
                'message_id': message.id,
                'chat_id': message.chat.id,
                'reply_to': message.reply_to_message.id
            })

            await bot.send_chat_action(
                chat_id=message.chat.id,
                action=ChatAction.TYPING
            )
        except Exception as e:
            logger.error(f"Handler error: {str(e)}")

async def start_queue_processor(bot: Client):
    asyncio.create_task(adaptive_queue_processor(bot))
