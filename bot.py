import aiohttp, asyncio, warnings, pytz
from datetime import datetime, timedelta
from pytz import timezone
from pyrogram import Client, __version__
from pyrogram.raw.all import layer
from config import settings  # Importation des paramètres de configuration
from database.data import hyoshcoder  # Importation de la base de données
from aiohttp import web
from route import web_server  # Importation du serveur web
import pyrogram.utils
import pyromod
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import os
import time
from dotenv import load_dotenv
load_dotenv()  # Chargement des variables d'environnement

# Définition de l'ID minimum d'un canal (pour éviter certains bugs)
pyrogram.utils.MIN_CHANNEL_ID = -1002175858655

# Chargement de la configuration
Config = settings
SUPPORT_CHAT = -1002229122792  # ID du chat de support

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

        # Lancement du serveur web si nécessaire
        if Config.WEBHOOK:
            app = web.AppRunner(await web_server())
            await app.setup()
            await web.TCPSite(app, "0.0.0.0", 8080).start()

        print(f"{me.first_name} a démarré.....✨️")

        # Calcul du temps de fonctionnement
        uptime_seconds = int(time.time() - self.start_time)
        uptime_string = str(timedelta(seconds=uptime_seconds))

        # Nettoyage de la base de données
        await hyoshcoder.clear_all_user_channels()

        # Envoi d'un message aux canaux de logs et de support
        for chat_id in [Config.LOG_CHANNEL, SUPPORT_CHAT]:
            try:
                # Définition du fuseau horaire
                curr = datetime.now(timezone("Africa/togo"))
                date = curr.strftime('%d %B, %Y')
                time_str = curr.strftime('%I:%M:%S %p')

                # Envoi d'une image avec un message de redémarrage
                await self.send_photo(
                    chat_id=chat_id,
                    photo="https://graph.org/file/7c1856ae9ba0a15065ade-abf2c0b5a93356da7b.jpg",
                    caption=(
                        "**bug est bot a redémarré !**\n\n"
                        f"Je n'ai pas dormi depuis​ : `{uptime_string}`"
                    ),
                    reply_markup=InlineKeyboardMarkup(
                        [[
                            InlineKeyboardButton("Mises à jour", url="https://t.me/sineur_x_bot")
                        ]]
                    )
                )

            except Exception as e:
                print(f"Échec de l'envoi du message dans le chat {chat_id} : {e}")

# Exécution du bot
Bot().run()