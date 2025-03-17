import re, os, time
from dotenv import load_dotenv

load_dotenv()  # Charge les variables d'environnement depuis un fichier .env si présent

# On accepte désormais les IDs négatifs (pour les chats/canaux Telegram)
id_pattern = re.compile(r'^-?\d+$')

class Settings():
    # API et authentification du bot
    API_HASH = os.getenv("API_HASH", "bf5a6381d07f045af4faeb46d7de36e5")
    API_ID = os.getenv("API_ID", "24777493")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "7683456107:AAH3y7X7fe6XtTjfYlv5v27wIGgsgcGHL70")
    
    # Configuration de la base de données
    DATA_URI = os.getenv("DATA_URI", "mongodb+srv://altof2:123Bonjoure@cluster0.s1suq.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0")
    DATA_NAME = os.getenv("DATA_NAME", "Altof2")
    
    # Répertoires temporaires et de téléchargement
    TEMP_DIR = os.getenv("TEMP_DIR", "temp/")
    DOWNLOAD_DIR = os.getenv("DOWNLOAD_DIR", "downloads/")
    
    # Configuration du serveur web
    PORT = os.getenv("PORT", "8000")
    WEBHOOK = os.getenv("WEBHOOK", "True").lower() in ("true", "1", "yes")
    
    BOT_UPTIME  = time.time()
    
    # Liste des administrateurs (IDs séparés par espace)
    ADMIN = [int(admin) for admin in os.getenv('ADMIN', '').split() if admin.isdigit()]
    
    # Liste des canaux pour le force subscribe (séparés par une virgule)
    FORCE_SUB_CHANNELS = os.getenv('FORCE_SUB_CHANNELS', '').split(',')
    
    # Récupération et conversion sécurisée des IDs de chat
    def safe_int(var_name, default=None):
        val = os.getenv(var_name, None)
        if val is not None and val.lstrip("-").isdigit():
            return int(val)
        return default

    # LOG_CHANNEL : Peut servir de canal de log
    LOG_CHANNEL = safe_int("LOG_CHANNEL", None)
    
    # CHANNEL_LOG : Autre canal de log si nécessaire
    CHANNEL_LOG = safe_int("CHANNEL_LOG", None)
    
    # DUMP_CHANNEL : Canal pour l'envoi des fichiers renommer
    DUMP_CHANNEL = safe_int("DUMP_CHANNEL", None)
    
    # UPDATE_CHANNEL et SUPPORT_GROUP restent en chaîne de caractères
    UPDATE_CHANNEL = os.getenv("UPDATE_CHANNEL", None)
    SUPPORT_GROUP = os.getenv("SUPPORT_GROUP", None)
    
    # Variables pour le raccourcissement de liens (à configurer si utilisé)
    SHORTED_LINK = os.getenv("SHORTED_LINK", None)
    SHORTED_LINK_API = os.getenv("SHORTED_LINK_API", None)
    
    # URL par défaut pour l'image de démarrage ou de log
    IMAGES = os.getenv("IMAGES", "https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg")

# Crée une instance de Settings pour un accès global
settings = Settings()