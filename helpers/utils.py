from datetime import datetime, timezone
import math
import random
import re
import time
from typing import Optional, Tuple , Union
import math, time
from shortzy import Shortzy
import asyncio
from pyrogram.types import (
    Message,
    User,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    CallbackQuery
)
from scripts import Txt
from config import settings
import logging

logger = logging.getLogger(__name__)
last_progress_edit = {}

# Patterns for extracting season numbers
SEASON_PATTERNS = [
    re.compile(r'(?:S|Season)\s*-?\s*(\d+)', re.IGNORECASE),
    re.compile(r'Season\s*(\d+)\s*\b(?:Episode|Ep|E)\s*\d+', re.IGNORECASE),
    re.compile(r'S(?P<season>\d+)(?:E|EP)\d+', re.IGNORECASE),
    re.compile(r'S(?P<season>\d+)\s*-\s*E\d+', re.IGNORECASE),
]

# Patterns for extracting episode numbers
EPISODE_PATTERNS = [
    re.compile(r'(?:E|Episode)\s*-?\s*(\d+)', re.IGNORECASE),
    re.compile(r'Season\s*\d+\s*(?:Episode|Ep|E)\s*(\d+)', re.IGNORECASE),
    re.compile(r'S\d+(?:E|EP)(\d+)', re.IGNORECASE),
    re.compile(r'S\d+\s*-\s*E(\d+)', re.IGNORECASE),
    re.compile(r'EP?(\d{2})\b', re.IGNORECASE),
    re.compile(r'\b(\d{1,4})\b(?!\s*[pP])', re.IGNORECASE),
]

# Patterns for extracting quality
QUALITY_PATTERNS = {
    re.compile(r'\b(?:.*?(\d{3,4}[^\dp]*p).*?|.*?(\d{3,4}p))\b', re.IGNORECASE): lambda match: match.group(1) or match.group(2),
    re.compile(r'[([<{]?\s*4k\s*[)\]>}]?', re.IGNORECASE): lambda _: "4k",
    re.compile(r'[([<{]?\s*2k\s*[)\]>}]?', re.IGNORECASE): lambda _: "2k",
    re.compile(r'[([<{]?\s*HdRip\s*[)\]>}]?|\bHdRip\b', re.IGNORECASE): lambda _: "HdRip",
    re.compile(r'[([<{]?\s*4kX264\s*[)\]>}]?', re.IGNORECASE): lambda _: "4kX264",
    re.compile(r'[([<{]?\s*4kx265\s*[)\]>}]?', re.IGNORECASE): lambda _: "4kx265",
    re.compile(r'[([<{]?\s*UHD\s*[)\]>}]?', re.IGNORECASE): lambda _: "UHD",
    re.compile(r'[([<{]?\s*HD\s*[)\]>}]?', re.IGNORECASE): lambda _: "HD",
    re.compile(r'[([<{]?\s*SD\s*[)\]>}]?', re.IGNORECASE): lambda _: "SD",
    re.compile(r'[([<{]?\s*converted\s*[)\]>}]?', re.IGNORECASE): lambda _: "converted",
}

async def extract_season(filename: str) -> Optional[str]:
    """
    Extracts season number as string.
    Returns None if no season number is found.
    """
    for pattern in SEASON_PATTERNS:
        match = pattern.search(filename)
        if match:
            return match.group(1)
    return None

async def extract_episode(filename: str) -> Optional[str]:
    """
    Extracts episode number as string.
    Returns None if no episode number is found.
    """
    for pattern in EPISODE_PATTERNS:
        match = pattern.search(filename)
        if match:
            return match.group(1)  
    return None

async def extract_season_episode(filename: str) -> Optional[Tuple[str, str]]:
    """
    Extracts both season and episode numbers as strings.
    Returns None if neither is found.
    """
    season = await extract_season(filename)
    episode = await extract_episode(filename)
    
    if episode is not None and season is None:
        season = "01"  # Default season value if not found
    
    if season is not None and episode is not None:
        return season, episode
    return None

