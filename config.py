import re, os, time
from dotenv import load_dotenv

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
    
    # Configuration du serveur web
    PORT = os.getenv("PORT", "8000")
    WEBHOOK = os.getenv("WEBHOOK", "True").lower() in ("true", "1", "yes")
    
    BOT_UPTIME  = time.time()
    
    # Liste des administrateurs (IDs séparés par espace)
    ADMIN = [int(admin) for admin in os.getenv('ADMIN', '1047253913').split() if admin.isdigit()]
    
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
    
    # Variables pour le raccourcissement de liens (à configurer si utilisé)
    SHORTED_LINK = os.getenv("SHORTED_LINK", None)
    SHORTED_LINK_API = os.getenv("SHORTED_LINK_API", None)
    
    # URL par défaut pour l'image de démarrage ou de log
    IMAGES = os.getenv("IMAGES", "https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg")
    ANIMATIONS = os.getenv("ANIMATIONS", "CgACAgUAAxkBAAIqu2gvdr3Ig6KwAjQdM9woyO2OApJsAAI9JQACQFB4VZDEV3IIg0VcHgQ").strip()
# Crée une instance de Settings pour un accès global
settings = Settings()
