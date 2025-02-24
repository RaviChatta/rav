import asyncio
from pathlib import Path
import random
import math, time
from datetime import datetime
from typing import Optional
from pytz import timezone
from config import Config 
from pyrogram import Client
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from pyrogram.errors import FloodWait
import re
# from moviepy.editor import VideoFileClip
from shortzy import Shortzy


from pyrogram.errors import FloodWait
import asyncio
import time

PROGRESS_BAR = """\n
<b>» ᴛᴀɪʟʟᴇ</b> : {1} | {2}  
<b>» ꜰᴀɪᴛ</b> : {0}%  
<b>» ᴠɪᴛᴇssᴇ</b> : {3}/s  
<b>» ᴇᴛᴀ</b> : {4}"""

async def progress_for_pyrogram(current, total, ud_type, message, start):
    try:
        if total == 0:
            percentage = 0  
        else:
            percentage = current * 100 / total

        elapsed_time = time.time() - start
        speed = current / elapsed_time if elapsed_time > 0 else 0

        # Afficher la progression
        progress_message = (
            f"**{ud_type}**\n"
            f"Progression : {percentage:.2f}%\n"
            f"Vitesse : {speed / 1024:.2f} KB/s\n"
            f"Temps écoulé : {elapsed_time:.2f}s"
        )
        await asyncio.sleep(3)
        await message.edit_text(progress_message)

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await progress_for_pyrogram(current, total, ud_type, message, start)  

    except Exception as e:
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
    return str(round(size, 2)) + " " + Dic_powerN[n] + 'ʙ'


def TimeFormatter(milliseconds: int) -> str:
    seconds, milliseconds = divmod(int(milliseconds), 1000)
    minutes, seconds = divmod(seconds, 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)
    tmp = ((str(days) + "ᴅ, ") if days else "") + \
        ((str(hours) + "ʜ, ") if hours else "") + \
        ((str(minutes) + "ᴍ, ") if minutes else "") + \
        ((str(seconds) + "ꜱ, ") if seconds else "") + \
        ((str(milliseconds) + "ᴍꜱ, ") if milliseconds else "")
    return tmp[:-2] 

def convert(seconds):
    seconds = seconds % (24 * 3600)
    hour = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60      
    return "%d:%02d:%02d" % (hour, minutes, seconds)

async def send_log(b, u):
    if Config.LOG_CHANNEL is not None:
        curr = datetime.now(timezone("Asia/Kolkata"))
        date = curr.strftime('%d %B, %Y')
        time = curr.strftime('%I:%M:%S %p')
        await b.send_message(
            Config.LOG_CHANNEL,
            f"**--Nᴇᴡ Uꜱᴇʀ Sᴛᴀʀᴛᴇᴅ Tʜᴇ Bᴏᴛ--**\n\nUꜱᴇʀ: {u.mention}\nIᴅ: `{u.id}`\nUɴ: @{u.username}\n\nDᴀᴛᴇ: {date}\nTɪᴍᴇ: {time}\n\nBy: {b.mention}"
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
    
async def get_user_profile_photo(client: Client, user_id: int) -> Optional[str]:

    try: 
        # Récupérer les photos de profil de l'utilisateur
        photos = [
            "https://telegra.ph/file/41a6574ff59f886a79071.jpg", 
            "https://telegra.ph/file/3e0baa3c7584c21f94df8.jpg", 
            "https://telegra.ph/file/ffc4a8eb4aeefbfb38e84.jpg",
            "https://telegra.ph/file/aaa4e80ce9f7985312543.jpg",
            "https://telegra.ph/file/de6169199ff536a57c7bb.jpg",
            "https://telegra.ph/file/111b8da5c1ea66ebead7c.jpg",
            "https://telegra.ph/file/06e88d7dee967fa209bc5.jpg",
            ]


        if photos:
            random_photo = random.choice(photos)
            return random_photo  
    except Exception as e:
        print(f"Erreur lors de la récupération des photos de profil : {e}")
    return None

# async def get_video_duration(file_path: Path) -> str:
#     """
#     Calcule la durée d'une vidéo et la retourne sous forme de chaîne de caractères (HH:MM:SS).
#     """
#     try:
#         clip = VideoFileClip(str(file_path))
#         duration = int(clip.duration)
#         hours, remainder = divmod(duration, 3600)
#         minutes, seconds = divmod(remainder, 60)
#         return f"{hours:02}:{minutes:02}:{seconds:02}"
#     except Exception as e:
#         print(f"Erreur lors du calcul de la durée de la vidéo: {e}")
#         return "00:00:00"

async def get_shortlink(url, api, link):
    """
    Crée un lien raccourci avec Shortzy.
    """
    shortzy = Shortzy(api_key=api, base_site=url)
    shortlink = await shortzy.convert(link)
    return shortlink