async def extract_quality(filename: str) -> str:
    """
    Extracts video quality.
    Returns "Unknown" if no quality is found.
    """
    for pattern, extractor in QUALITY_PATTERNS.items():
        match = pattern.search(filename)
        if match:
            return extractor(match)
    return "Unknown"




# Add this at the top of your file with other globals

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start

    # Global control: Only update once every X seconds per message
    last = last_progress_edit.get(message.chat.id, 0)
    
    # Dynamic delay: adjust based on file size
    if total >= 1024 * 1024 * 1024:         # ≥ 1 GB
        delay = 8
    elif total >= 500 * 1024 * 1024:        # 500 MB – 1 GB
        delay = 5
    else:                                   # < 500 MB
        delay = 1.5
    
    if now - last < delay and current != total:
        return

    last_progress_edit[message.chat.id] = now

    try:
        # Detect aria2c-style download messages
        is_aria2c_download = "Aria2c" in (message.text or "") and "Downloading" in ud_type
        
        if is_aria2c_download:
            # Aria2c: we may not have exact progress, so show a fun spinner bar
            elapsed = diff
            speed = current / elapsed if elapsed > 0 else 0
            remaining = (total - current) / speed if speed > 0 else 0

            progress_text = (
                f"🚀 **Aria2c Turbo Download**\n\n"
                f"{''.join(['▰' for _ in range(min(10, int(elapsed % 10)))])}"
                f"{''.join(['▱' for _ in range(10 - min(10, int(elapsed % 10)))])}\n\n"
                f"**Speed:** {humanbytes(speed)}/s\n"
                f"**Downloaded:** {humanbytes(current)} / {humanbytes(total)}\n"
                f"**Time:** {TimeFormatter(elapsed * 1000)}\n"
                f"**ETA:** {TimeFormatter(remaining * 1000) if remaining > 0 else 'Calculating...'}"
            )

            await message.edit_text(progress_text)

        else:
            # Regular Pyrogram download progress
            percentage = current * 100 / total if total > 0 else 0
            speed = current / diff if diff > 0 else 0
            elapsed_time = round(diff) * 1000
            time_to_completion = round((total - current) / speed) * 1000 if speed > 0 else 0
            estimated_total_time = elapsed_time + time_to_completion

            estimated_total_time_str = TimeFormatter(milliseconds=estimated_total_time)

            progress = "{0}{1}".format(
                ''.join(["▰" for _ in range(math.floor(percentage * 15 / 100))]),
                ''.join(["▱" for _ in range(15 - math.floor(percentage * 15 / 100))])
            )

            tmp = progress + Txt.PROGRESS_BAR.format(
                round(percentage, 2),
                humanbytes(current),
                humanbytes(total),
                humanbytes(speed),
                estimated_total_time_str if estimated_total_time_str != '' else "0s"
            )

            await message.edit(
                text=f"{ud_type}\n\n{tmp}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• Cancel •", callback_data="close")]
                ])
            )

    except Exception as e:
        pass  # optionally log error


def humanbytes(size):
    if not size:
        return "0B"
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size >= power and n < 4:
        size /= power
        n += 1
    return f"{round(size, 2)} {Dic_powerN[n]}B"


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds: parts.append(f"{seconds}s")
    if milliseconds: parts.append(f"{milliseconds}ms")
    return " ".join(parts) if parts else "0s"


def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)
    
async def send_log(b, u):
    if settings.LOG_CHANNEL is not None:
        curr = datetime.now(timezone("Asia/Kolkata"))
        date = curr.strftime('%d %B, %Y')
        time = curr.strftime('%I:%M:%S %p')
        await b.send_message(
            settings.LOG_CHANNEL,
            f"**--New User Started The Bot--**\n\nUser: {u.mention}\nID: `{u.id}`\nUsername: @{u.username}\n\nDate: {date}\nTime: {time}\n\nBy: {b.mention}"
        )

def add_prefix_suffix(input_string, prefix='', suffix=''):
    pattern = r'(?P<filename>.*?)(\.\w+)?$'
    match = re.search(pattern, input_string)
    if match:
        filename = match.group('filename')
        extension = match.group(2) or ''
        if prefix == None:
            if suffix == None:
                return f"{filename}{extension}"
            return f"{filename} {suffix}{extension}"
        elif suffix == None:
            if prefix == None:
               return f"{filename}{extension}"
            return f"{prefix}{filename}{extension}"
        else:
            return f"{prefix}{filename} {suffix}{extension}"
    else:
        return input_string
    
