from datetime import datetime, timedelta
import os
import random
import asyncio
import sys
import time
import traceback
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, InputMediaPhoto
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired, FloodWait, InputUserDeactivated, UserIsBlocked, PeerIdInvalid
from config import settings
from scripts import Txt
from helpers.utils import get_random_photo
from database.data import hyoshcoder
import logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN
is_restarting = False


ON = [[InlineKeyboardButton('mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛɪᴠᴇ́ᴇs', callback_data='metadata_1'),
       InlineKeyboardButton('✅', callback_data='metadata_1')],
      [InlineKeyboardButton('Dᴇ́fɪɴɪʀ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴘᴇʀsᴏɴɴᴀʟɪsᴇ́ᴇs', callback_data='custom_metadata')]]

OFF = [[InlineKeyboardButton('mᴇ́tᴀᴅᴏɴᴇᴇs ᴅᴇ́sᴀᴄᴛɪᴠᴇ́ᴇs', callback_data='metadata_0'),
        InlineKeyboardButton('❌', callback_data='metadata_0')],
       [InlineKeyboardButton('Dᴇ́fɪɴɪʀ ᴅᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴘᴇʀsᴏɴɴᴀʟɪsᴇ́ᴇs', callback_data='custom_metadata')]]


@Client.on_message(filters.private & filters.command(["start", 
                                                      "autorename", 
                                                      "setmedia", 
                                                      "set_caption", 
                                                      "del_caption", 
                                                      "see_caption", 
                                                      "view_caption", 
                                                      "viewthumb", 
                                                      "view_thumb", 
                                                      "del_thumb", 
                                                      "delthumb", 
                                                      "metadata", 
                                                      "donate",
                                                      "premium",
                                                      "plan",
                                                      "bought",
                                                      "help",
                                                      "set_dump",
                                                      "view_dump",
                                                      "viewdump",
                                                      "del_dump",
                                                      "deldump",
                                                      "profile"
                                                      ]))
