from datetime import datetime, timezone
import math
import random
import re
import time
from typing import Optional, Tuple
import math, time
from shortzy import Shortzy
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from scripts import Txt
from config import settings

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

async def progress_for_pyrogram(current, total, ud_type, message, start):
    now = time.time()
    diff = now - start
    if round(diff % 5.00) == 0 or current == total:        
        percentage = current * 100 / total
        speed = current / diff
        elapsed_time = round(diff) * 1000
        time_to_completion = round((total - current) / speed) * 1000
        estimated_total_time = elapsed_time + time_to_completion

        elapsed_time = TimeFormatter(milliseconds=elapsed_time)
        estimated_total_time = TimeFormatter(milliseconds=estimated_total_time)

        progress = "{0}{1}".format(
            ''.join(["█" for i in range(math.floor(percentage / 5))]),
            ''.join(["░" for i in range(20 - math.floor(percentage / 5))])
        )            
        tmp = progress + Txt.PROGRESS_BAR.format( 
            round(percentage, 2),
            humanbytes(current),
            humanbytes(total),
            humanbytes(speed),            
            estimated_total_time if estimated_total_time != '' else "0 s"
        )
        try:
            await message.edit(
                text=f"{ud_type}\n\n{tmp}",               
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("• Cancel •", callback_data="close")]])                                               
            )
        except:
            pass

def humanbytes(size):    
    if not size:
        return ""
    power = 2**10
    n = 0
    Dic_powerN = {0: ' ', 1: 'K', 2: 'M', 3: 'G', 4: 'T'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'B'

def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "d, ") if days else "") + \
        ((str(hours) + "h, ") if hours else "") + \
        ((str(minutes) + "m, ") if minutes else "") + \
        ((str(seconds) + "s, ") if seconds else "") + \
        ((str(milliseconds) + "ms, ") if milliseconds else "")
    return tmp[:-2] 

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

async def get_shortlink(url, api, link):
    """
    Creates a shortlink using Shortzy.
    """
    shortzy = Shortzy(api_key=api, base_site=url)
    shortlink = await shortzy.convert(link)
    return shortlink
