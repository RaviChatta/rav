from datetime import datetime
import random
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from config import settings
from database import read_user, update_user, create_new_user
from database.userdb import add_file_to_user_queue, get_user_by_code, update_user_metadata
from model import *
from helper.utils import get_user_profile_photo, send_log
from plugins.callback import  waiting_for_response
from helper.autorename import process_file

@Client.on_message(filters.private & filters.command("start"))
async def start(client: Client, message: Message):
    cmd, args = message.command[0], message.command[1:]
    user_id = message.from_user.id
    img = await get_user_profile_photo(client, user_id)
    username = message.from_user.username or message.from_user.first_name
    userinfo = await read_user(user_id)
    
    if not userinfo:
        userinfo = await create_new_user(user_id, username)
        await send_log(client, message.from_user)


        if args and args[0].startswith("refer_"):
            referrer_id = int(args[0].replace("refer_", ""))  
            if referrer_id != user_id:  
                referrer = await read_user(referrer_id)
                if referrer:
                    userinfo.referrer_id = referrer_id

                    reward_points = 10 
                    referrer.type.add_points(reward_points)
                    await update_user(referrer_id, {"type": referrer.type.model_dump()})

                    await client.send_message(
                        chat_id=referrer_id,
                        text=f"🎉 {username} a rejoint le bot grâce à votre invitation ! Vous avez reçu {reward_points} points."
                    )

                    await message.reply(f"🎉 Vous avez été invité par {referrer.name}. Ils ont reçu {reward_points} points !")
                else:
                    await message.reply("❌ L'utilisateur qui vous a invité n'existe pas.")
            else:
                await message.reply("⚠️ Vous ne pouvez pas vous inviter vous-même.")

        welcome_message = (
            f"Félicitations {message.from_user.mention} ! 🎉\n"
            "Merci d'avoir choisi nos services. Vous avez obtenu une allocation de **100 points**.\n\n"
            "Nous allons y allez pas a pas, pour commencez clicker sur [Aide]"
        )
    else:
        welcome_message = (
            f"Bonjour {message.from_user.mention} ! 👋\n"
            "Heureux de vous revoir.\nComme d'abitude je suis la pour vous aider "
        )

    keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("Mise à jour", url=f"{settings.UPDATE_CHANNEL}"),InlineKeyboardButton("Support", url=f"{settings.SUPPORT_GROUP}")],
                [InlineKeyboardButton("Aide", callback_data="help"),InlineKeyboardButton("À propos", callback_data="about")],
                [InlineKeyboardButton("Devellopeur", callback_data="dev")]
            ]
        )
    
    if img:
        await message.reply_photo(
            photo=img, 
            caption=welcome_message, 
            reply_markup=keyboard  
        )
    else:
        await message.reply_text(
            welcome_message,
            reply_markup=keyboard
        )
    
    if args and args[0].startswith("adds_"):
        unique_code = args[0].replace("adds_", "")  
        user = await get_user_by_code(unique_code)  

        if not user:
            await message.reply("❌ le lien n'est pas valide ou l'avez déjà utilisé.")
            return

        if not user.unique_code or user.unique_code != unique_code:
            await message.reply("❌ Ce lien n'est pas valide.")
            return

        if user.pending_points and user.pending_points > 0:
            reward_points = user.pending_points
            user.type.add_points(reward_points) 
            user.pending_points = 0 
            user.unique_code = None
            await update_user(user.id, {"type": user.type.model_dump(), "pending_points": user.pending_points, "unique_code": user.unique_code})
            await message.reply(f"🎉 Vous avez gagné {reward_points} points !")
        else:
            await message.reply("⚠️ Aucun point en attente pour ce code.")
        
        

@Client.on_message(filters.private & filters.command("set_channel"))
async def set_channel(client: Client, message: Message):
    user_id = message.from_user.id
    userinfo = await read_user(user_id)
    
    if not userinfo:
        await message.reply_text("Vous devez d'abord démarrer avec /start.")
        return
    
    if len(message.command) < 2:
        await message.reply_text("Veuillez fournir l'ID du canal. Utilisation: /set_channel [channel_id]")
        return
    
    channel_id = message.command[1]
    m=await message.reply_text(
        "Enregistrement en cours"
    )
    userinfo.channel_dump = {"channel_id": channel_id}
    await update_user(user_id, {"channel_dump": userinfo.channel_dump})
    
    await m.edit(f"Le canal a été défini sur {channel_id}.")
    
