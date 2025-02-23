import re, os, time
from os import environ, getenv
id_pattern = re.compile(r'^.\d+$') 
from dotenv import load_dotenv
load_dotenv()

class Config(object):
    # pyro client config
    API_ID    = os.environ.get("API_ID")
    API_HASH  = os.environ.get("API_HASH")
    BOT_TOKEN = os.environ.get("BOT_TOKEN") 

    # database config
    DB_NAME = os.environ.get("DB_NAME")     
    DB_URL  = os.environ.get("DB_URL")	
    PORT = os.environ.get("PORT")

    # other configs
    BOT_UPTIME  = time.time()
    START_PIC   = os.environ.get("START_PIC", "https://graph.org/file/29a3acbbab9de5f45a5fe.jpg")
    ADMIN       = [int(admin) if id_pattern.search(admin) else admin for admin in os.environ.get('ADMIN').split()]
    FORCE_SUB_CHANNELS = os.environ.get('FORCE_SUB_CHANNELS').split(',')
    CHANNEL_LOG = int(os.environ.get("CHANNEL_LOG"))
    LOG_CHANNEL = CHANNEL_LOG
    DUMP_CHANNEL = int(os.environ.get("DUMP_CHANNEL"))
    UPDATE_CHANNEL = os.environ.get("UPDATE_CHANNEL")
    SUPPORT_GROUP = os.environ.get("SUPPORT_GROUP")
    
    SHORTED_LINK = os.environ.get("SHORTED_LINK")
    SHORTED_LINK_API = os.environ.get("SHORTED_LINK_API")
    
    # wes response configuration     
    WEBHOOK = bool(os.environ.get("WEBHOOK", "True"))
    
    TEMP_DIR = os.environ.get("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.environ.get("DOWNLOAD_DIR", "downloads/")
    Thmb = "img/image1.jpg"
    


settings = Config()