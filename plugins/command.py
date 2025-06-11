import string
import random
import asyncio
import logging
import uuid
from urllib.parse import quote
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    InputMediaAnimation,
    Message 
)
from pyrogram.errors import FloodWait
from config import settings
from scripts import Txt
from PIL import Image, ImageEnhance
from io import BytesIO
from datetime import datetime, timedelta
import pytz
from pyrogram.errors import PeerIdInvalid
from pyrogram.enums import ChatMemberStatus
from helpers.utils import get_random_photo, get_random_animation, get_shortlink
from database.data import hyoshcoder
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
from os import makedirs, path as ospath
import sys
import os
from config import settings
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

EMOJI = {
    'error': '❌',
    'success': '✅',
    'warning': '⚠️'
}
async def send_response(client, chat_id, text, delete_after=None):
    """Helper function to send responses"""
    msg = await client.send_message(chat_id, text)
    if delete_after:
        asyncio.create_task(auto_delete_message(msg, delete_after))
    return msg

async def auto_delete_message(message, delay):
    """Auto delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN
@Client.on_message(filters.command("genpoints") & filters.private)
async def generate_point_link(client: Client, message: Message):
    user_id = message.from_user.id
    db = hyoshcoder
    
    point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
    deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"
    short_url = await get_shortlink(
        settings.SHORTED_LINK,
        settings.SHORTED_LINK_API,
        deep_link
    )

    if not short_url:
        return await message.reply("**Fᴀɪʟᴇᴅ ᴛᴏ ɢᴇɴᴇʀᴀᴛᴇ ᴘᴏɪɴᴛ ʟɪɴᴋ. Tʀʏ ᴀɢᴀɪɴ ʟᴀᴛᴇʀ.**")

    await db.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)

    await message.reply(
        f"**Gᴇᴛ 100 Pᴏɪɴᴛs**\n\n"
        f"**Cʟɪᴄᴋ ʙᴇʟᴏᴡ ʟɪɴᴋ ᴀɴᴅ ᴄᴏᴍᴘʟᴇᴛᴇ ᴛᴀsᴋs:**\n{short_url}\n\n"
        "**Lɪɴᴋ ᴠᴀʟɪᴅ ғᴏʀ 24 ʜᴏᴜʀs | Oɴᴇ-ᴛɪᴍᴇ ᴜsᴇ ᴏɴʟʏ**",
        disable_web_page_preview=True
    )
async def handle_point_redemption(client: Client, message: Message, point_id: str):
    user_id = message.from_user.id

    try:
        point_data = await hyoshcoder.get_point_link(point_id)

        if not point_data:
            return await message.reply("**Iɴᴠᴀʟɪᴅ ᴏʀ ᴇxᴘɪʀᴇᴅ ʟɪɴᴋ...**")

        if point_data['used']:
            return await message.reply("**Tʜɪs ʟɪɴᴋ ʜᴀs ᴀʟʀᴇᴀᴅʏ ʙᴇᴇɴ ᴜsᴇᴅ...**")

        expiry_utc = point_data['expiry'].replace(tzinfo=pytz.UTC)

        if datetime.now(pytz.UTC) > expiry_utc:
            return await message.reply("**Pᴏɪɴᴛ ʟɪɴᴋ ᴇxᴘɪʀᴇᴅ...**")

        if point_data['user_id'] != user_id:
            return await message.reply("**Tʜɪs ʟɪɴᴋ ʙᴇʟᴏɴɢs ᴛᴏ ᴀɴᴏᴛʜᴇʀ ᴜsᴇʀ...**")

        await hyoshcoder.col.update_one(
            {"_id": user_id},
            {"$inc": {"points": point_data['points']}}  # Changed from token to points
        )

        await hyoshcoder.mark_point_used(point_id)

        await message.reply(f"✅ Sᴜᴄᴄᴇss! {point_data['points']} ᴘᴏɪɴᴛs ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!")

    except Exception as e:
        logging.error(f"Error during point redemption: {e}")
        await message.reply("**Aɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.**")
@Client.on_message(filters.command("refer") & filters.private)
async def refer(client, message):
    user_id = message.from_user.id
    user = await hyoshcoder.col.find_one({"_id": user_id})

    if not user or not user.get("referral_code"):
        referral_code = secrets.token_hex(4)
        await hyoshcoder.col.update_one(
            {"_id": user_id},
            {"$set": {"referral_code": referral_code}},
            upsert=True
        )
    else:
        referral_code = user["referral_code"]

    referrals = user.get("referrals", []) if user else []
    count = len(referrals)

    refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
    await message.reply_text(
        f"**Your Referral Link:**\n{refer_link}\n\n"
        f"**Total Referrals:** {count}\n"
        f"**You get 100 tokens for every successful referral!**"
    )
@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "freepoints", "genpoints"
]))
async def command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_USER_ID  # Check if user is admin
    
    # Admin bypass for all commands
    if is_admin:
        logger.info(f"Admin {user_id} accessed command: {message.command}")

    img = await get_random_photo()
    anim = await get_random_animation()
    
    try:
        cmd = message.command[0].lower()
        args = message.command[1:]

        if cmd == 'start':
            user = message.from_user
            await hyoshcoder.add_user(user_id)
        
            if args:
                arg = args[0]
        
                # Handle referral link with numeric user ID (refer_12345)
                if arg.startswith("refer_"):
                    referrer_id = int(arg.replace("refer_", ""))
                    reward = 10
        
                    if not await hyoshcoder.is_refferer(user_id) and referrer_id != user_id:
                        referrer = await hyoshcoder.read_user(referrer_id)
                        if referrer:
                            await hyoshcoder.set_referrer(user_id, referrer_id)
                            await hyoshcoder.add_points(referrer_id, reward)
                            try:
                                cap = f"🎉 {user.mention} joined using your referral! You earned {reward} points!"
                                await client.send_message(referrer_id, cap)
                            except Exception:
                                pass
        
                # Handle token-based referral (ref_xxx)
                elif arg.startswith("ref_"):
                    referral_code = arg[4:]
                    referrer = await hyoshcoder.col.find_one({"referral_code": referral_code})
                    if referrer and referrer["_id"] != user_id:
                        updated = await hyoshcoder.col.update_one(
                            {"_id": referrer["_id"]},
                            {"$addToSet": {"referrals": user_id}}
                        )
                        if updated.modified_count > 0:
                            await hyoshcoder.col.update_one(
                                {"_id": referrer["_id"]},
                                {"$inc": {"token": settings.REFER_TOKEN}}
                            )
                            try:
                                await client.send_message(
                                    referrer["_id"],
                                    f"**You received {settings.REFER_TOKEN} tokens for referring {user.mention}!**"
                                )
                            except Exception:
                                pass
        
                # Handle token redemption (e.g. /start XYZ123)
                else:
                    await handle_token_redemption(client, message, arg)
                    return

            # Send sticker
            m = await message.reply_sticker("CAACAgIAAxkBAAI0WGg7NBOpULx2heYfHhNpqb9Z1ikvAAL6FQACgb8QSU-cnfCjPKF6HgQ")
            await asyncio.sleep(3)
            await m.delete()

            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("MY COMMANDS", callback_data='help')],
                [InlineKeyboardButton("My Stats", callback_data='mystats'),
                 InlineKeyboardButton("Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton("Earn Points", callback_data='freepoints'),
                 InlineKeyboardButton("Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("Updates", url='https://t.me/Raaaaavi'),
                 InlineKeyboardButton("Support", url='https://t.me/Raaaaavi')]
            ])


            # Send welcome message
            caption = Txt.START_TXT.format(user.mention)

            if anim:
                await message.reply_animation(
                    animation=anim,
                    caption=caption,
                    reply_markup=buttons
                )
            elif img:
                await message.reply_photo(
                    photo=img,
                    caption=caption,
                    reply_markup=buttons
                )
            else:
                await message.reply_text(
                    text=caption,
                    reply_markup=buttons
                )

        elif cmd == "autorename":
            if len(args) == 0:
                await message.reply_text(
                    "**Please provide a rename template**\n\n"
                    "Example:\n"
                    "`/autorename MyFile_[episode]_[quality]`\n\n"
                    "Available placeholders:\n"
                    "[filename], [size], [duration], [date], [time]"
                )
                return

            format_template = ' '.join(args)
            await hyoshcoder.set_format_template(user_id, format_template)
            reply_text = (
                f"✅ <b>Auto-rename template set!</b>\n\n"
                f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
                "Now send me files to rename automatically!"
            )
            await message.reply_text(reply_text)

        elif cmd == "setmedia":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 Document", callback_data="setmedia_document")],
                [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
            ])
            await message.reply_text(
                "**Please select the type of media you want to set:**",
                reply_markup=keyboard
            )

        elif cmd == "set_caption":
            if len(args) == 0:
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

        elif cmd in ["leaderboard", "lb"]:
            await show_leaderboard_ui(client, message)

       
        elif cmd == "set_dump":
            if len(args) == 0:
                await message.reply_text(
                    "Please enter the dump channel ID after the command.\n"
                    "Example: `/set_dump -1001234567890`"
                )
                return

            channel_id = args[0]
            try:
                channel_info = await client.get_chat(channel_id)
                if channel_info:
                    await hyoshcoder.set_user_channel(user_id, channel_id)
                    await message.reply_text(
                        f"**Channel {channel_id} has been set as the dump channel.**"
                    )
            except Exception as e:
                await message.reply_text(
                    f"Error: {e}\n"
                    "Please enter a valid channel ID.\n"
                    "Example: `/set_dump -1001234567890`"
                )

        elif cmd in ["view_dump", "viewdump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                await message.reply_text(
                    f"**Current Dump Channel:** {channel_id}"
                )
            else:
                await message.reply_text("No dump channel is currently set.")

        elif cmd in ["del_dump", "deldump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                await hyoshcoder.set_user_channel(user_id, None)
                await message.reply_text(
                    f"**Channel {channel_id} has been removed from dump list.**"
                )
            else:
                await message.reply_text("No dump channel is currently set.")
                
      # In command.py - Replace the freepoints section with this:
       # In command.py - Update the freepoints section
        elif cmd == "freepoints":
            me = await client.get_me()
            me_username = me.username
            
            # Generate unique code for the user
            unique_code = str(uuid.uuid4())[:8]
            
            # Create two types of links
            referral_link = f"https://t.me/{me_username}?start=refer_{user_id}"
            ad_link = f"https://t.me/{me_username}?start=adds_{unique_code}"
            
            # Shorten both links
            short_referral = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, referral_link)
            short_ad_link = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, ad_link)
            
            # Random points between 5-20
            points = random.randint(5, 20)
            
            # Store the expend points with the unique code
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            
            # Verify and reward for link clicks
            await hyoshcoder.verify_shortlink_click(user_id, "referral")
            
            # Create share message
            share_msg = (
                "I just discovered this amazing bot! 🚀\n"
                "Automatically rename files with this bot!\n"
                f"Join me using this link: {short_referral}\n\n"
                "FEATURES:\n"
                "- Auto-rename files\n"
                "- Add custom metadata\n"
                "- Custom thumbnails\n"
                "- Premium features available\n"
            )
            
            share_msg_encoded = f"https://t.me/share/url?url={quote(short_referral)}&text={quote(share_msg)}"
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Watch Ad", url=short_ad_link)],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            caption = (
                "**Free Points**\n\n"
                "Earn points by:\n"
                "1. **Sharing** our bot with friends\n"
                "2. **Watching** short ads\n\n"
                f"🔗 Your referral link: `{short_referral}`\n"
                f"📌 Your ad link: `{short_ad_link}`\n\n"
                f"🎁 You'll earn {points} points for each successful action!\n\n"
                "Your points will be added automatically when someone uses your links."
            )
            
            if img:
                await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
            else:
                await message.reply_text(text=caption, reply_markup=buttons)
        elif cmd == "help":
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏʀᴇɴᴀᴍᴇ", callback_data='file_names'),
                 InlineKeyboardButton('ᴛʜᴜᴍʙ', callback_data='thumbnail'),
                 InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
                [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta'),
                 InlineKeyboardButton('ᴍᴇᴅɪᴀ', callback_data='setmedia'),
                 InlineKeyboardButton('ᴅᴜᴍᴘ', callback_data='setdump')],
                [InlineKeyboardButton(btn_sec_text, callback_data='sequential'),
                 InlineKeyboardButton('ᴘʀᴇᴍɪᴜᴍ', callback_data='premiumx'),
                 InlineKeyboardButton(f'Source: {src_txt}', callback_data='toggle_src')],
                [InlineKeyboardButton('ʜᴏᴍᴇ', callback_data='home')]
            ])
            
            if img:
                await message.reply_photo(
                    photo=img,
                    caption=Txt.HELP_TXT.format(client.mention),
                    reply_markup=buttons
                )
            else:
                await message.reply_text(
                    text=Txt.HELP_TXT.format(client.mention),
                    reply_markup=buttons
                )

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Command error: {e}")
        await message.reply_text("⚠️ An error occurred. Please try again.")


@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    """Handle thumbnail setting"""
    try:
        mkn = await send_response(client, message.chat.id, "Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await mkn.edit("**Thumbnail saved successfully ✅️**")
        asyncio.create_task(auto_delete_message(mkn, delay=30))
    except Exception as e:
        logger.error(f"Error setting thumbnail: {e}")
        await send_response(
            client,
            message.chat.id,
            f"{EMOJI['error']} Failed to save thumbnail",
            delete_after=15
        )

# In command.py
@Client.on_message(filters.command(["leaderboard", "lb"]))
async def leaderboard_command(client: Client, message: Message):
    try:
        lb_type = "renames"
        if len(message.command) > 1:
            arg = message.command[1].lower()
            if arg in ["points", "renames", "files"]:
                lb_type = arg

        sent = await show_leaderboard_ui(client, message, lb_type)
        await asyncio.sleep(60)
        await sent.delete()
        await message.delete()
    except Exception as e:
        logger.error(f"Leaderboard command error: {e}")
        await message.reply_text("⚠️ Error loading leaderboard. Please try again.")

async def show_leaderboard_ui(client: Client, message: Union[Message, CallbackQuery], lb_type: str = None):
    try:
        msg = message if isinstance(message, Message) else message.message
        user_id = message.from_user.id
        period = await hyoshcoder.get_leaderboard_period(user_id)
        lb_type = lb_type or await hyoshcoder.get_leaderboard_type(user_id)

        if lb_type == "files":
            leaders = await hyoshcoder.get_sequence_leaderboard(10)
            leaders = [{
                '_id': str(user['user_id']),
                'username': user['username'],
                'value': user['files_sequenced'],
                'rank': idx + 1
            } for idx, user in enumerate(leaders)]
        else:
            leaders = await hyoshcoder.get_leaderboard(period, lb_type, limit=10)

        emoji = {"points": "⭐", "renames": "📁", "files": "🧬"}.get(lb_type, "🏆")
        title = f"🏆 **{period.capitalize()} {lb_type.capitalize()} Leaderboard**\n\n"

        if not leaders:
            body = "No data yet. Start using the bot to enter the leaderboard!"
        else:
            body = ""
            for user in leaders:
                uname = user.get('username', f"User {user['_id']}")
                value = user['value']
                line = f"**{user['rank']}.** {uname} — `{value}` {emoji}"
                if user.get('is_premium'):
                    line += " 💎"
                body += line + "\n"

        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("DAILY" if period != "daily" else "• DAILY •", callback_data="lb_period_daily"),
                InlineKeyboardButton("WEEKLY" if period != "weekly" else "• WEEKLY •", callback_data="lb_period_weekly")
            ],
            [
                InlineKeyboardButton("MONTHLY" if period != "monthly" else "• MONTHLY •", callback_data="lb_period_monthly"),
                InlineKeyboardButton("ALLTIME" if period != "alltime" else "• ALLTIME •", callback_data="lb_period_alltime")
            ],
            [
                InlineKeyboardButton("POINTS" if lb_type != "points" else "• POINTS •", callback_data="lb_type_points"),
                InlineKeyboardButton("RENAMES" if lb_type != "renames" else "• RENAMES •", callback_data="lb_type_renames"),
                InlineKeyboardButton("FILES" if lb_type != "files" else "• FILES •", callback_data="lb_type_files")
            ]
        ])

        if isinstance(message, CallbackQuery):
            await msg.edit_text(title + body, reply_markup=keyboard)
            return msg
        else:
            return await msg.reply(title + body, reply_markup=keyboard)

    except Exception as e:
        logger.error(f"Error showing leaderboard UI: {e}")
        if isinstance(message, CallbackQuery):
            await message.answer("Failed to load leaderboard", show_alert=True)

@Client.on_callback_query(filters.regex(r'^lb_period_'))
async def leaderboard_period_callback(client: Client, callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        period = callback.data.split('_')[-1]
        if period not in ["daily", "weekly", "monthly", "alltime"]:
            await callback.answer("Invalid period", show_alert=True)
            return
        await hyoshcoder.set_leaderboard_period(user_id, period)
        await show_leaderboard_ui(client, callback)
        await callback.answer(f"Showing {period} leaderboard")
    except Exception as e:
        await callback.answer("Failed to update period", show_alert=True)
        logger.error(f"Period callback error: {e}")

@Client.on_callback_query(filters.regex(r'^lb_type_'))
async def leaderboard_type_callback(client: Client, callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        lb_type = callback.data.split('_')[-1]
        if lb_type not in ["points", "renames", "files"]:
            await callback.answer("Invalid type", show_alert=True)
            return
        await hyoshcoder.set_leaderboard_type(user_id, lb_type)
        await show_leaderboard_ui(client, callback)
        await callback.answer(f"Showing {lb_type} leaderboard")
    except Exception as e:
        await callback.answer("Failed to update type", show_alert=True)
        logger.error(f"Type callback error: {e}")