async def get_random_photo():
    try: 
        photos = settings.IMAGES.split(' ')
        random_photo = random.choice(photos)
        if random_photo:
            return random_photo
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None
async def get_random_animation() -> Optional[str]:
    """Get a random animation from configured animations"""
    try:
        if not settings.ANIMATIONS:
            return None
            
        animations = [a.strip() for a in settings.ANIMATIONS.split() if a.strip()]
        return random.choice(animations) if animations else None
    except Exception as e:
        logger.error(f"Error getting random animation: {e}")
        return None
async def get_shortlink(url: str, api: str, link: str, max_retries: int = 3) -> str:
    """
    Creates a shortlink with retry mechanism and fallback
    
    Args:
        url: Base URL of the shortener service
        api: API key for the shortener service
        link: Original URL to be shortened
        max_retries: Number of retry attempts
        
    Returns:
        str: Shortened URL or original URL if shortening fails
    """
    if not all([url, api, link]):
        logger.warning("Missing required parameters for shortlink")
        return link
    
    shortzy = Shortzy(api_key=api, base_site=url)
    
    for attempt in range(max_retries):
        try:
            shortlink = await shortzy.convert(link)
            if shortlink and shortlink.startswith(('http://', 'https://')):
                logger.info(f"Successfully shortened URL (attempt {attempt + 1})")
                return shortlink
            logger.warning(f"Invalid shortlink format received: {shortlink}")
        except Exception as e:
            logger.warning(f"Shortlink attempt {attempt + 1} failed: {str(e)}")
            if attempt < max_retries - 1:
                await asyncio.sleep(1)  # Exponential backoff could be used here
    
    logger.error("All shortlink attempts failed, falling back to original URL")
    return link
async def safe_edit_message(target: Union[Message, CallbackQuery], text: str, **kwargs):
    """Safely edit a message with error handling"""
    try:
        if isinstance(target, CallbackQuery):
            if not target.message:
                logger.warning("No message in CallbackQuery")
                return None
            return await target.message.edit_text(text, **kwargs)
        else:
            return await target.edit_text(text, **kwargs)
    except (AttributeError, TypeError) as e:
        logger.warning(f"Message edit failed (invalid target): {e}")
    except Exception as e:
        logger.error(f"Message edit failed: {e}")
    return None

def safe_mention(user: Optional[User]) -> str:
    """Safe user mention with fallback"""
    if not user:
        return "User"
    return user.mention if hasattr(user, 'mention') else f"@{user.username}" if user.username else f"User {user.id}"

async def get_safe_media(media_type: str, user_id: int, fallback=None):
    """Get media with fallback handling"""
    try:
        if media_type == "photo":
            thumb = await hyoshcoder.get_thumbnail(user_id)
            return thumb or await get_random_photo() or fallback
        elif media_type == "animation":
            return await get_random_animation() or fallback
    except Exception as e:
        logger.error(f"Error getting {media_type}: {e}")
    return fallback

async def get_file_url(client: Client, file_id: str) -> Optional[str]:
    """Get direct download URL for a file"""
    try:
        file = await client.get_file(file_id)
        return f"https://api.telegram.org/file/bot{client.bot_token}/{file.file_path}"
    except Exception as e:
        logger.error(f"Error getting file URL: {e}")
        return None

async def check_aria2_status() -> Dict[str, Any]:
    """Check aria2c service status"""
    if not settings.ARIA2_ENABLED or not aria2_manager.initialized:
        return {"status": "disabled", "active": False}
    
    try:
        stats = aria2_manager.api.get_global_stats()
        downloads = aria2_manager.api.get_downloads()
        
        return {
            "status": "active",
            "download_speed": stats.download_speed,
            "upload_speed": stats.upload_speed,
            "active_downloads": len([d for d in downloads if d.is_active]),
            "total_downloads": len(downloads)
        }
    except Exception as e:
        return {"status": "error", "error": str(e), "active": False}
