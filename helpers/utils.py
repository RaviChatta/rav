import asyncio
import math
import random
import re
import time
from datetime import datetime, timezone
from typing import Optional, Tuple, List, Dict
from shortzy import Shortzy
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import settings
from scripts import Txt

# Enhanced patterns with priority matching
MEDIA_PATTERNS = {
    'season': [
        (re.compile(r'S(\d+)', re.IGNORECASE), 1),  # S01, S1
        (re.compile(r'Season\s*(\d+)', re.IGNORECASE), 1),
        (re.compile(r'(\d+)(?:st|nd|rd|th)\s*Season', re.IGNORECASE), 1),
    ],
    'episode': [
        (re.compile(r'E(\d+)', re.IGNORECASE), 1),  # E01, E1
        (re.compile(r'Episode\s*(\d+)', re.IGNORECASE), 1),
        (re.compile(r'(\d+)(?:st|nd|rd|th)\s*Episode', re.IGNORECASE), 1),
        (re.compile(r'\[(\d+)\]', re.IGNORECASE), 1),  # [01], [1]
    ],
    'quality': [
        (re.compile(r'(\d{3,4}p)', re.IGNORECASE), 1),  # 1080p, 720p
        (re.compile(r'(4K|UHD)', re.IGNORECASE), 1),
        (re.compile(r'(HD|SD)', re.IGNORECASE), 1),
        (re.compile(r'(HDR|HDRip|BluRay|WEB-DL|WEBRip)', re.IGNORECASE), 1),
    ]
}

class MediaInfoExtractor:
    @staticmethod
    async def extract_info(filename: str) -> Dict[str, Optional[str]]:
        """
        Extract all media info (season, episode, quality) in one pass
        Returns dict with keys: season, episode, quality
        """
        result = {'season': None, 'episode': None, 'quality': 'Unknown'}
        
        # Combined extraction for better performance
        for pattern_type, patterns in MEDIA_PATTERNS.items():
            for pattern, group in patterns:
                match = pattern.search(filename)
                if match:
                    result[pattern_type] = match.group(group)
                    break  # Stop after first match
        
        # Default season if episode exists but no season
        if result['episode'] and not result['season']:
            result['season'] = '01'
            
        return result

class ProgressTracker:
    def __init__(self):
        self.last_update = 0
        self.update_interval = 0.5  # seconds between updates
        
    async def update_progress(
        self,
        current: int,
        total: int,
        operation_type: str,
        message,
        start_time: float
    ) -> None:
        """Real-time progress updater with smooth rendering"""
        now = time.time()
        if now - self.last_update < self.update_interval and current != total:
            return
            
        self.last_update = now
        elapsed = now - start_time
        
        try:
            # Calculate progress metrics
            percentage = min(100, max(0, (current / total) * 100))
            speed = current / elapsed if elapsed > 0 else 0
            remaining = (total - current) / speed if speed > 0 else 0
            
            # Create progress bar
            progress_bar = self._create_progress_bar(percentage)
            stats = self._format_stats(
                current, total, speed, remaining, percentage
            )
            
            # Update message
            await message.edit(
                text=f"**{operation_type}**\n\n{progress_bar}\n{stats}",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="cancel")]
                ])
            )
        except Exception as e:
            print(f"Progress update error: {e}")

    def _create_progress_bar(self, percentage: float) -> str:
        """Create a smooth animated progress bar"""
        filled = math.floor(percentage / 5)
        empty = 20 - filled
        return f"`[{'█' * filled}{'░' * empty}] {percentage:.1f}%`"

    def _format_stats(
        self,
        current: int,
        total: int,
        speed: float,
        remaining: float,
        percentage: float
    ) -> str:
        """Format statistics line"""
        return Txt.PROGRESS_BAR.format(
            round(percentage, 1),
            self._humanbytes(current),
            self._humanbytes(total),
            self._humanbytes(speed),
            self._format_time(remaining) if remaining > 0 else "0s"
        )

    @staticmethod
    def _humanbytes(size: float) -> str:
        """Convert bytes to human-readable format"""
        if not size:
            return "0 B"
            
        units = ['B', 'KB', 'MB', 'GB', 'TB']
        power = 2**10
        n = 0
        
        while size >= power and n < len(units) - 1:
            size /= power
            n += 1
            
        return f"{size:.2f} {units[n]}" if n > 0 else f"{size} {units[n]}"

    @staticmethod
    def _format_time(seconds: float) -> str:
        """Format time duration"""
        seconds = int(seconds)
        days, seconds = divmod(seconds, 86400)
        hours, seconds = divmod(seconds, 3600)
        minutes, seconds = divmod(seconds, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if seconds > 0 or not parts:
            parts.append(f"{seconds}s")
            
        return " ".join(parts)

async def get_random_photo() -> Optional[str]:
    """Get a random photo from configured images"""
    try:
        if not settings.IMAGES:
            return None
            
        photos = [p.strip() for p in settings.IMAGES.split() if p.strip()]
        return random.choice(photos) if photos else None
    except Exception as e:
        print(f"Error getting random photo: {e}")
        return None

async def get_shortlink(url: str, api: str, link: str) -> str:
    """Get shortlink with retry logic"""
    shortzy = Shortzy(api_key=api, base_site=url)
    
    for attempt in range(3):
        try:
            return await shortzy.convert(link)
        except Exception as e:
            if attempt == 2:
                raise
            await asyncio.sleep(1)
    return link  # fallback to original link

async def send_log(bot, user) -> None:
    """Send new user log to admin channel"""
    if not settings.LOG_CHANNEL:
        return
        
    try:
        now = datetime.now(timezone("Asia/Kolkata"))
        date_time = now.strftime('%d %B, %Y at %I:%M:%S %p')
        
        log_msg = (
            "**🆕 New User Started The Bot**\n\n"
            f"👤 User: {user.mention}\n"
            f"🆔 ID: `{user.id}`\n"
            f"📛 Username: @{user.username}\n\n"
            f"📅 Date: {date_time}\n"
            f"🤖 Bot: {bot.mention}"
        )
        
        await bot.send_message(settings.LOG_CHANNEL, log_msg)
    except Exception as e:
        print(f"Failed to send log: {e}")

def format_duration(seconds: int) -> str:
    """Format duration in HH:MM:SS"""
    seconds = int(seconds)
    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    seconds = seconds % 60
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"

def sanitize_filename(filename: str) -> str:
    """Sanitize filename by removing special characters"""
    return re.sub(r'[\\/*?:"<>|]', "", filename).strip()

# Initialize progress tracker
progress_tracker = ProgressTracker()

# Backward compatibility
async def progress_for_pyrogram(*args, **kwargs):
    """Legacy progress handler"""
    await progress_tracker.update_progress(*args, **kwargs)

async def extract_season(filename: str) -> Optional[str]:
    """Legacy season extractor"""
    return (await MediaInfoExtractor.extract_info(filename))['season']

async def extract_episode(filename: str) -> Optional[str]:
    """Legacy episode extractor"""
    return (await MediaInfoExtractor.extract_info(filename))['episode']

async def extract_quality(filename: str) -> str:
    """Legacy quality extractor"""
    return (await MediaInfoExtractor.extract_info(filename))['quality']

def humanbytes(size: float) -> str:
    """Legacy bytes formatter"""
    return ProgressTracker._humanbytes(size)

def TimeFormatter(milliseconds: int) -> str:
    """Legacy time formatter"""
    return ProgressTracker._format_time(milliseconds / 1000)

def convert(seconds: int) -> str:
    """Legacy duration formatter"""
    return format_duration(seconds)
