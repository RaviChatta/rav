import random
import asyncio
import logging
import uuid
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
            # Handle referral link
            if args and args[0].startswith("refer_"):
                referrer_id = int(args[0].replace("refer_", ""))
                reward = 10
                
                # Check if user already has a referrer
                if await hyoshcoder.is_refferer(user_id):
                    pass  # User already has a referrer
                elif referrer_id != user_id:  # Prevent self-referral
                    referrer = await hyoshcoder.read_user(referrer_id)
                    if referrer:
                        await hyoshcoder.set_referrer(user_id, referrer_id)
                        await hyoshcoder.add_points(referrer_id, reward)
                        
                        # Notify referrer
                        cap = f"🎉 {user.mention} joined using your referral! You earned {reward} points!"
                        await client.send_message(referrer_id, cap)
            
            # Handle ad link
            if args and args[0].startswith("adds_"):
                unique_code = args[0].replace("adds_", "")
                user = await hyoshcoder.get_user_by_code(unique_code)
            
                # If user with that code not found
                if not user:
                    return await message.reply("❌ The link is invalid or already used.")
            
                # Check if code was already used or expired
                expires_at = user.get("expires_at", datetime.datetime.utcnow())
                if user.get("code_used") or datetime.datetime.utcnow() > expires_at:
                    return await message.reply("❌ Link expired or already claimed.")
            
                reward = user.get("expend_points", 0)
                if reward <= 0:
                    return await message.reply("❌ No points available for this code.")
            
                # Reward points
                await hyoshcoder.add_points(user["_id"], reward)
            
                # Mark code as used and reset reward data
                await hyoshcoder.users.update_one(
                    {"_id": user["_id"]},
                    {"$set": {
                        "code_used": True,
                        "expend_points": 0,
                        "unique_code": None,
                        "expires_at": None
                    }}
                )
            
                # Notify link owner
                await client.send_message(
                    user["_id"],
                    f"🎉 Someone used your ad link! You earned {reward} points!"
                )
            
                # Notify the clicker
                await message.reply("🎉 Thanks for supporting us! The link owner has been rewarded.")
  


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
