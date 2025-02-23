import random
import uuid
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired,FloodWait
from database.userdb import read_user, update_user, update_user_metadata
from helper.utils import get_shortlink, get_user_profile_photo
from helper.autorename import process_user_queue
from config import settings
from urllib.parse import quote
import asyncio

photo_cache = {}
waiting_for_response = {}
process_user = {}

async def remove_photo_from_cache(user_id, delay=5):
    await asyncio.sleep(delay)
    if user_id in photo_cache:
        del photo_cache[user_id]

def format_value(value):
    """Formate une valeur en remplaçant None par 'Non défini'."""
    return value if value is not None else "Non défini"

async def reset_waiting_for_response(user_id, query_message, client):
    """Réinitialiser l'état d'attente après 60 secondes et réafficher l'interface."""
    await asyncio.sleep(30)  
    if user_id in photo_cache:
        img = photo_cache[user_id]
    else:
        img = await get_user_profile_photo(client, user_id)
        if img:
            photo_cache[user_id] = img
            asyncio.create_task(remove_photo_from_cache(user_id)) 

    if user_id in waiting_for_response:
        del waiting_for_response[user_id]

        userinfo = await read_user(user_id)
        user_metadata = userinfo.metadata

        def metadata_buttons(field_name, display_name, value):
            if value:  
                return [
                    InlineKeyboardButton(f"✏ Modifier {display_name}", callback_data=f"editMetadata_{field_name}"),
                    InlineKeyboardButton(f"🗑 Supprimer {display_name}", callback_data=f"deleteMetadata_{field_name}")
                ]
            else:  
                return [InlineKeyboardButton(f"➕ Ajouter {display_name}", callback_data=f"addMetadata_{field_name}")]
        
        btn = InlineKeyboardMarkup([
            metadata_buttons("titre", "Titre", user_metadata.titre),
            metadata_buttons("artiste", "Artiste", user_metadata.artiste),
            metadata_buttons("album", "Album", user_metadata.album),
            metadata_buttons("genre", "Genre", user_metadata.genre),
            [InlineKeyboardButton("🔙 Retour", callback_data="help")]
        ])

        caption = (
            "**CONFIGURATION DES MÉTADONNÉES**\n"
            "Cliquez sur une option ci-dessous pour ajouter, modifier ou supprimer une métadonnée.\n\n"
            f"📌 **Titre :** {user_metadata.titre or 'Non défini'}\n"
            f"📌 **Artiste :** {user_metadata.artiste or 'Non défini'}\n"
            f"📌 **Album :** {user_metadata.album or 'Non défini'}\n"
            f"📌 **Genre :** {user_metadata.genre or 'Non défini'}\n"
        )

        if hasattr(query_message, "edit_text"):
            await query_message.edit_text(text=caption, reply_markup=btn)
        elif hasattr(query_message, "edit_media"):
            await query_message.edit_media(media=InputMediaPhoto(media=img, caption=caption), reply_markup=btn)

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    userinfo = await read_user(user_id)
    
    # --------debug callback----------------------------------------------------------------------------------------------------------
    # print(f"Callback received : {data}")
    # ---------------------------------------------------------------------------------------------------------------------------------

    try:
        if user_id in photo_cache:
            img = photo_cache[user_id]
        else:
            img = await get_user_profile_photo(client, user_id)
            if img:
                photo_cache[user_id] = img
                asyncio.create_task(remove_photo_from_cache(user_id)) 

        if data == "help":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Configurer Autorename Format", callback_data="configAuto")],
                [InlineKeyboardButton("Metadata", callback_data="configMetadata"), InlineKeyboardButton("Connect Channel", callback_data="connectChannel")],
                [InlineKeyboardButton("Sequence", callback_data="configSec"), InlineKeyboardButton("Premium", callback_data="premium")],
                [InlineKeyboardButton("Mon compte", callback_data="myAccount")],
                [InlineKeyboardButton("Retour", callback_data="home")]
            ])

            caption = f"**Hey {query.from_user.mention}\nVoici l'aide des commandes**"
        
        elif data == "home":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Mise à jour", url=f"{settings.UPDATE_CHANNEL}"), InlineKeyboardButton("Support", url=f"{settings.SUPPORT_GROUP}")],
                [InlineKeyboardButton("Aide", callback_data="help"), InlineKeyboardButton("À propos", callback_data="about")],
                [InlineKeyboardButton("Développeur", callback_data="dev")],
                [InlineKeyboardButton("Lancer le processus", callback_data="process")]
            ])

            caption = (
                f"**Super {query.from_user.mention}**\n"
                "Si vous êtes prêt, vous pouvez commencer à m'envoyer vos fichiers pour que je les ajoute à la file.\n"
                "Envoyer moi une photo de la miniature de vos fichiers.\n"
                "Une fois terminé, appuyez sur le bouton [Lancer le processus] pour lancer le renommage.\n"
                "Propulsé par [Hyoshcoder](https://t.me/hyoshcoder)"
            )

        elif data == "about":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Retour", callback_data="home")]
            ])

            caption = (
                f"**{query.from_user.mention}**\n\n"
                "Je suis un puissant bot de renommage de fichiers automatique.\n"
                "Je vous envoie tous vos fichiers en ordre dans votre canal dump.\n"
                "Je prends en charge les miniatures et les légendes personnalisées.\n"
                "Je peux détecter l'épisode, la saison et la qualité automatiquement dans vos fichiers."
            )

        elif data == "dev":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Retour", callback_data="home")]
            ])

            caption = (
                f"**{query.from_user.mention}**\n"
                "Voici l'équipe Dev derrière cette idée ingénieuse.\n"
                "Propulsé par [Hyoshcoder](https://t.me/hyoshcoder)\n\n"
                "[Code Sources](https://t.me/hyoshcoder)"
            )
        
        elif data =="configAuto":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Retour", callback_data="help")]
            ])
            caption = (
                "**CNFIGURATION AUTORENAME**\n"
                "Utiliser ces mot clés pour postionner chaque elements dans votre nouveau nom des fichiers\n"
                "`{saison}` : - Pour remplacer la saison\n"
                "`{episode}` : - Pour remplacer l'épisode\n"
                "`{quality}` : - Pour remplacer la resolution\n"
                "`{titre}` : - Pour remplacer le titre\n"
                "`{album}` : - Pour remplacer le nom de l'album\n"
                "`{artiste}` : - Pour remplacer le nom de l'artiste\n"
                "`{genre}` : - Pour remplacer le genre\n"
                "`{duree}` : - Pour remplacer la durée\n\n"
                "Exemple: `/auto Squid Game S0{saison}E{episode}`\n\n"
                "Attention ! : la command /auto n'est prend que 2 arguments ({episode} et {saison})"
                "Utiser cette command pour definir votre caption :\n /set_caption\n"
                "Le caption peut prendre tous ces arguments"
                "Ex de sortie: \nSquid Game S01E01 - 2022\n"
                "Squid Game S01E02 - 2022\n"
                "..."
                
            )
        
        elif data == "configMetadata":
            user_metadata = userinfo.metadata

            def metadata_buttons(field_name, display_name, value):
                if value:  
                    return [
                        InlineKeyboardButton(f"✏ Modifier {display_name}", callback_data=f"editMetadata_{field_name}"),
                        InlineKeyboardButton(f"🗑 Supprimer {display_name}", callback_data=f"deleteMetadata_{field_name}")
                    ]
                else:  
                    return [InlineKeyboardButton(f"➕ Ajouter {display_name}", callback_data=f"addMetadata_{field_name}")]
                
            btn = InlineKeyboardMarkup([
                metadata_buttons("titre", "Titre", user_metadata.titre),
                metadata_buttons("artiste", "Artiste", user_metadata.artiste),
                metadata_buttons("album", "Album", user_metadata.album),
                metadata_buttons("genre", "Genre", user_metadata.genre),
                [InlineKeyboardButton("🔙 Retour", callback_data="help")]
            ])

            caption = (
                "**CONFIGURATION DES MÉTADONNÉES**\n"
                "Cliquez sur une option ci-dessous pour ajouter, modifier ou supprimer une métadonnée.\n\n"
                f"📌 **Titre :** {user_metadata.titre or 'Non défini'}\n"
                f"📌 **Artiste :** {user_metadata.artiste or 'Non défini'}\n"
                f"📌 **Album :** {user_metadata.album or 'Non défini'}\n"
                f"📌 **Genre :** {user_metadata.genre or 'Non défini'}\n"
            )
            
        elif data.startswith(("addMetadata_", "deleteMetadata_", "editMetadata_")):
            action, field = data.split("_")
            user_metadata = userinfo.metadata

            if user_id in waiting_for_response:
                await query.answer("Vous avez déjà une action en cours. Veuillez répondre à la question précédente.", show_alert=True)
                return

            if action == "addMetadata":
                await query.message.edit_text(f"Veuillez entrer la valeur pour {field}:")
                waiting_for_response[user_id] = {"action": action, "field": field, "query_message_id": query.message.id}
                
                asyncio.create_task(reset_waiting_for_response(user_id, query.message, client))
                return  

            elif action == "deleteMetadata":
                setattr(user_metadata, field, None)
                await update_user_metadata(user_id, user_metadata)
                
                confirmation_message = await query.message.reply(f"✅ {field.capitalize()} supprimé avec succès!")
                await asyncio.sleep(3)  
                await confirmation_message.delete() 

            elif action == "editMetadata":
                await query.message.edit_text(f"Veuillez entrer la nouvelle valeur pour {field} dans le 30s:")
                waiting_for_response[user_id] = {"action": action, "field": field, "query_message_id": query.message.id}
                
                asyncio.create_task(reset_waiting_for_response(user_id, query.message, client))
                return 

            userinfo = await read_user(user_id)  
            user_metadata = userinfo.metadata

            def metadata_buttons(field_name, display_name, value):
                if value:  
                    return [
                        InlineKeyboardButton(f"✏ Modifier {display_name}", callback_data=f"editMetadata_{field_name}"),
                        InlineKeyboardButton(f"🗑 Supprimer {display_name}", callback_data=f"deleteMetadata_{field_name}")
                    ]
                else:  
                    return [InlineKeyboardButton(f"➕ Ajouter {display_name}", callback_data=f"addMetadata_{field_name}")]
            
            btn = InlineKeyboardMarkup([
                metadata_buttons("titre", "Titre", user_metadata.titre),
                metadata_buttons("artiste", "Artiste", user_metadata.artiste),
                metadata_buttons("album", "Album", user_metadata.album),
                metadata_buttons("genre", "Genre", user_metadata.genre),
                [InlineKeyboardButton("🔙 Retour", callback_data="help")]
            ])

            caption = (
                "**CONFIGURATION DES MÉTADONNÉES**\n"
                "Cliquez sur une option ci-dessous pour ajouter, modifier ou supprimer une métadonnée.\n\n"
                f"📌 **Titre :** {user_metadata.titre or 'Non défini'}\n"
                f"📌 **Artiste :** {user_metadata.artiste or 'Non défini'}\n"
                f"📌 **Album :** {user_metadata.album or 'Non défini'}\n"
                f"📌 **Genre :** {user_metadata.genre or 'Non défini'}\n"
            )
            
        
        elif data in ["connectChannel", "delchannel", "upload_at"]:
            if data == "delchannel":
                # Déconnecter le canal
                userinfo.channel_dump = {}  
                await update_user(user_id, {"channel_dump": userinfo.channel_dump})
                caption = "✅ Le canal a été déconnecté avec succès."
                await asyncio.sleep(3)  

            

            else:
                # Afficher les informations du canal
                caption = (
                    "LIER UN CANAL AU BOT\n"
                    "Cette fonctionalité vous permet de connecter un canal pour envoyer vos vidéos en ordre après le renommage.\n"
                    "Ajoutez le bot en tant qu'admin de votre canal, puis utilisez la commande `/set_channel [channel_id]` pour me connecter au canal.\n"
                    "Exemple : `/set_channel -1002175858655`\n\n"
                )

            if data == "upload_at":
                # Basculer entre vidéo et document
                userinfo.is_video = not userinfo.is_video  # Inverser la valeur actuelle
                await update_user(user_id, {"is_video": userinfo.is_video})
                # Ne pas modifier le caption, seulement mettre à jour le bouton

            # Mettre à jour les informations du canal
            userinfo = await read_user(user_id)
            channelinfo = userinfo.channel_dump

            if channelinfo:
                try:
                    channel = await client.get_chat(channelinfo["channel_id"])
                    caption += f"Votre canal actuel est :\n {channel.title} \nID: {channel.id}\n"
                    
                    btn = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Déconnecter le canal", callback_data="delchannel")],
                        [InlineKeyboardButton("Retour", callback_data="help")]
                    ])
                except (ChannelInvalid, ChannelPrivate, ChatAdminRequired):
                    caption += "⚠️ Votre canal actuel n'est pas accessible ou n'existe plus.\n"
                    btn = InlineKeyboardMarkup([
                        [InlineKeyboardButton("Retour", callback_data="help")]
                    ])
            else:
                caption += "Aucun canal n'est actuellement configuré.\n"
                btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Retour", callback_data="help")]
                ])

            # Ajouter le bouton toggle pour upload_at
            btn.inline_keyboard.insert(0, [
                InlineKeyboardButton(
                    f"Upload en: {'Video' if userinfo.is_video else 'Document'}",
                    callback_data="upload_at"
                )
            ])
            
        elif data == "premium":
            me = await client.get_me()
            me_username = me.username

            # Créer un lien de partage personnalisé
            invite_link = f"https://t.me/{me_username}?start=refer_{user_id}"

            # Message partageable (encodé pour une URL)
            share_msg = (
                "Je viens de découvrir ce super bot ! 🚀\n"
                f"Rejoins-moi en utilisant ce lien : {invite_link}\n"
                "Renommer les fichiers automatiquement avec ce bot !\n"
                "FONCTIONNALITÉS :\n"
                "- Renommer les fichiers automatiquement\n"
                "- Ajouter des métadonnées personnalisées\n"
                "- Choisir le nom de votre fichier\n"
                "- Choisir le nom de votre album\n"
                "- Choisir le nom de votre artiste\n"
                "- Choisir le nom de votre genre\n"
                "- Choisir l'année de votre film\n"
                "- Ajouter une miniature personnalisée\n"
                "- Lier un canal pour envoyer vos vidéos\n"
                "Et plus encore !\n"
                "Tu peux gagner des points en t'inscrivant et en utilisant le bot !"
            )
            share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(share_msg)}"

            unique_code = str(uuid.uuid4())[:8] 

            telegram_link = f"https://t.me/{me_username}?start=adds_{unique_code}"

            shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, telegram_link)

            point_map = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
            points = random.choice(point_map)

            await update_user(user_id, {"pending_points": points, "unique_code": unique_code})

            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Partager le bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Regarder la publicité", url=shortlink)],
                [InlineKeyboardButton("🔙 Retour", callback_data="help")]
            ])

            caption = (
                "**SUPPORT PREMIUM**\n\n"
                "Vous avez choisi de soutenir notre bot. Vous pouvez le faire de plusieurs manières :\n\n"
                "1. **Faire un don** : Soutenez-nous financièrement en envoyant un don à [Hyoshcoder](https://t.me/hyoshcoder).\n"
                "2. **Partager le bot** : Invitez vos amis à utiliser notre bot en partageant le lien ci-dessous.\n"
                "3. **Regarder une publicité** : Gagnez des points en regardant une petite publicité.\n\n"
                "**Comment ça marche ?**\n"
                "- Chaque fois que vous partagez le bot et qu'un ami s'inscrit, vous gagnez des points.\n"
                "- Les points peuvent varier entre 5 et 20 points par action.\n\n"
                "Merci de votre soutien ! 🙏 [Support](https://t.me/hyoshcoder)"
            )
        
        elif data == "myAccount":
            caption = (
                    "**📌 Mon profil**\n"
                    "━━━━━━\n"
                    f"📅 **Date d'inscription** : {str(userinfo.created_date.strftime('%Y-%m-%d'))}\n"
                    f"🚀 **Points** : {userinfo.type.points}\n"
                    f"👤 **Nom d'utilisateur** : {format_value(userinfo.name)}\n"
                    f"🔢 **ID** : {userinfo.id}\n"
                    f"⚙️ **Type** : {format_value(userinfo.type.type_name)}\n"
                    f"⚖️ **Abonnement** : {format_value(userinfo.type.abonnement)}\n"
                    "━━━━━━\n"
                    "**💬 Métadonnées**\n"
                    f"🎵 **Titre** : {format_value(userinfo.metadata.titre)}\n"
                    f"🎤 **Artiste** : {format_value(userinfo.metadata.artiste)}\n"
                    f"💿 **Album** : {format_value(userinfo.metadata.album)}\n"
                    f"🎭 **Genre** : {format_value(userinfo.metadata.genre)}\n"
                    f"🕒 **Dernière modification** : {str(userinfo.metadata.date_modification.strftime('%Y-%m-%d'))}\n"
                    "━━━━━━\n"
                    "**⚙️ Paramètres personnalisés**\n"
                    f"📝 **Caption** : {format_value(userinfo.caption)}\n"
                    f"📦 **Channel dump** : {format_value(userinfo.channel_dump.get('channel_id') if userinfo.channel_dump else None)}\n"
                    f"🔄 **Format auto** : {format_value(userinfo.auto)}\n"
                    "━━━━━━\n"
                )
            
            if userinfo.queue.files:
                caption += (
                    f"**📄 Mes fichiers**\n"
                    f"━━━━━━\n"
                    f"📄 Nombre de fichiers en attente : {len(userinfo.queue.files)}\n"
                    "━━━━━━\n"
                )
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Voir la Miniature", callback_data="showThumb"), InlineKeyboardButton("Voir Model Auto", callback_data="showAuto")],
                [InlineKeyboardButton("Retour", callback_data="help")]
            ])
        elif data == "showThumb":
            caption = "**📷 Miniature**\n"
            if not userinfo.thumb:
                caption += "Aucune miniature enregistrée."
            
            btn = []
            if userinfo.thumb:
                btn.append([InlineKeyboardButton("Supprimer la Miniature", callback_data="deleteThumb")])
            btn.append([InlineKeyboardButton("Retour", callback_data="myAccount")])
            
            btn = InlineKeyboardMarkup(btn)
        
        elif data == "deleteThumb":
            userinfo.thumb = None
            await update_user(user_id, {"thumb": userinfo.thumb})
            caption = (
                f"**📷 Miniature supprimée**\n"
            )
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Retour", callback_data="myAccount")]
            ])
        
        elif data == "showAuto":
            if userinfo.auto:
                caption = (
                    f"**📌 Format auto**\n"
                    f"`{userinfo.auto}`\n"
                )
            else:
                caption = (
                    f"**📌 Aucun format auto**\n"
                )
            btn = []
            if not userinfo.auto:
                btn.append([InlineKeyboardButton("Configurer Autorename Format", callback_data="configAuto")])
            btn.append([InlineKeyboardButton("Retour", callback_data="myAccount")])
            
            btn = InlineKeyboardMarkup(btn)
        
        elif data == "process":
            caption = (
                "Traitement en cours...\n Vous serez signaler une fois la tache finis"
            )
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Retour", callback_data="myAccount")]
            ])
            await process_user_queue(user_id, client, query)
        else:
            return  
        if img:
            media = InputMediaPhoto(media=img, caption=caption)
            if data == "showThumb":
                if userinfo.thumb:
                    media = InputMediaPhoto(media=userinfo.thumb, caption=caption)
                else:
                    media = InputMediaPhoto(media=img, caption=caption)
            await query.message.edit_media(media=media, reply_markup=btn)
        else:
            await query.message.edit_text(text=caption, reply_markup=btn)

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb_handler(client, query)
    except Exception as e:
        print(f"Erreur lors du traitement du callback : {e}")