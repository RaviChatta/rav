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
    API_HASH = os.getenv("API_HASH", "a712d2b8486f26c4dee5127cc9ae0615")
    API_ID = os.getenv("API_ID", "20793620")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7991682891:AAHq3QY1Bgf3UoucgLeAS2wCw-geUUlZAbI")
    
    # Configuration de la base de données
    DATA_URI = os.getenv("DATA_URI", "mongodb+srv://luffyravi2000:AfeOePR1ZVQLJL4P@cluster2.qbjobeq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster2")
    DATA_NAME = os.getenv("DATA_NAME", "Cluster2")
    
    # Répertoires temporaires et de téléchargement
    TEMP_DIR = os.getenv("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads/")
    AUTO_DELETE_TIME = 60
    # Configuration du serveur web
    PORT = os.getenv("PORT", "8000")
    WEBHOOK = os.getenv("WEBHOOK", "True").lower() in ("true", "1", "yes")
    
    BOT_UPTIME  = time.time()
    
    # Liste des administrateurs (IDs séparés par espace)
    ADMIN = [int(admin) for admin in os.getenv('ADMIN', '7259016766').split() if admin.isdigit()]
    BOT_OWNER = int(os.environ.get("BOT_OWNER", "7259016766"))
    # List of admin user IDs who can use /resetdb
    ADMINS = [7259016766]  # Replace with your Telegram user ID
    # Liste des canaux pour le force subscribe (séparés par une virgule)
    FORCE_SUB_CHANNELS = os.getenv('FORCE_SUB_CHANNELS', ' ').split(',')
    ADMIN_MODE = False

        
    # Récupération et conversion sécurisée des IDs de chat
    def safe_int(var_name, default=None):
        val = os.getenv(var_name, None)
        if val is not None and val.lstrip("-").isdigit():
            return int(val)
        return default

    # LOG_CHANNEL : Peut servir de canal de log
    LOG_CHANNEL = safe_int("LOG_CHANNEL", -1001333766434)
    
    # CHANNEL_LOG : Autre canal de log si nécessaire
    CHANNEL_LOG = safe_int("CHANNEL_LOG", -1001333766434)
    
    # DUMP_CHANNEL : Canal pour l'envoi des fichiers renommer
    DUMP_CHANNEL = safe_int("DUMP_CHANNEL", -1002636559428)
    
    # UPDATE_CHANNEL et SUPPORT_GROUP restent en chaîne de caractères
    UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", -1002768753641)
    SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", -1002563598431)
    
    SHORTEN_SERVICES = [
        {
            "domain": "linkshortify.com",
            "api": "aa623da32f4fac5681bb51b20745ddae2ac91462"
        },
        {
            "domain": "arolinks.com",
            "api": "9a78ec81b038a8ac80a59a7456ff6b342927f3d2"
        },
        {
            "domain": "vplink.in",
            "api": "af3216e9f613ea737ed5c1d414ead11542ecfe97"
        },
        {
            "domain": "shortxlinks.com",
            "api": "0d984482b29030629709bfb1265677fef8fa32f7"
        }
    ]

    def get_random_shortener(self):
        """
        🔁 Return a new shortener (domain + api) on each call
        Example: { "domain": "pocolinks.com", "api": "xxx" }
        """
        return random.choice(self.SHORTEN_SERVICES)
    BOT_USERNAME = os.getenv("BOT_USERNAME", "Autorenameboabot")
    TOKEN_ID_LENGTH = 8  # Or whatever you use
    SHORTENER_POINT_REWARD = 80 
    REFER_POINT_REWARD = 300  # or whatever value you want
    LEADERBOARD_DELETE_TIMER = 30
    # URL par défaut pour l'image de démarrage ou de log
    IMAGES = os.getenv("IMAGES", "https://files.catbox.moe/3fnqwm.png https://files.catbox.moe/ikzje9.png ")
    ANIMATIONS = os.getenv("ANIMATIONS", "CgACAgUAAxkBAAMCaFHMN42d-6xOYmAJLrHy7GZSuY4AAkcXAAJropFWeHj762J8d5AeBA CgACAgUAAxkBAAMEaFHMSnEtf6CWZvm64ndibmIk5mwAAkgXAAJropFWDeIwYreCjHIeBA").strip()
# Crée une instance de Settings pour un accès global
settings = Settings()
