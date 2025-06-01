# findanime.py - Fully compatible with Python 3.13 and PTB v13
import asyncio
import requests
import psutil
import mimetypes  # Replacement for imghdr
from collections import deque

# Compatibility layer for Python 3.13
import sys
if sys.version_info >= (3, 13):
    # Create imghdr replacement
    class ImghdrCompat:
        @staticmethod
        def what(file, h=None):
            mime = mimetypes.guess_type(file)[0]
            return mime.split('/')[-1] if mime else None
    sys.modules['imghdr'] = ImghdrCompat()

# PTB v13 imports
try:
    from telegram import Update, ParseMode, ChatAction
    from telegram.ext import (
        CallbackContext,
        CommandHandler,
        MessageHandler,
        Filters
    )
except ImportError as e:
    print(f"Import error: {e}")
    raise

# --- Config ---
TRACE_MOE_KEY = "your_trace_moe_key"  # Replace with your key
ANILIST_API = "https://graphql.anilist.co"

# --- Adaptive Queue System ---
REQUEST_QUEUE = deque()
ACTIVE_TASKS = set()
CPU_THRESHOLD = 80

def get_system_load():
    return psutil.cpu_percent(interval=1)

async def adaptive_queue_processor(app):
    while True:
        if REQUEST_QUEUE:
            current_load = get_system_load()
            if current_load < CPU_THRESHOLD:
                task = REQUEST_QUEUE.popleft()
                ACTIVE_TASKS.add(task['message'].message_id)
                asyncio.create_task(process_anime_request(task, app))
            await asyncio.sleep(0.5 if current_load > CPU_THRESHOLD else 0.1)
        else:
            await asyncio.sleep(1)

async def turbo_search(image_url: str):
    headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
    params = {'url': image_url, 'cutBorders': True}
    for attempt in range(3):
        try:
            response = requests.get("https://api.trace.moe/search", params=params, headers=headers, timeout=10)
            return response.json() if response.status_code == 200 else None
        except requests.exceptions.RequestException:
            if attempt == 2: return None
            await asyncio.sleep(1)

async def fetch_anilist(anilist_id: int):
    query = """query($id: Int) { Media(id: $id, type: ANIME) {
        title { romaji english } episodes siteUrl coverImage { large } } }"""
    try:
        response = requests.post(ANILIST_API, json={'query': query, 'variables': {'id': anilist_id}}, timeout=10)
        return response.json().get('data', {}).get('Media', {})
    except:
        return {}

def format_response(data: dict) -> str:
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown')
    return (f"🎬 <b>{title}</b>\n"
            f"• {'🎥 Movie' if data.get('episodes', 0) == 1 else f'📺 Episode: {data.get('episode', 'N/A')}'}\n"
            f"• ⏱ <b>Timestamp:</b> {data.get('timestamp', '00:00')}\n"
            f"• 📊 <b>Confidence:</b> {data.get('confidence', 0):.1f}%\n"
            f"• 🔗 <a href='{data.get('anilist_url', '#')}'>More Info</a>")

async def process_anime_request(task, app):
    try:
        update = task['update']
        context = task['context']
        message = task['message']
        file = await message.reply_to_message.photo[-1].get_file()
        
        if not (trace_data := await turbo_search(file.file_path)):
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
            await message.reply_video(response_data['video_url'], caption=caption, parse_mode=ParseMode.HTML)
        elif response_data.get('cover_image'):
            await message.reply_photo(response_data['cover_image'], caption=caption, parse_mode=ParseMode.HTML)
        else:
            await message.reply_text(caption, parse_mode=ParseMode.HTML)

    except Exception as e:
        print(f"Processing error: {e}")
    finally:
        ACTIVE_TASKS.discard(message.message_id)

async def findanime(update: Update, context: CallbackContext):
    try:
        if not (update.message and update.message.reply_to_message and update.message.reply_to_message.photo):
            await update.message.reply_text("🔍 Reply to an anime screenshot with /findanime")
            return

        REQUEST_QUEUE.append({'update': update, 'context': context, 'message': update.message})
        await context.bot.send_chat_action(chat_id=update.message.chat.id, action=ChatAction.TYPING)
    except Exception as e:
        print(f"Command error: {e}")

async def handle_mention(update: Update, context: CallbackContext):
    if update.message and context.bot.username and f"@{context.bot.username}" in update.message.text:
        await findanime(update, context)

async def setup_anime_finder(app):
    asyncio.create_task(adaptive_queue_processor(app))
    app.add_handler(CommandHandler("findanime", findanime))
    app.add_handler(MessageHandler(
        Filters.text & Filters.chat_type.groups,
        handle_mention
    ))
    print("🎌 Anime Finder feature initialized successfully!")
