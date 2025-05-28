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



@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile"
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
                    [InlineKeyboardButton("• My Commands •", callback_data='help')],
                    [InlineKeyboardButton('• Updates', url='https://t.me/CulturedTeluguweeb'),
                     InlineKeyboardButton('Support •', url='https://t.me/OngoingCTW')],
                    [InlineKeyboardButton('• About', callback_data='about'),
                     InlineKeyboardButton('Source •', callback_data='source')]
                ])

                if args and args[0].startswith("refer_"):
                    referrer_id = int(args[0].replace("refer_", ""))
                    reward = 10
                    ref = await hyoshcoder.is_refferer(user_id)
                    if ref:
                        return
                    if referrer_id != user_id:
                        referrer = await hyoshcoder.read_user(referrer_id)

                        if referrer:
                            await hyoshcoder.set_referrer(user_id, referrer_id)
                            await hyoshcoder.add_points(referrer_id, reward)
                            cap = f"🎉 {message.from_user.mention} joined the bot through your referral! You received {reward} points."
                            await client.send_message(
                                chat_id=referrer_id,
                                text=cap
                            )
                        else:
                            await message.reply("❌ The user who invited you does not exist.")

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
                        await message.reply("❌ The link is invalid or already used.")
                        return

                    await hyoshcoder.add_points(user["_id"], reward)
                    await hyoshcoder.set_expend_points(user["_id"], 0, None)
                    cap = f"🎉 You earned {reward} points!"
                    await client.send_message(
                        chat_id=user["_id"],
                        text=cap
                    )

            elif command == "autorename":
                command_parts = message.text.split("/autorename", 1)
                if len(command_parts) < 2 or not command_parts[1].strip():
                    caption = (
                        "**Please provide a new name after the /autorename command**\n\n"
                        "To begin using:\n"
                        "**Example Format:** `MyAwesomeVideo [season] [episode] [quality]`"
                    )
                    await message.reply_text(caption)
                    return

                format_template = command_parts[1].strip()
                await hyoshcoder.set_format_template(user_id, format_template)
                caption = (
                    f"**🌟 Fantastic! You are now ready to auto-rename your files.**\n\n"
                    "📩 Just send the files you want renamed.\n\n"
                    f"**Your saved template:** `{format_template}`\n\n"
                    "Remember, I may rename slowly, but I make your files perfect! ✨"
                )
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command == "setmedia":
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📁 Document", callback_data="setmedia_document")],
                    [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
                ])
                caption = "**Please select the type of media you want to set:**"
                if img:
                    await message.reply_photo(photo=img, caption=caption, reply_markup=keyboard)
                else:
                    await message.reply_text(text=caption, reply_markup=keyboard)

            elif command == "set_caption":
                if len(message.command) == 1:
                    caption = (
                        "**Provide the caption\n\nExample : `/set_caption 📕Name ➠ : {filename} \n\n🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**"
                    )
                    await message.reply_text(caption)
                    return
                new_caption = message.text.split(" ", 1)[1]
                await hyoshcoder.set_caption(message.from_user.id, caption=new_caption)
                caption = ("**Your caption has been saved successfully ✅**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command == "del_caption":
                old_caption = await hyoshcoder.get_caption(message.from_user.id)
                if not old_caption:
                    caption = ("**You don't have any caption ❌**")
                    await message.reply_text(caption)
                    return
                await hyoshcoder.set_caption(message.from_user.id, caption=None)
                caption = ("**Your caption has been successfully deleted 🗑️**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command in ['see_caption', 'view_caption']:
                old_caption = await hyoshcoder.get_caption(message.from_user.id)
                if old_caption:
                    caption = (f"**Your caption:**\n\n`{old_caption}`")
                else:
                    caption = ("**You don't have any caption ❌**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command in ['view_thumb', 'viewthumb']:
                thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
                if thumb:
                    await client.send_photo(chat_id=message.chat.id, photo=thumb)
                else:
                    caption = ("**You don't have any thumbnail ❌**")
                    if img:
                        await message.reply_photo(photo=img, caption=caption)
                    else:
                        await message.reply_text(text=caption)

            elif command in ['del_thumb', 'delthumb']:
                old_thumb = await hyoshcoder.get_thumbnail(user_id)
                if not old_thumb:
                    caption = "No thumbnail is currently set."
                    await message.reply_photo(photo=img, caption=caption)
                    return

                await hyoshcoder.set_thumbnail(message.from_user.id, file_id=None)
                caption = ("**Thumbnail successfully deleted 🗑️**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

            elif command == "donate":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton(text="Back", callback_data="help"),
                     InlineKeyboardButton(text="Owner", url='https://t.me/hyoshassistantBot')]
                ])
                caption = Txt.DONATE_TXT

                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)

                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()

            elif command == "premium":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Owner", url="https://t.me/hyoshassistantBot"),
                     InlineKeyboardButton("Close", callback_data="close")]
                ])
                caption = Txt.PREMIUM_TXT
                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)

                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()

            elif command == "plan":
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Pay Your Subscription", url="https://t.me/hyoshassistantBot"),
                     InlineKeyboardButton("Close", callback_data="close")]
                ])
                caption = Txt.PREPLANS_TXT
                if img:
                    yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    yt = await message.reply_text(text=caption, reply_markup=buttons)

                await asyncio.sleep(300)
                await yt.delete()
                await message.delete()

            elif command == "bought":
                msg = await message.reply("Hold on, I’m verifying...")
                replied = message.reply_to_message

                if not replied:
                    await msg.edit("<b>Please reply with a screenshot of your payment for the premium purchase so I can check...</b>")
                elif replied.photo:
                    await client.send_photo(
                        chat_id=settings.LOG_CHANNEL,
                        photo=replied.photo.file_id,
                        caption=(
                            f"<b>User - {message.from_user.mention}\n"
                            f"User ID - <code>{message.from_user.id}</code>\n"
                            f"Username - <code>{message.from_user.username}</code>\n"
                            f"First Name - <code>{message.from_user.first_name}</code></b>"
                        ),
                        reply_markup=InlineKeyboardMarkup([
                            [InlineKeyboardButton("Close", callback_data="close_data")]
                        ])
                    )
                    await msg.edit_text("<b>Your screenshot has been sent to the admins.</b>")
            
            elif command == "help":
                bot = await client.get_me()
                mention = bot.mention
                caption = Txt.HELP_TXT.format(mention=mention) 
                sequential_status = await hyoshcoder.get_sequential_mode(user_id)
                src_info = await hyoshcoder.get_src_info(user_id)
            
                btn_seq_text = "Sequential ✅" if sequential_status else "Sequential ❌"
                src_txt = "File name" if src_info == "file_name" else "File caption"
            
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("• Automatic renaming format •", callback_data='file_names')],
                    [InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), InlineKeyboardButton('Caption •', callback_data='caption')],
                    [InlineKeyboardButton('• Metadata', callback_data='meta'), InlineKeyboardButton('Make a donation •', callback_data='donate')],
                    [InlineKeyboardButton(f'• {btn_seq_text}', callback_data='secanciel'), InlineKeyboardButton('Premium •', callback_data='premiumx')],
                    [InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toogle_src')],
                    [InlineKeyboardButton('• Home', callback_data='home')]
                ])
                caption = Txt.HELP_TXT.format(client.mention)
                if img:
                    await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
                else:
                    await message.reply_text(text=caption, disable_web_page_preview=True, reply_markup=buttons)
            
            elif command == "set_dump":
                if len(message.command) == 1:
                    caption = "Please enter the dump channel ID after the command.\nExample: `/set_dump -1001234567890`"
                    await message.reply_text(caption)
                else:
                    channel_id = message.command[1]
                    if not channel_id:
                        await message.reply_text("Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`")
                    else:
                        try:
                            channel_info = await client.get_chat(channel_id)
                            if channel_info:
                                await hyoshcoder.set_user_channel(message.from_user.id, channel_id)
                                await message.reply_text(f"Channel {channel_id} has been set as the dump channel.")
                            else:
                                await message.reply_text("The specified channel doesn't exist or is not accessible.\nMake sure I'm an admin in the channel.")
                        except Exception as e:
                            await message.reply_text(f"Error: {e}. Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`")
            
            elif command in ["view_dump", "viewdump"]:
                channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
                if channel_id:
                    caption = f"Channel {channel_id} is currently set as the dump channel."
                    await message.reply_text(caption)
                else:
                    await message.reply_text("No dump channel is currently set.")
            
            elif command in ["del_dump", "deldump"]:
                channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
                if channel_id:
                    await hyoshcoder.set_user_channel(message.from_user.id, None)
                    caption = f"Channel {channel_id} has been removed from the dump list."
                    await message.reply_text(caption)
                else:
                    await message.reply_text("No dump channel is currently set.")
            
            elif command == "profile":
                user = await hyoshcoder.read_user(message.from_user.id)
                caption = (
                    f"Username: {message.from_user.username}\n"
                    f"First Name: {message.from_user.first_name}\n"
                    f"Last Name: {message.from_user.last_name}\n"
                    f"User ID: {message.from_user.id}\n"
                    f"Points: {user['points']}\n"
                )
                await message.reply_photo(img, caption=caption)
            
        except FloodWait as e:
            print(f"FloodWait: {e}")
            await asyncio.sleep(e.value)
        
        except Exception as e:
            print(f"Unexpected error: {e}")
            await message.reply_text("An error occurred. Please try again later.")
        
@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    mkn = await message.reply_text("Please wait...")
    await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
    await mkn.edit("**Thumbnail saved successfully ✅️**")
