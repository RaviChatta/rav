import re, os, time
from dotenv import load_dotenv
import random
import logging
logger = logging.getLogger(__name__)
load_dotenv()  # Charge les variables d'environnement depuis un fichier .env si présent

# On accepte désormais les IDs négatifs (pour les chats/canaux Telegram)
id_pattern = re.compile(r'^-?\d+$')

class Settings():
    # API et authentification du bot
    API_HASH = os.getenv("API_HASH", "449da69cf4081dc2cc74eea828d0c490")
    API_ID = os.getenv("API_ID", "24500584")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "1599848664:AAHc75il2BECWK39tiPv4pVf-gZdPt4MFcw")
    
    # Configuration de la base de données
    DATA_URI = os.getenv("DATA_URI", "mongodb+srv://erenyeagermikasa84:pkbOXb3ulzi9cEFd@cluster0.ingt8mt.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATA_NAME = os.getenv("DATA_NAME", "erenyeagermikasa84")
    
    # Répertoires temporaires et de téléchargement
    TEMP_DIR = os.getenv("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads/")
    AUTO_DELETE_TIME = 60
    # Configuration du serveur web
    PORT = os.getenv("PORT", "8000")
    WEBHOOK = os.getenv("WEBHOOK", "True").lower() in ("true", "1", "yes")
    
    BOT_UPTIME  = time.time()
    
    # Liste des administrateurs (IDs séparés par espace)
    ADMIN = [int(admin) for admin in os.getenv('ADMIN', '1047253913').split() if admin.isdigit()]
    BOT_OWNER = int(os.environ.get("BOT_OWNER", "1047253913"))

    # Liste des canaux pour le force subscribe (séparés par une virgule)
    FORCE_SUB_CHANNELS = os.getenv('FORCE_SUB_CHANNELS', '').split(',')
    
    # Récupération et conversion sécurisée des IDs de chat
    def safe_int(var_name, default=None):
        val = os.getenv(var_name, None)
        if val is not None and val.lstrip("-").isdigit():
            return int(val)
        return default

    # LOG_CHANNEL : Peut servir de canal de log
    LOG_CHANNEL = safe_int("LOG_CHANNEL",-1001333766434)
    
    # CHANNEL_LOG : Autre canal de log si nécessaire
    CHANNEL_LOG = safe_int("CHANNEL_LOG", -1001333766434)
    
    # DUMP_CHANNEL : Canal pour l'envoi des fichiers renommer
    DUMP_CHANNEL = safe_int("DUMP_CHANNEL", None)
    
    # UPDATE_CHANNEL et SUPPORT_GROUP restent en chaîne de caractères
    UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", None)
    SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", -1002072871676)
    
    SHORTEN_SERVICES = [
        {
            "domain": "pocolinks.com",
            "api": "de5bd3536a538fb73d70f5d82c5a55820a869b0a"
        },
        {
            "domain": "smallshorts.com",
            "api": "9c63c5b31b1386ffacbe38c84c15f1eb589e8703"
        },
        {
            "domain": "vplink.in",
            "api": "af3216e9f613ea737ed5c1d414ead11542ecfe97"
        },
        {
            "domain": "tinyurl.com",
            "api": "ttJSm2RszqbLenoyY54p2IyFI28DF0wTAHHoQW159uMMH7mb3Pr1vpdZbywa"
        }
    ]

    def get_random_shortener(self):
        """
        🔁 Return a new shortener (domain + api) on each call
        Example: { "domain": "pocolinks.com", "api": "xxx" }
        """
        return random.choice(self.SHORTEN_SERVICES)
    BOT_USERNAME = os.getenv("BOT_USERNAME", "Forwardmsgremoverbot")
    TOKEN_ID_LENGTH = 8  # Or whatever you use
    SHORTENER_POINT_REWARD = 50 
    REFER_POINT_REWARD = 300  # or whatever value you want
    LEADERBOARD_DELETE_TIMER = 30
    # URL par défaut pour l'image de démarrage ou de log
    IMAGES = os.getenv("IMAGES", "https://files.catbox.moe/3fnqwm.png https://files.catbox.moe/ikzje9.png ")
    ANIMATIONS = os.getenv("ANIMATIONS", "CgACAgUAAxkBAAI0Vmg7Mvvv5pviZa3X3EoOcPjELHRvAAKIFAACh_PgVUqDkRmyCLEnHgQ CgACAgUAAxkBAAI0VGg7MvR9HxCuyV4L4aWZWKGPUFV2AAKHFAACh_PgVacMEeJozkEcHgQ").strip()
# Crée une instance de Settings pour un accès global
settings = Settings()