async def command(client, message: Message):
    user_id = message.from_user.id
    img = await get_random_photo()  
    if message.text.startswith('/'):
        command = message.text.split(' ')[0][1:]  
        cmd, args = message.command[0], message.command[1:]
        try:
            if command == 'start':
                user = message.from_user
                await hyoshcoder.add_user(client, message)
                m = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
                await asyncio.sleep(3)
                await m.delete()  

                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴍᴇs ᴄᴏᴍᴍᴀɴᴅᴇs •", callback_data='help')],
                    [InlineKeyboardButton('• ᴍɪsᴇs à ᴊᴏᴜʀ', url='https://t.me/hyoshassistantbot'),
                     InlineKeyboardButton('sᴜᴘᴘᴏʀᴛ •', url='https://t.me/tout_manga_confondu')],
                    [InlineKeyboardButton('• ᴀ ᴘʀᴏᴘᴏs', callback_data='about'),
                     InlineKeyboardButton('sᴏᴜʀᴄᴇ •', callback_data='source')]
                ])
                
                if args and args[0].startswith("refer_"):
                    referrer_id = int(args[0].replace("refer_", "")) 
                    reward = 10
                    if referrer_id != user_id:
                        referrer = await hyoshcoder.read_user(referrer_id)
                        
                        if referrer:
                            await hyoshcoder.set_referrer(user_id, referrer_id)
                            await hyoshcoder.add_points(referrer_id, reward)
                            cap = f"🎉 {message.from_user.mention} a rejoint le bot grâce à votre invitation ! Vous avez reçu {reward} points."
                            await client.send_message(
                                chat_id = referrer_id,
                                text = cap
                            )
                        else:
                            await message.reply("❌ L'utilisateur qui vous a invité n'existe pas.")

                caption = Txt.START_TXT.format(user.mention)

                if img:
                    await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    await message.reply_text(text=caption, reply_markup=buttons)
                
                if args and args[0].startswith("adds_"):
                    unique_code = args[0].replace("adds_", "")  
                    user = await hyoshcoder.get_user_by_code(unique_code)
                    reward = await hyoshcoder.get_expend_points(user["_id"])

                    if not user:
                        await message.reply("❌ le lien n'est pas valide ou l'avez déjà utilisé.")
                        return

                    await hyoshcoder.add_points(user["_id"], reward)
                    await hyoshcoder.set_expend_points(user["_id"], 0, None)
                    cap = f"🎉 Vous avez gagné {reward} points !"
                    await client.send_message(
                        chat_id = user["_id"],
                        text = cap
                    )

            elif command == "autorename":
                command_parts = message.text.split("/autorename", 1)
                if len(command_parts) < 2 or not command_parts[1].strip():
                    caption = (
                        "**Vᴇᴜɪʟʟᴇᴢ ᴘʀᴏᴠɪᴅᴇʀ ᴜɴ ɴᴏᴜᴠᴇᴀᴜ ɴᴏᴍ ᴀᴘʀès ʟᴀ ᴄᴏᴍᴍᴀɴᴅᴇ /ᴀᴜᴛᴏʀᴇɴᴀᴍᴇ**\n\n"
                        "Pour ᴄᴏᴍᴍᴇɴᴄᴇʀ ʟ'ᴜᴛɪʟɪsᴀᴛɪᴏɴ :\n"
                        "**Fᴏʀᴍᴀᴛ ᴅ'ᴇxᴀᴍᴘʟᴇ :** `ᴍᴏɴSᴜᴘᴇʀVɪᴅᴇᴏ [saison] [episode] [quality]`"
                    )
                    await message.reply_text(caption)
                    return

                format_template = command_parts[1].strip()
                await hyoshcoder.set_format_template(user_id, format_template)
                caption = (
                    f"**🌟 Fᴀɴᴛᴀsᴛɪqᴜᴇ! Vᴏᴜs êᴛᴇs ᴘʀêᴛ ᴀ ʀᴇɴᴏᴍᴍᴇʀ ᴀᴜᴛᴏᴍᴀᴛɪqᴜᴇᴍᴇɴᴛ vᴏᴛʀᴇs ꜰɪʟᴇs.**\n\n"
                    "📩 Iʟ vᴏᴜs sᴜꜰꜰɪᴛ d'ᴇɴᴠᴏʏᴇʀ ʟᴇs ꜰɪʟᴇs qᴜᴇ vᴏᴜs sᴏᴜʜᴀɪᴛᴇᴢ ʀᴇɴᴏᴍᴍᴇʀ.\n\n"
                    f"**Vᴏᴛʀᴇ mᴏᴅèʟᴇ ᴇɴʀᴇɢɪsᴛʀé :** `{format_template}`\n\n"
                    "Rappelez-vous, je vais peut-être renommer vos fichiers lentement mais je les rendrai sûrement parfaits!✨"
                )
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command == "setmedia":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📁 ᴅᴏᴄᴜᴍᴇɴᴛ", callback_data="setmedia_document")],
                    [InlineKeyboardButton("🎥 ᴠɪᴅᴇᴏ", callback_data="setmedia_video")]
                ])
                caption = (
                    "**Vᴇᴜɪʟʟᴇᴢ sᴇʟᴇᴄᴛɪᴏɴɴᴇʀ ʟᴇ ᴛʏᴘᴇ ᴅᴇ ᴍéᴅɪᴀ qᴜᴇ vᴏᴜs sᴏᴜʜᴀɪᴛᴇᴢ ᴅéғɪɴɪʀ :**"
                )
                if img:
                    await message.reply_photo(photo=img, caption=caption, reply_markup=keyboard)
                else:
                    await message.reply_text(text=caption, reply_markup=keyboard)

            elif command == "set_caption":
                if len(message.command) == 1:
                    caption = (
                        "**Dᴏɴɴᴇᴢ ʟᴀ ʟᴇ́ɢᴇɴᴅᴇ\n\nE𝓍ᴀᴍᴘʟᴇ : `/set_caption 📕Nᴏᴍ ➠ : {filename} \n\n🔗 Tᴀɪʟʟᴇ ➠ : {filesize} \n\n⏰ Dᴜʀᴇ́ᴇ ➠ : {duration}`**"
                    )
                    await message.reply_text(caption)
                    return
                new_caption = message.text.split(" ", 1)[1]
                await hyoshcoder.set_caption(message.from_user.id, caption=new_caption)
                caption = ("**Vᴏᴛʀᴇ ʟᴇ́ɢᴇɴᴅᴇ ᴀ ᴇᴛᴇ ᴇnregistrᴇr ᴀᴠᴇᴄ sᴜᴄᴄᴇ̀s ✅**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command == "del_caption":
                old_caption = await hyoshcoder.get_caption(message.from_user.id)
                if not old_caption:
                    caption = ("**Vᴏᴜs n'ᴀᴠᴇᴢ ᴀᴜᴄᴜᴍᴇ ʟᴇ́ɢᴇɴᴅᴇ ❌**")
                    await message.reply_text(caption)
                    return
                await hyoshcoder.set_caption(message.from_user.id, caption=None)
                caption = ("**Vᴏᴛʀᴇ ʟᴇ́ɢᴇɴᴅᴇ ᴀ ᴇᴛᴇ sᴜᴘᴘʀɪᴍᴇ́ᴇ ᴀᴠᴇᴄ sᴜᴄᴄᴇ̀s 🗑️**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command in ['see_caption', 'view_caption']:
                old_caption = await hyoshcoder.get_caption(message.from_user.id)
                if old_caption:
                    caption = (f"**Vᴏᴛʀᴇ ʟᴇ́ɢᴇɴᴅᴇ :**\n\n`{old_caption}`")
                else:
                    caption = ("**Vᴏᴜs n'ᴀᴠᴇᴢ ᴀᴜᴄᴜᴍᴇ ʟᴇ́ɢᴇɴᴅᴇ ❌**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command in ['view_thumb', 'viewthumb']:
                thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
                if thumb:
                    await client.send_photo(chat_id=message.chat.id, photo=thumb)
                else:
                    caption = ("**Vᴏᴜs n'ᴀᴠᴇᴢ ᴀᴜᴄᴜᴍᴇ ᴍɪɴɪᴀᴛᴜʀᴇ ❌**")
                    if img:
                        await message.reply_photo(photo=img, caption=caption)
                    else:
                        await message.reply_text(text=caption)

            elif command in ['del_thumb', 'delthumb']:
                old_thumb = await hyoshcoder.get_thumbnail(user_id)
                if not old_thumb:
                    caption = (
                        "Aucune miniature n'est actuellement definis."
                    )
                    await message.reply_photo(photo=img, caption=caption)
                    return
                
                await hyoshcoder.set_thumbnail(message.from_user.id, file_id=None)
                caption = ("**ᴍɪɴɪᴀᴛᴜʀᴇ sᴜᴘᴘʀɪᴍᴇ́ᴇ ᴀᴠᴇᴄ sᴜᴄᴄᴇ̀s 🗑️**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)
            
            elif command == "metadata":
                ms = await message.reply_text("**Vᴇᴜɪʟʟᴇᴢ ᴘᴀᴛɪᴇɴᴛᴇʀ...**", reply_to_message_id=message.id)
                bool_metadata = await hyoshcoder.get_metadata(message.from_user.id)
                user_metadata = await hyoshcoder.get_metadata_code(message.from_user.id)
                await ms.delete()
                if bool_metadata:
                    await message.reply_text(
                        f"<b>Vᴏᴛʀᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛᴜᴇʟʟᴇs :</b>\n\n➜ {user_metadata} ",
                        reply_markup=InlineKeyboardMarkup(ON),
                    )
                else:
                    await message.reply_text(
                        f"<b>Vᴏᴛʀᴇs mᴇ́tᴀᴅᴏɴᴇᴇs ᴀᴄᴛᴜᴇʟʟᴇs :</b>\n\n➜ {user_metadata} ",
                        reply_markup=InlineKeyboardMarkup(OFF),
                    )
            
            elif command == "donate":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="ʀᴇᴛᴏᴜʀ", callback_data="help"), InlineKeyboardButton(text="ᴘʀᴏᴘʀɪᴇᴛᴀɪʀᴇ", url='https://t.me/hyoshassistantBot')]
                ])
                caption=Txt.DONATE_TXT
                
                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)
            
                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()
            
            elif command == "premium":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("ᴘʀᴏᴘʀɪᴇᴛᴀɪʀᴇ", url="https://t.me/hyoshassistantBot"), InlineKeyboardButton("ғᴇʀᴍᴇʀ", callback_data="close")]
                ])
                caption=Txt.PREMIUM_TXT
                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)
            
                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()
            
            elif command == "plan":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("ᴘᴀʏᴇʀ ᴠᴏᴛʀᴇ ᴀʙᴏɴɴᴇᴍᴇɴᴛ", url="https://t.me/hyoshassistantBot"), InlineKeyboardButton("ғᴇʀᴍᴇʀ", callback_data="close")]
                ])
                caption=Txt.PREPLANS_TXT
                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)
            
                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()
                
            elif command == "bought":
                msg = await message.reply('ᴀᴛᴛᴇɴᴅ, ᴊᴇ ᴠᴇʀɪғɪᴇ...')
                replied = message.reply_to_message

                if not replied:
                    await msg.edit("<b>ᴠᴇᴜɪʟʟᴇᴢ ʀᴇᴘᴏɴᴅʀᴇ ᴀᴠᴇᴄ ʟᴀ ᴄᴀᴘᴛᴜʀᴇ ᴅ'ᴇ́cran ᴅᴇ ᴠᴏᴛʀᴇ ᴘᴀʏᴇᴍᴇɴᴛ ᴘᴏᴜʀ ʟ'ᴀᴄʜᴀᴛ ᴘʀᴇᴍɪᴜᴍ ᴘᴏᴜʀ ᴄᴏɴᴛɪɴᴜᴇʀ.\n\nᴘᴀʀ ᴇxᴀᴍᴘʟᴇ, ᴛᴇ́ʟᴇᴄʜᴀʀɢᴇᴢ ᴅ'ᴀʙᴏʀᴅ ᴠᴏᴛʀᴇ ᴄᴀᴘᴛᴜʀᴇ ᴅ'ᴇ́cran, ᴘᴜɪs ʀᴇᴘᴏɴᴅʀᴇ ᴀᴠᴇᴄ ʟᴀ ᴄᴏᴍᴍᴀɴᴅᴇ '/bought</b>")
                elif replied.photo:
                    await client.send_photo(
                        chat_id=settings.LOG_CHANNEL,
                        photo=replied.photo.file_id,
                        caption=f'<b>ᴜᴛɪʟɪsᴀᴛᴇᴜʀ - {message.from_user.mention}\nɪᴅ ᴜᴛɪʟɪsᴀᴛᴇᴜʀ - <code>{message.from_user.id}</code>\nɴᴏᴍ ᴜᴛɪʟɪsᴀᴛᴇᴜʀ - <code>{message.from_user.username}</code>\nᴘʀᴇɴᴏᴍ - <code>{message.from_user.first_name}</code></b>',
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Close", callback_data="close_data")]
                        ])
                    )
                    await msg.edit_text('<b>Vᴏᴛʀᴇ ᴄᴀᴘᴛᴜʀᴇ ᴅ\'ᴇ́ᴛᴏɪʟᴇ ᴀ ᴇᴛᴇ ᴇɴᴠᴏʏᴇ́ᴇ ᴀᴜx ᴀᴅᴍɪɴs</b>')
            
            elif command == "help":
                bot = await client.get_me()
                mention = bot.mention
                caption = Txt.HELP_TXT.format(mention=mention) 
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ғᴏʀᴍᴀᴛ ᴅᴇ ʀᴇɴᴏᴍᴍᴀɢᴇ ᴀᴜᴛᴏᴍᴀᴛɪǫᴜᴇ •", callback_data='file_names')],
                    [InlineKeyboardButton('• ᴠɪɢɴᴇᴛᴛᴇ', callback_data='thumbnail'), InlineKeyboardButton('ʟᴇ́ɢᴇɴᴅᴇ •', callback_data='caption')],
                    [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴏɴɴᴇ́ᴇs', callback_data='meta'), InlineKeyboardButton('ғᴀɪʀᴇ ᴜɴ ᴅᴏɴ •', callback_data='donate')],
                    [InlineKeyboardButton('• ᴀᴄᴄᴜᴇɪʟ', callback_data='home')]
                ])
                if img:
                    await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    await message.reply_text(text=caption, disable_web_page_preview=True, reply_markup=buttons)
            
            elif command == "set_dump":
                if len(message.command) == 1:
                    caption = "Veuillez entrer l'ID du channel à dumper après la commande.\nEx : `/set_dump -1001234567890`"
                    await message.reply_text(caption)
                else:
                    channel_id = message.command[1]  

                    if not channel_id:  
                        await message.reply_text("Veuillez entrer un ID de channel valide.\nEx : `/set_dump -1001234567890`")
                    else:
                        try:
                            channel_info = await client.get_chat(channel_id)
                            if channel_info:
                                await hyoshcoder.set_user_channel(message.from_user.id, channel_id)
                                await message.reply_text(f"Le channel {channel_id} a été definis comme channel de dump.")
                            else:
                                await message.reply_text("Le channel spécifié n'existe pas ou n'est pas accessible.\nAssurez-vous que je suis admin du channel.")
                        except Exception as e:
                            await message.reply_text(f"Erreur : {e}. Veuillez entrer un ID de channel valide.\nEx : `/set_dump -1001234567890`")
            
            elif command in ["view_dump", "viewdump"]:
                channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
                if channel_id:
                    caption = f"Le channel {channel_id} est actuellement configuré comme channel de dump."
                    await message.reply_text(caption)
                else:
                    caption = "Aucun channel configuré pour le moment."
                    await message.reply_text(caption)

            elif command in ["del_dump", "deldump"]:
                channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
                if channel_id:
                    await hyoshcoder.set_user_channel(message.from_user.id, None)
                    caption = f"Le channel {channel_id} a été supprimé de la liste des channels de dump."
                    await message.reply_text(caption)
                else:
                    caption = "Aucun channel configuré pour le moment."
                    await message.reply_text(caption)
            
            elif command == "profile":
                user = await hyoshcoder.read_user(message.from_user.id)
                caption = f"Username: {message.from_user.username}\n"
                caption += f"First Name: {message.from_user.first_name}\n"
                caption += f"Last Name: {message.from_user.last_name}\n"
                caption += f"User ID: {message.from_user.id}\n"
                caption +=f"Points: {user['points']}\n"
                
                await message.reply_photo(img, caption=caption)
                    
        except FloodWait as e:
            print(f"FloodWait: {e}")
            await asyncio.sleep(e.value)  
        except Exception as e:
            print(f"Erreur inattendue : {e}")
            await message.reply_text("Une erreur s'est produite. Veuillez réessayer plus tard.")

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    mkn = await message.reply_text("Vᴇᴜɪʟʟᴇᴢ ᴘᴀᴛɪᴇɴᴛᴇʀ ...")
    await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)                
    await mkn.edit("**ᴍɪɴɪᴀᴛᴜʀᴇ ᴇɴʀᴇɢɪsᴛʀᴇ́ᴇ ᴀᴠᴇᴄ sᴜᴄᴄᴇ̀s ✅️**")

