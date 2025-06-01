import asyncio
import psutil
from collections import deque
from pyrogram import filters, Client
from pyrogram.types import Message, InputMediaPhoto
from pyrogram.enums import ParseMode, ChatAction
from typing import Dict, Optional
import logging
import aiohttp
from io import BytesIO

logger = logging.getLogger(__name__)

TRACE_MOE_KEY = None
ANILIST_API = "https://graphql.anilist.co"
CPU_THRESHOLD = 80

REQUEST_QUEUE = deque()
ACTIVE_TASKS = set()

def get_system_load() -> float:
    return psutil.cpu_percent(interval=1)

async def adaptive_queue_processor(bot: Client):
    while True:
        if REQUEST_QUEUE and get_system_load() < CPU_THRESHOLD:
            task = REQUEST_QUEUE.popleft()
            ACTIVE_TASKS.add(task['message_id'])
            asyncio.create_task(process_anime_request(bot, task))
        await asyncio.sleep(0.5)

async def turbo_search(image_bytes: bytes) -> Optional[Dict]:
    headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
    url = "https://api.trace.moe/search"

    data = aiohttp.FormData()
    data.add_field('image', image_bytes, filename='image.jpg', content_type='image/jpeg')

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=data, headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    logger.error(f"Trace.moe returned status {resp.status}")
                    return None
    except Exception as e:
        logger.error(f"Trace.moe request failed: {e}")
        return None

async def fetch_anilist(anilist_id: int) -> Dict:
    query = """query($id: Int) { 
        Media(id: $id, type: ANIME) {
            title { romaji english } 
            episodes 
            siteUrl 
            coverImage { large } 
        } 
    }"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                ANILIST_API, 
                json={'query': query, 'variables': {'id': anilist_id}}, 
                timeout=15
            ) as resp:
                if resp.status == 200:
                    json_data = await resp.json()
                    return json_data.get('data', {}).get('Media', {})
                else:
                    logger.error(f"AniList API returned status {resp.status}")
                    return {}
    except Exception as e:
        logger.error(f"AniList API request failed: {e}")
        return {}

def format_response(data: Dict) -> str:
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown')
    episodes = data.get('episodes', 0)
    episode = data.get('episode', 'N/A')
    timestamp = data.get('timestamp', '00:00')
    confidence = data.get('confidence', 0)
    anilist_url = data.get('anilist_url', '#')

    return (
        f"🎬 <b>{title}</b>\n"
        f"• {'🎥 Movie' if episodes == 1 else f'📺 Episode: {episode}'}\n"
        f"• ⏱ <b>Timestamp:</b> {timestamp}\n"
        f"• 📊 <b>Confidence:</b> {confidence:.1f}%\n"
        f"• 🔗 <a href='{anilist_url}'>More Info</a>"
    )

async def process_anime_request(bot: Client, task: Dict):
    try:
        message = await bot.get_messages(task['chat_id'], task['message_id'])
        if not message or not message.reply_to_message:
            return

        # Handle both photo and document cases
        if message.reply_to_message.photo:
            photo = message.reply_to_message.photo
            file_id = photo.file_id
        elif message.reply_to_message.document and message.reply_to_message.document.mime_type.startswith('image/'):
            file_id = message.reply_to_message.document.file_id
        else:
            await message.reply_text("❌ Please reply to an image with /findanime")
            return

        # Download the image properly
        image_bytes = BytesIO()
        await bot.download_media(file_id, file_name=image_bytes)
        image_bytes.seek(0)

        trace_data = await turbo_search(image_bytes.getvalue())
        if not trace_data or not trace_data.get('result'):
            await message.reply_text("❌ Couldn't identify the anime. Try a clearer image.")
            return

        best_match = trace_data['result'][0]
        anilist_data = await fetch_anilist(best_match['anilist'])

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

        if response_data['video_url']:
            sent_message = await message.reply_video(
                response_data['video_url'],
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        elif response_data['cover_image']:
            sent_message = await message.reply_photo(
                response_data['cover_image'],
                caption=caption,
                parse_mode=ParseMode.HTML
            )
        else:
            sent_message = await message.reply_text(
                caption,
                parse_mode=ParseMode.HTML
            )

        # Mention user in groups
        if message.chat.type in ["group", "supergroup"]:
            user_mention = message.from_user.mention(style="html")
            await sent_message.reply_text(
                f"👆 For {user_mention}",
                parse_mode=ParseMode.HTML,
                quote=True
            )

    except Exception as e:
        logger.error(f"Error processing anime request: {e}")
        await message.reply_text("⚠️ An error occurred while processing your request")
    finally:
        ACTIVE_TASKS.discard(task['message_id'])

def register_handlers(bot: Client):
    @bot.on_message(filters.command("findanime") & (filters.private | filters.group))
    async def findanime_handler(bot: Client, message: Message):
        try:
            if not message.reply_to_message or not (message.reply_to_message.photo or 
                                                   (message.reply_to_message.document and 
                                                    message.reply_to_message.document.mime_type.startswith('image/'))):
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
            logger.error(f"Error in findanime handler: {e}")

async def start_queue_processor(bot: Client):
    asyncio.create_task(adaptive_queue_processor(bot))
