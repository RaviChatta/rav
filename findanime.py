import asyncio
import requests
import psutil
import mimetypes
from collections import deque
from pyrogram import Client, filters
from pyrogram.types import Message
from pyrogram.enums import ParseMode, ChatAction
from typing import Dict, Optional

# Config
TRACE_MOE_KEY = Config.TRACE_MOE_KEY  # Make sure to add this to your config
ANILIST_API = "https://graphql.anilist.co"
CPU_THRESHOLD = 80

# Queue system
REQUEST_QUEUE = deque()
ACTIVE_TASKS = set()

def get_system_load():
    return psutil.cpu_percent(interval=1)

async def adaptive_queue_processor(bot: Client):
    while True:
        if REQUEST_QUEUE and get_system_load() < CPU_THRESHOLD:
            task = REQUEST_QUEUE.popleft()
            ACTIVE_TASKS.add(task['message_id'])
            asyncio.create_task(process_anime_request(bot, task))
        await asyncio.sleep(0.5)

async def turbo_search(image_url: str) -> Optional[Dict]:
    headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
    params = {'url': image_url, 'cutBorders': True}
    try:
        response = requests.get(
            "https://api.trace.moe/search", 
            params=params, 
            headers=headers, 
            timeout=10
        )
        return response.json() if response.status_code == 200 else None
    except requests.exceptions.RequestException:
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
        response = requests.post(
            ANILIST_API, 
            json={'query': query, 'variables': {'id': anilist_id}}, 
            timeout=10
        )
        return response.json().get('data', {}).get('Media', {})
    except Exception:
        return {}

def format_response(data: Dict) -> str:
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown')
    return (
        f"🎬 <b>{title}</b>\n"
        f"• {'🎥 Movie' if data.get('episodes', 0) == 1 else f'📺 Episode: {data.get('episode', 'N/A')}'}\n"
        f"• ⏱ <b>Timestamp:</b> {data.get('timestamp', '00:00')}\n"
        f"• 📊 <b>Confidence:</b> {data.get('confidence', 0):.1f}%\n"
        f"• 🔗 <a href='{data.get('anilist_url', '#')}'>More Info</a>"
    )

async def process_anime_request(bot: Client, task: Dict):
    try:
        message_id = task['message_id']
        chat_id = task['chat_id']
        reply_to = task['reply_to']
        
        message = await bot.get_messages(chat_id, message_id)
        if not message or not message.reply_to_message or not message.reply_to_message.photo:
            return

        file = await message.reply_to_message.download()
        
        if not (trace_data := await turbo_search(file)):
            await message.reply_text("❌ Couldn't identify the anime. Try a clearer image.")
            return

        best_match = trace_data['result'][0]
        anilist_data = await fetch_anilist(best_match['anilist'])
        from_time = best_match.get('from', 0)
        timestamp = f"{int(from_time//60):02}:{int(from_time%60):02}"

        response_data = {
            'title': anilist_data.get('title', {}),
            'episode': best_match.get('episode', 'N/A'),
            'episodes': anilist_data.get('episodes', 0),
            'timestamp': timestamp,
            'confidence': float(best_match.get('similarity', 0)) * 100,
            'anilist_url': anilist_data.get('siteUrl', '#'),
            'video_url': f"{best_match.get('video', '')}&size=l",
            'cover_image': anilist_data.get('coverImage', {}).get('large', '')
        }

        caption = format_response(response_data)
        if response_data.get('video_url'):
            await message.reply_video(
                response_data['video_url'], 
                caption=caption, 
                parse_mode=ParseMode.HTML
            )
        elif response_data.get('cover_image'):
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
        logger.error(f"Error processing anime request: {e}")
    finally:
        ACTIVE_TASKS.discard(message_id)

@Client.on_message(filters.command("findanime") & (filters.private | filters.group))
async def findanime_handler(bot: Client, message: Message):
    try:
        if not message.reply_to_message or not message.reply_to_message.photo:
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

async def setup_anime_finder(bot: Client):
    """Setup anime finder handlers and queue processor"""
    try:
        asyncio.create_task(adaptive_queue_processor(bot))
        logger.info("Anime finder setup completed")
    except Exception as e:
        logger.error(f"Error setting up anime finder: {e}")
        raise