# -------------------------------------------------------------------------------------------------------------------------------------
# Gestionnaire pour /auto
@Client.on_message(filters.private & filters.command("auto"))
async def auto(client: Client, message: Message):
    user_id = message.from_user.id
    img = await get_user_profile_photo(client, user_id)
    userinfo = await read_user(user_id)
    if not userinfo:
        await message.reply_text("Vous devez d'abord démarrer avec /start.")
        return

    if len(message.command) < 2:
        await message.reply_photo(
            photo=img,
            caption=("Veuillez fournir un format après la commande. Utilisation: /auto [nom du fichier]\n"
            "Exemple : `/auto Squid Game S{saison}E{episode}`"),
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Aide sur configuration", callback_data="configAuto")]])
        )
        return

    auto_format = " ".join(message.command[1:]) 
    m = await message.reply_photo(
        photo=img,
        caption=("Enregistrement en cours...")
    )

    try:
        userinfo.auto = auto_format
        await update_user(user_id, {"auto": auto_format})

        ms = (
            "Le format a été enregistré.\n"
        )
        
        if userinfo.queue.files:
            ms += (
                "J'ai déjà des fichiers dans la file d'attente.\n"
                "Vous pouvez démarrer le renommage en utilisant la commande /process."
            )
        else:
            ms += (
                "Envoyez-moi tous les fichiers que vous souhaitez renommer.\n"
                "Une fois terminé, appuyez sur le bouton [Lancer le processus] pour lancer le renommage.\n"
                "Propulsé par [Hyoshcoder](https://t.me/hyoshcoder)"
            )

        await m.edit(ms, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Lancer le processus", callback_data="process")]]))
    except Exception as e:
        await m.edit("Une erreur s'est produite lors de l'enregistrement du format. Veuillez réessayer.")
    
# -------------------------------------------------------------------------------------------------------------------------------------
# -------------------------------------------------------------------------------------------------------------------------------------
# Gestionnaire pour capturer les réponses de l'utilisateur
@Client.on_message(filters.text & filters.private)
async def handle_user_response(client: Client, message: Message):
    user_id = message.from_user.id
    if user_id in waiting_for_response:
        response_data = waiting_for_response[user_id]
        action = response_data["action"]
        field = response_data["field"]
        query_message_id = response_data["query_message_id"]

        await message.delete()

        userinfo = await read_user(user_id)
        user_metadata = userinfo.metadata

        if action == "addMetadata":
            setattr(user_metadata, field, message.text)
            await update_user_metadata(user_id, user_metadata)

        elif action == "editMetadata":
            setattr(user_metadata, field, message.text)
            await update_user_metadata(user_id, user_metadata)



# -------------------------------------------------------------------------------------------------------------------------------------
        
# -------------------------------------------------------------------------------------------------------------------------------------


db_lock = asyncio.Lock()

@Client.on_message(filters.private & (filters.document | filters.video | filters.photo))
async def handle_incoming_file(client: Client, message: Message):

    user_id = message.from_user.id
    img = await get_user_profile_photo(client, user_id)

    async with db_lock:  
        userinfo = await read_user(user_id)
        if not userinfo:
            await message.reply("Vous devez d'abord démarrer avec /start.")
            return

        if userinfo.type.points < 1:
            await message.reply_photo(
                photo=img,
                caption="Vous n'avez pas assez de points pour ajouter un fichier à la file d'attente. Vous pouvez obtenir plus de points en achetant un pack de points.",
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Premium", callback_data="premium")]])
            )
            return

        if message.photo:
            file = message.photo
            file_id = file.file_id
            userinfo.thumb = file_id
            await update_user(user_id, {"thumb": userinfo.thumb})
            await message.reply("La photo a été enregistrée comme miniature.")
            return

        if message.document:
            file = message.document
        elif message.video:
            file = message.video
        elif message.audio:
            file = message.audio
        else:
            await message.reply("Type de fichier non supporté.")
            return

        file_id = file.file_id
        file_name = getattr(file, "file_name", "unknown_file")
        mimetype = getattr(file, "mime_type", "application/octet-stream")

        # Vérifier si le fichier est déjà dans la file d'attente
        if file_id in [item.file_id for item in userinfo.queue.files]:
            await message.reply("Ce fichier est déjà dans la file d'attente.")
            return

        try:
            # Déduire un point et mettre à jour l'utilisateur
            userinfo.type.points -= 1
            await update_user(user_id, {"type": userinfo.type.model_dump()})

            # Ajouter le fichier à la file d'attente
            await add_file_to_user_queue(user_id, file_id, file_name, mimetype)
            await message.reply(f"Fichier {file_name} ajouté à la file d'attente. Un point a été déduit.")
        except Exception as e:
            # En cas d'erreur, restaurer le point et informer l'utilisateur
            userinfo.type.points += 1
            await update_user(user_id, {"type": userinfo.type.model_dump()})
            await message.reply(f"❌ Erreur lors de l'ajout du fichier à la file d'attente. Votre point a été restitué. Erreur : {e}")