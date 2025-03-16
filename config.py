
import re, os, time
from os import environ, getenv
id_pattern = re.compile(r'^.\d+$') 
from dotenv import load_dotenv
load_dotenv()


class Settings():
    
    API_HASH = os.getenv("bf5a6381d07f045af4faeb46d7de36e5")
    API_ID = os.getenv("24777493")
    BOT_TOKEN = os.getenv("7683456107:AAH3y7X7fe6XtTjfYlv5v27wIGgsgcGHL70")
    
    DATA_URI =  os.getenv("mongodb+srv://altof2:123Bonjoure@cluster0.s1suq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATA_NAME = os.getenv("Altof2")
    
    TEMP_DIR = os.environ.get("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads/")
    
    PORT = os.environ.get("PORT")
    WEBHOOK = bool(os.environ.get("WEBHOOK", "True"))
    
    BOT_UPTIME  = time.time()
    ADMIN       = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN').split()]
    FORCE_SUB_CHANNELS = os.environ.get('sineur_x_bot', '').split(',')
    CHANNEL_LOG = os.environ.get("-1002059540600", None)
    CHANNEL_LOG = int(CHANNEL_LOG) if CHANNEL_LOG and CHANNEL_LOG.lstrip("-").isdigit() else None
    DUMP_CHANNEL = int(os.environ.get("-1002203058630", None))
    DUMP_CHANNEL = int(DUMP_CHANNEL) if DUMP_CHANNEL and DUMP_CHANNEL.lstrip("-").isdigit() else None
    UPDATE_CHANNEL = os.environ.get("@sineur_x_bot", None)
    SUPPORT_GROUP = os.environ.get("https://t.me/REQUETE_ANIME_30sbot", None)
    SHORTED_LINK = os.environ.get("SHORTED_LINK")
    SHORTED_LINK_API = os.environ.get("SHORTED_LINK_API")
    
    IMAGES = os.environ.get("https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg")
    
    
    
settings = Settings()