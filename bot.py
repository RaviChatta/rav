import aiohttp
import asyncio
import pytz
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client
from aiohttp import web
from route import web_server  # Importation du serveur web
from config import settings  # Paramètres de configuration
from database.data import hyoshcoder  # Base de données
import time
from dotenv import load_dotenv

load_dotenv()  # Chargement des variables d'environnement

# Chargement de la configuration
Config = settings
SUPPORT_CHAT = -1002308381248  # ID du chat de support

class Bot(Client):

    def __init__(self):
        """Initialisation du bot avec ses paramètres."""
        super().__init__(
            name="autorename",
            api_id=Config.API_ID,
            api_hash=Config.API_HASH,
            bot_token=Config.BOT_TOKEN,
            workers=200,  # Nombre de threads simultanés
            plugins={"root": "plugins"},  # Dossier contenant les plugins
            sleep_threshold=15,  # Seuil de sommeil du bot
        )
        self.start_time = time.time()  # Enregistrement du temps de démarrage

    async def start(self):
        """Démarrage du bot."""
        await super().start()
        me = await self.get_me()  # Récupération des informations du bot
        self.mention = me.mention  # Mention du bot
        self.username = me.username  # Nom d'utilisateur du bot
        self.uptime = Config.BOT_UPTIME  # Temps de fonctionnement du bot

        print(f"{me.first_name} a Started.....✨️")

        # Calcul du temps de fonctionnement
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        # Nettoyage de la base de données
        await hyoshcoder.clear_all_user_channels()

        # Envoi d'un message aux canaux de logs et de support
        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                # Définition du fuseau horaire
                curr = datetime.now(timezone("Asia/Kolkata"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')

                # Envoi d'une image avec un message de redémarrage
                # Sending an image with a restart message
                # Sending an image with a restart message
                await self.send_photo(
                    chat_id=chat_id,
                    photo="https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg",
                    caption=(
                        "**Oops! The bot has restarted.**\n\n"
                        f"I haven't slept since: `{uptime_string}`"
                    )
                )
            except Exception as e:
                print(f"Failed to send message in chat {chat_id}: {e}")


# Fonction pour démarrer les services : Pyrogram + Serveur Web
async def start_services():
    bot = Bot()
    
    # Démarrage du client Pyrogram
    await bot.start()
    
    # Lancer le serveur web si configuré
    if Config.WEBHOOK:
        app = web.AppRunner(await web_server())  # Assurez-vous que `web_server()` retourne une instance valide de serveur
        await app.setup()
        site = web.TCPSite(app, "0.0.0.0", 8080)
        await site.start()  # Démarrage du serveur web

# Fonction principale pour exécuter le bot
async def main():
    await start_services()  # Appel de la fonction start_services()

if __name__ == "__main__":
    asyncio.run(main())
