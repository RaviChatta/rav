import compat  
import asyncio
import requests
import psutil
from collections import deque
from telegram import Update
from telegram.ext import CallbackContext  # Add this import
from telegram.constants import ParseMode, ChatAction
from telegram import constants
from telegram.ext import (
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

# Import from your existing config
from config import settings

# --- Config ---
TRACE_MOE_KEY = getattr(__import__('config', fromlist=['TRACE_MOE_KEY']), 'TRACE_MOE_KEY', None)
ANILIST_API = "https://graphql.anilist.co"

# --- Adaptive Queue System ---
REQUEST_QUEUE = deque()
ACTIVE_TASKS = set()
CPU_THRESHOLD = 80  # Max CPU% before throttling

def get_system_load():
    """Get current CPU usage percentage"""
    return psutil.cpu_percent(interval=1)

async def adaptive_queue_processor(app):
    """Smart queue that adjusts based on system load"""
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
    """Ultra-reliable anime detection with retries"""
    headers = {'x-trace-key': TRACE_MOE_KEY} if TRACE_MOE_KEY else {}
    params = {'url': image_url, 'cutBorders': True}

    for attempt in range(3):
        try:
            response = requests.get(
                "https://api.trace.moe/search",
                params=params,
                headers=headers,
                timeout=10
            )
            if response.status_code == 200:
                return response.json()
        except requests.exceptions.RequestException:
            if attempt == 2:
                return None
            await asyncio.sleep(1)

async def fetch_anilist(anilist_id: int):
    """Bulletproof AniList metadata fetch"""
    query = """
    query($id: Int) {
        Media(id: $id, type: ANIME) {
            title { romaji english }
            episodes
            siteUrl
            coverImage { large }
        }
    }
    """
    try:
        response = requests.post(
            ANILIST_API,
            json={'query': query, 'variables': {'id': anilist_id}},
            timeout=10
        )
        return response.json().get('data', {}).get('Media', {})
    except:
        return {}

def format_response(data: dict) -> str:
    """Professional box-style formatting"""
    title = data.get('title', {}).get('english') or data.get('title', {}).get('romaji', 'Unknown Title')
    is_movie = data.get('episodes', 0) == 1
    timestamp = data.get('timestamp', '00:00')

    return (
        f"╔══════════════════════════╗\n"
        f"  🎬 <b>{title}</b>\n"
        f"╚══════════════════════════╝\n"
        f"• {'🎥 Movie' if is_movie else f'📺 Episode: {data.get('episode', 'N/A')}'}\n"
        f"• ⏱ <b>Timestamp:</b> {timestamp}\n"
        f"• 📊 <b>Confidence:</b> {data.get('confidence', 0):.1f}%\n"
        f"• 🔗 <a href='{data.get('anilist_url', '#')}'>More Info</a>"
    )

async def process_anime_request(task, app):
    """Handles each request with maximum reliability"""
    try:
        update = task['update']
        context = task['context']
        message = task['message']
        
        photo = message.reply_to_message.photo[-1]
        file = await photo.get_file()
        image_url = file.file_path

        trace_data = await turbo_search(image_url)
        if not trace_data or not trace_data.get('result'):
            await message.reply_text("❌ Couldn't identify the anime. Try a clearer image.")
            return

        best_match = trace_data['result'][0]
        anilist_data = await fetch_anilist(best_match['anilist'])

        from_time = best_match.get('from', 0)
        minutes = int(from_time // 60)
        seconds = int(from_time % 60)
        timestamp = f"{minutes:02}:{seconds:02}"

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

        try:
            if response_data.get('video_url'):
                sent_msg = await message.reply_video(
                    response_data['video_url'],
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            elif response_data.get('cover_image'):
                sent_msg = await message.reply_photo(
                    response_data['cover_image'],
                    caption=caption,
                    parse_mode=ParseMode.HTML
                )
            else:
                sent_msg = await message.reply_text(
                    caption,
                    parse_mode=ParseMode.HTML
                )

            if message.chat.type in ["group", "supergroup"]:
                await sent_msg.reply_text(
                    f"👆 For {message.from_user.mention_html()}",
                    parse_mode=ParseMode.HTML
                )

        except Exception as e:
            print(f"Error sending results: {e}")

    except Exception as e:
        print(f"Processing error: {e}")
    finally:
        ACTIVE_TASKS.discard(message.message_id)

async def findanime(update: Update, context: CallbackContext):  # Changed this line
    """Handle /findanime command"""
    try:
        message = update.message
        if not (message and message.reply_to_message and message.reply_to_message.photo):
            await message.reply_text("🔍 Reply to an anime screenshot with /findanime")
            return

        REQUEST_QUEUE.append({
            'update': update,
            'context': context,
            'message': message
        })

        await context.bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.TYPING
        )

    except Exception as e:
        print(f"Command error: {e}")

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle @bot mentions in groups"""
    if update.message and context.bot.username:
        if f"@{context.bot.username}" in update.message.text:
            await findanime(update, context)

async def setup_anime_finder(app):
    """Initialize the anime finder feature"""
    # Start queue processor
    asyncio.create_task(adaptive_queue_processor(app))
    
    # Add handlers
    app.add_handler(CommandHandler("findanime", findanime))
    app.add_handler(MessageHandler(
        filters.TEXT & filters.ChatType.GROUPS,
        handle_mention
    ))
    
    print("🎌 Anime Finder feature initialized successfully!")
