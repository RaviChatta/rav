import re, os, time
from os import environ, getenv
id_pattern = re.compile(r'^.\d+$') 
from dotenv import load_dotenv
load_dotenv()


class Settings():
    
    API_HASH = os.getenv("API_HASH", "bf5a6381d07f045af4faeb46d7de36e5")
    API_ID = os.getenv("API_ID", "24777493")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7683456107:AAH3y7X7fe6XtTjfYlv5v27wIGgsgcGHL70")
    
    DATA_URI = os.getenv("DATA_URI", "mongodb+srv://altof2:123Bonjoure@cluster0.s1suq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATA_NAME = os.getenv("DATA_NAME", "Altof2")
    
    TEMP_DIR = os.getenv("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads/")
    
    PORT = os.getenv("PORT")
    WEBHOOK = bool(os.getenv("WEBHOOK", "True"))
    
    BOT_UPTIME  = time.time()
    ADMIN = [int(admin) if id_pattern.search(admin) else admin for admin in os.getenv('ADMIN', '').split()]
    FORCE_SUB_CHANNELS = os.getenv('FORCE_SUB_CHANNELS', '').split(',')
    CHANNEL_LOG = os.getenv("CHANNEL_LOG", None)
    CHANNEL_LOG = int(CHANNEL_LOG) if CHANNEL_LOG and CHANNEL_LOG.lstrip("-").isdigit() else None
    DUMP_CHANNEL = os.getenv("DUMP_CHANNEL", None)
    DUMP_CHANNEL = int(DUMP_CHANNEL) if DUMP_CHANNEL and DUMP_CHANNEL.lstrip("-").isdigit() else None
    UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", None)
    SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", None)
    SHORTED_LINK = os.getenv("SHORTED_LINK", None)
    SHORTED_LINK_API = os.getenv("SHORTED_LINK_API", None)
    
    IMAGES = os.getenv("IMAGES", "https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg")
    

settings = Settings()