import random
import uuid
from pyrogram import Client, filters
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired,FloodWait
from urllib.parse import quote
import asyncio
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings

@Client.on_callback_query()
async def cb_handler(client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    img = await get_random_photo() 
    thumb = await hyoshcoder.get_thumbnail(user_id) 
    disable_web_page_preview = False
    src_info = await hyoshcoder.get_src_info(user_id)
    if src_info == "file_name":
                src_txt = "Nom du fichier"
    else:
        src_txt = "Caption du fichier"
    
    # print(f"Callback data received: {data}")  
    
    try:
        if data == "home":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("•  ᴍᴇs ᴄᴏᴍᴍᴀɴᴅᴇs  •", callback_data='help')],
                [InlineKeyboardButton('• ᴍɪsᴇs à ᴊᴏᴜʀ', url='https://t.me/sineur_x_bot'), InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ •', url='https://t.me/sineur_x_bot')],
                [InlineKeyboardButton('• ᴀ ᴘʀᴏᴘᴏs', callback_data='about'), InlineKeyboardButton('sᴏᴜʀᴄᴇ •', callback_data='source')]
            ])
            caption =Txt.START_TXT.format(query.from_user.mention)
        
        elif data == "caption":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url='https://t.me/REQUETE_ANIME_30sbot'), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
            caption = Txt.CAPTION_TXT
        
        elif data == "help":
            secantial_statut = await hyoshcoder.get_sequential_mode(user_id)  
            if secantial_statut:
                btn_sec_text = "Secantiel ✅"
            else:
                btn_sec_text = "Secantiel ❌"

            btn = InlineKeyboardMarkup([
                            [InlineKeyboardButton("• ғᴏʀᴍᴀᴛ ᴅᴇ ʀᴇɴᴏᴍᴍᴀɢᴇ ᴀᴜᴛᴏᴍᴀᴛɪǫᴜᴇ •", callback_data='file_names')],
                            [InlineKeyboardButton('• ᴠɪɢɴᴇᴛᴛᴇ', callback_data='thumbnail'), InlineKeyboardButton('ʟᴇ́ɢᴇɴᴅᴇ •', callback_data='caption')],
                            [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴏɴɴᴇ́ᴇs', callback_data='meta'), InlineKeyboardButton('ғᴀɪʀᴇ ᴜɴ ᴅᴏɴ •', callback_data='donate')],
                            [InlineKeyboardButton(f'• {btn_sec_text}', callback_data='secanciel'), InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ •', callback_data='premiumx')],
                            [InlineKeyboardButton(f'• Extraire depuis : {src_txt}', callback_data='toogle_src')],
                            [InlineKeyboardButton('• ᴀᴄᴄᴜᴇɪʟ', callback_data='home')]
                        ])
            caption =Txt.HELP_TXT.format(client.mention)
        
        elif data == "meta":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
            
            caption =Txt.SEND_METADATA
        
        elif data == "donate":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʀᴇᴛᴏᴜʀ", callback_data="help"), InlineKeyboardButton("ᴘʀᴏᴘʀɪᴇᴛᴀɪʀᴇ •", url='https://t.me/hyoshassistantBot')]
            ])
            caption = Txt.DONATE_TXT
        
        elif data == "file_names":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
            format_template = await hyoshcoder.get_format_template(user_id)
            caption = Txt.FILE_NAME_TXT.format(format_template=format_template)
        
        elif data == "thumbnail":
            caption=Txt.THUMBNAIL_TXT
            btn =InlineKeyboardMarkup([
                [InlineKeyboardButton("• voir la miniature", callback_data="showThumb")],
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
        
        elif data == "metadatax":
            caption=Txt.SEND_METADATA,
            btn=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
            
        elif data == "source":
            caption=Txt.SOURCE_TXT
            btn=InlineKeyboardMarkup([
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="home")]
            ])
        
        elif data == "premiumx":
                caption=Txt.PREMIUM_TXT
                btn=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• Free Points", callback_data="free_points")],
                    [InlineKeyboardButton("• ʀᴇᴛᴏᴜʀ", callback_data="help"), InlineKeyboardButton("ᴀᴄʜᴇᴛᴇʀ ᴘʀᴇᴍɪᴜᴍ •", url='https://t.me/hyoshassistantBot')]
                ])
        
        elif data == "plans":
                caption=Txt.PREPLANS_TXT
                btn=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ᴀᴄʜᴇᴛᴇʀ ᴘʀᴇᴍɪᴜᴍ •", url='https://t.me/hyoshassistantBot')]
                ])
        elif data == "about":
            caption=Txt.ABOUT_TXT
            btn=InlineKeyboardMarkup([
                [InlineKeyboardButton("• sᴜᴘᴘᴏʀᴛ", url='https://t.me/tout_manga_confondu'), InlineKeyboardButton("ᴄᴏᴍᴍᴀɴᴅᴇs •", callback_data="help")],
                [InlineKeyboardButton("• ᴅᴇᴠᴇʟᴏᴘᴇʀ", url='https://t.me/hyoshassistantbot'), InlineKeyboardButton("ɴᴇᴛᴡᴏʀᴋ •", url='https://t.me/tout_manga_confondu')],
                [InlineKeyboardButton("• ʀᴇᴛᴏᴜʀ •", callback_data="home")]
            ])
        
        elif data == "showThumb":
            if thumb:
                caption = "Voici la miniature actuelle"
            else:
                caption = "Aucune miniature actuelle"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ғᴇʀᴍᴇʀ", callback_data="close"), InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data="help")]
            ])
        
        elif data in ["custom_metadata", "metadata_1", "metadata_0"]:
            ON = InlineKeyboardMarkup([
                [InlineKeyboardButton('mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛɪᴠᴇ́ᴇs', callback_data='metadata_1'), InlineKeyboardButton('✅', callback_data='metadata_1')],
                [InlineKeyboardButton('Dᴇ́fɪɴɪʀ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴘᴇʀsᴏɴɴᴀʟɪsᴇ́ᴇs', callback_data='custom_metadata')]
            ])
            
            OFF = InlineKeyboardMarkup([
                [InlineKeyboardButton('mᴇ́tᴀᴅᴏɴᴇᴇs ᴅᴇ́sᴀᴄᴛɪᴠᴇ́ᴇs', callback_data='metadata_0'), InlineKeyboardButton('❌', callback_data='metadata_0')],
                [InlineKeyboardButton('Dᴇ́fɪɴɪʀ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴘᴇʀsᴏɴɴᴀʟɪsᴇ́ᴇs', callback_data='custom_metadata')]
            ])
            
            if data.startswith("metadata_"):
                _bool = data.split("_")[1] == '1'
                user_metadata = await hyoshcoder.get_metadata_code(user_id)
                if _bool:
                    await hyoshcoder.set_metadata(user_id, bool_meta=False)
                    caption = f"<b>Vᴏᴛʀᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛᴜᴇʟʟᴇs :</b>\n\n➜ {user_metadata} "
                    btn = OFF
                else:
                    await hyoshcoder.set_metadata(user_id, bool_meta=True)
                    caption = f"<b>Vᴏᴛʀᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛᴜᴇʟʟᴇs :</b>\n\n➜ {user_metadata} "
                    btn = ON
            elif data == "custom_metadata":
                await query.message.delete()
                try:
                    user_metadata = await hyoshcoder.get_metadata_code(query.from_user.id)
                    metadata_message = f"""
        <b>--Pᴀʀᴀᴍᴇᴛʀᴇs ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs:--</b>

        ➜ <b>mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛᴜᴇʟʟᴇs :</b> {user_metadata}

        <b>Dᴇ́sᴄʀɪᴘᴛɪᴏɴ</b> : Lᴇs mᴇ́tᴀᴅᴏɴᴇᴇs vᴏɴᴛ mᴏdɪꜰɪᴇʀ ʟᴇs fɪʟᴇs vɪᴅᴇᴏ MKV, ʏ ɪɴclᴜᴇɴs tᴏᴜᴛs ʟᴇs tɪᴛʀᴇs ᴀᴜᴅɪᴏ, sᴛʀᴇᴀᴍs ᴇᴛ sᴜʙᴛɪᴛʀᴇs.

        <b>➲ Eɴvᴏʏᴇᴢ ʟᴇ tɪᴛʀᴇ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs. Dᴇ́ʟᴀɪ : 60 sᴇc</b>
        """

                    metadata = await client.ask(
                        text=metadata_message,
                        chat_id=query.from_user.id,
                        filters=filters.text,
                        timeout=60,
                        disable_web_page_preview=True,
                    )
                except asyncio.TimeoutError:
                    await client.send_message(
                        chat_id=query.from_user.id,
                        text="⚠️ Eʀʀᴇᴜʀ !!\n\n**Lᴀ dᴇᴍᴀɴᴅᴇ ᴀ ᴇxᴘɪʀᴇ́ᴇ.**\nRᴇ́dᴇᴍᴀʀʀᴇᴢ ᴇɴ ᴜtilisant /metadata",
                    )
                    return
                
                try:
                    ms = await client.send_message(
                        chat_id=query.from_user.id,
                        text="**Vᴇᴜɪʟʟᴇᴢ ᴘᴀᴛɪᴇɴᴛᴇʀ...**",
                        reply_to_message_id=query.message.id,
                    )
                    await hyoshcoder.set_metadata_code(
                        query.from_user.id, metadata_code=metadata.text
                    )
                    await ms.edit("**Vᴏᴛʀᴇ cᴏᴅᴇ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴀ ᴇᴛᴇ ᴅᴇ́fɪɴɪ ᴀᴠᴇᴄ sᴜᴄᴄᴇ̀s ✅**")
                    return
                except Exception as e:
                    await client.send_message(
                        chat_id=query.from_user.id,
                        text=f"**Uɴᴇ ᴇʀʀᴇᴜʀ ᴇsᴛ sᴜʀᴠᴇᴜ :** {str(e)}",
                    )
                    return  
            
        elif data == "free_points":
            me = await client.get_me()
            me_username = me.username
            unique_code = str(uuid.uuid4())[:8]
            telegram_link = f"https://t.me/{me_username}?start=adds_{unique_code}"
            invite_link = f"https://t.me/{me_username}?start=refer_{user_id}"
            shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, telegram_link)
            point_map = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
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
            points = random.choice(point_map)
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Partager le bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Regarder la publicité", url=shortlink)],
                [InlineKeyboardButton("🔙 Retour", callback_data="help")]
            ])
            caption = (
                "**Free Points**\n\n"
                "Vous avez choisi de soutenir notre bot. Vous pouvez le faire de plusieurs manières :\n\n"
                "1. **Faire un don** : Soutenez-nous financièrement en envoyant un don à [Hyoshcoder](https://t.me/hyoshcoder).\n"
                "2. **Partager le bot** : Invitez vos amis à utiliser notre bot en partageant le lien ci-dessous.\n"
                "3. **Regarder une publicité** : Gagnez des points en regardant une petite publicité.\n\n"
                "**Comment ça marche ?**\n"
                "- Chaque fois que vous partagez le bot et qu'un ami s'inscrit, vous gagnez des points.\n"
                "- Les points peuvent varier entre 5 et 20 points par action.\n\n"
                "Merci de votre soutien ! 🙏 [Support](https://t.me/hyoshcoder)"
            )
        
        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            await hyoshcoder.set_media_preference(user_id, media_type)
            caption = f"**Pʀéғéʀᴇɴᴄᴇ ᴅᴇ ᴍéᴅɪᴀ déғɪɴɪᴇ sᴜʀ :** {media_type} ✅"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("ʀᴇᴛᴏᴜʀ •", callback_data='help')]
            ])
            
        
        elif data == "secanciel":
            await hyoshcoder.toggle_sequential_mode(user_id)
            secanticel = await hyoshcoder.get_sequential_mode(user_id)
            if secanticel:
                btn_sec_text = "Secantiel ✅"
            else:
                btn_sec_text = "Secantiel ❌"
            btn = InlineKeyboardMarkup([
                            [InlineKeyboardButton("• ғᴏʀᴍᴀᴛ ᴅᴇ ʀᴇɴᴏᴍᴍᴀɢᴇ ᴀᴜᴛᴏᴍᴀᴛɪǫᴜᴇ •", callback_data='file_names')],
                            [InlineKeyboardButton('• ᴠɪɢɴᴇᴛᴛᴇ', callback_data='thumbnail'), InlineKeyboardButton('ʟᴇ́ɢᴇɴᴅᴇ •', callback_data='caption')],
                            [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴏɴɴᴇ́ᴇs', callback_data='meta'), InlineKeyboardButton('ғᴀɪʀᴇ ᴜɴ ᴅᴏɴ •', callback_data='donate')],
                            [InlineKeyboardButton(f'• {btn_sec_text}', callback_data='secanciel'), InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ •', callback_data='premiumx')],
                            [InlineKeyboardButton(f'• Extraire depuis : {src_txt}', callback_data='toogle_src')],
                            [InlineKeyboardButton('• ᴀᴄᴄᴜᴇɪʟ', callback_data='home')]
                        ])
            caption =Txt.HELP_TXT.format(client.mention)
            
        elif data == "toogle_src":
            await hyoshcoder.toogle_src_info(user_id)
            secanticel = await hyoshcoder.get_sequential_mode(user_id)
            if secanticel:
                btn_sec_text = "Secantiel ✅"
            else:
                btn_sec_text = "Secantiel ❌"
            src_info = await hyoshcoder.get_src_info(user_id)
            if src_info == "file_name":
                        src_txt = "Nom du fichier"
            else:
                src_txt = "Caption du fichier"
            btn = InlineKeyboardMarkup([
                            [InlineKeyboardButton("• ғᴏʀᴍᴀᴛ ᴅᴇ ʀᴇɴᴏᴍᴍᴀɢᴇ ᴀᴜᴛᴏᴍᴀᴛɪǫᴜᴇ •", callback_data='file_names')],
                            [InlineKeyboardButton('• ᴠɪɢɴᴇᴛᴛᴇ', callback_data='thumbnail'), InlineKeyboardButton('ʟᴇ́ɢᴇɴᴅᴇ •', callback_data='caption')],
                            [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴏɴɴᴇ́ᴇs', callback_data='meta'), InlineKeyboardButton('ғᴀɪʀᴇ ᴜɴ ᴅᴏɴ •', callback_data='donate')],
                            [InlineKeyboardButton(f'• {btn_sec_text}', callback_data='secanciel'), InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ •', callback_data='premiumx')],
                            [InlineKeyboardButton(f'• Extraire depuis : {src_txt}', callback_data='toogle_src')],
                            [InlineKeyboardButton('• ᴀᴄᴄᴜᴇɪʟ', callback_data='home')]
                        ])
            caption =Txt.HELP_TXT.format(client.mention)
        
        elif data == "close":
            try:
                await query.message.delete()
                await query.message.reply_to_message.delete()
                await query.message.continue_propagation()
            except:
                await query.message.delete()
                await query.message.continue_propagation()
        else:
            return
            
        if img:
            media = InputMediaPhoto(media=img, caption=caption)
            if data in ["showThumb", "thumbnail"]:
                if thumb:
                    media = InputMediaPhoto(media=thumb, caption=caption)
                else:
                    media = InputMediaPhoto(media=img, caption=caption)
                if data == "about":
                    disable_web_page_preview=True
            await query.message.edit_media(media=media, reply_markup=btn)
        else:
            await query.message.edit_text(text=caption, reply_markup=btn, disable_web_page_preview=disable_web_page_preview)
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb_handler(client, query)
    except Exception as e:
        pass