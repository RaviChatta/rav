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

from sequence import get_files_sequenced_leaderboard

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
            
            # Handle referral and campaign links
            if args:
                # Handle referral first
                if args[0].startswith("refer_"):
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
            
                # Then handle campaign
                elif args[0].startswith("adds_"):
                    unique_code = args[0].replace("adds_", "")
                    user = await hyoshcoder.get_user_by_code(unique_code)
            
                    if not user:
                        await message.reply("❌ The link is invalid or already used.")
                        return
            
                    reward = await hyoshcoder.get_expend_points(user["_id"])
                    await hyoshcoder.add_points(user["_id"], reward)
                    await hyoshcoder.set_expend_points(user["_id"], 0, None)
            
                    cap = f"🎉 You earned {reward} points!"
                    await client.send_message(
                        chat_id=user["_id"],
                        text=cap
                    )
            
                # Handle points link redemption
                elif args[0].startswith("points_"):
                    code = args[0].replace("points_", "")
                    result = await hyoshcoder.claim_expend_points(user_id, code)
            
                    if result["success"]:
                        await message.reply_text(
                            f"🎉 You claimed {result['points']} points!\nThanks for supporting the bot!"
                        )
                    else:
                        await message.reply_text(f"❌ Could not claim points: {result['error']}")
            
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
        elif cmd == "free_points":
            me = await client.get_me()
            me_username = me.username
            unique_code = str(uuid.uuid4())[:8]
            telegram_link = f"https://t.me/{me_username}?start=adds_{unique_code}"
            invite_link = f"https://t.me/{me_username}?start=refer_{user_id}"
            shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, telegram_link)
            point_map = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
            share_msg = (
                "I just discovered this amazing bot! 🚀\n"
                f"Join me using this link: {invite_link}\n"
                "Automatically rename files with this bot!\n"
                "FEATURES:\n"
                "- Auto-rename files\n"
                "- Add custom metadata\n"
                "- Choose your filename\n"
                "- Choose your album name\n"
                "- Choose your artist name\n"
                "- Choose your genre\n"
                "- Choose your movie year\n"
                "- Add custom thumbnails\n"
                "- Link a channel to send your videos\n"
                "And much more!\n"
                "You can earn points by signing up and using the bot!"
            )
            share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(share_msg)}"
            points = random.choice(point_map)
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Watch Ad", url=shortlink)],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            caption = (
                "**Free Points**\n\n"
                "You chose to support our bot. You can do this in several ways:\n\n"
                "1. **Donate**: Support us financially by sending a donation to [Hyoshcoder](https://t.me/hyoshcoder).\n"
                "2. **Share the Bot**: Invite your friends to use our bot by sharing the link below.\n"
                "3. **Watch an Ad**: Earn points by watching a short ad.\n\n"
                "**How it works?**\n"
                "- Every time you share the bot and a friend signs up, you earn points.\n"
                "- Points can range between 5 and 20 per action.\n\n"
                "Thanks for your support! 🙏 [Support](https://t.me/hyoshcoder)"
            )
        
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
@Client.on_message(filters.command(["leaderboard", "lb"]))
async def leaderboard_command(client: Client, message: Message):
    """Handle /leaderboard command"""
    await show_leaderboard_ui(client, message)

@Client.on_callback_query(filters.regex(r'^lb_(period|type|refresh)_'))
async def leaderboard_callback(client: Client, callback: CallbackQuery):
    """Handle leaderboard button presses"""
    user_id = callback.from_user.id
    data = callback.data
    
    if data.startswith("lb_period_"):
        period = data.split("_")[2]
        await hyoshcoder.set_leaderboard_period(user_id, period)
    elif data.startswith("lb_type_"):
        lb_type = data.split("_")[2]
        await hyoshcoder.set_leaderboard_type(user_id, lb_type)
    elif data == "lb_refresh_":
        await callback.answer("Refreshing leaderboard...")
    
    await show_leaderboard_ui(client, callback)

async def show_leaderboard_ui(client: Client, message: Union[Message, CallbackQuery]):
    """Display the leaderboard with interactive buttons"""
    try:
        msg = message if isinstance(message, Message) else message.message
        user_id = message.from_user.id
        
        period = await hyoshcoder.get_leaderboard_period(user_id)
        lb_type = await hyoshcoder.get_leaderboard_type(user_id)
        
        # Get the appropriate leaderboard data
        if lb_type == "files":
            leaders = await get_files_sequenced_leaderboard(limit=20)
            # Convert to the format expected by the UI
            leaders = [{
                '_id': str(user['_id']),
                'username': user.get('username', f"User {user['_id']}"),
                'value': user['files_sequenced'],
                'rank': idx + 1
            } for idx, user in enumerate(leaders)]
        else:
            leaders = await hyoshcoder.get_leaderboard(period, lb_type, limit=20)
        
        if not leaders:
            text = "📊 No leaderboard data available yet!\n\n"
            if lb_type == "points":
                text += "Earn points by using the bot's features!"
            elif lb_type == "renames":
                text += "Rename files to appear on this leaderboard!"
            elif lb_type == "files":
                text += "Sequence files to appear here!"
        else:
            emoji = {
                "points": "⭐", 
                "renames": "📁", 
                "files": "🧬"
            }.get(lb_type, "🏆")
            
            text = f"🏆 **{period.upper()} {lb_type.upper()} LEADERBOARD**\n\n"
            
            for user in leaders:
                username = user.get('username', f"User {user['_id']}")
                value = user['value']
                text += f"{user['rank']}. {username} - {value} {emoji}"
                if user.get('is_premium'):
                    text += " 💎"
                text += "\n"
        
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    "DAILY" if period != "daily" else f"• DAILY •",
                    callback_data="lb_period_daily"
                ),
                InlineKeyboardButton(
                    "WEEKLY" if period != "weekly" else f"• WEEKLY •",
                    callback_data="lb_period_weekly"
                ),
                InlineKeyboardButton(
                    "MONTHLY" if period != "monthly" else f"• MONTHLY •",
                    callback_data="lb_period_monthly"
                ),
                InlineKeyboardButton(
                    "ALLTIME" if period != "alltime" else f"• ALLTIME •",
                    callback_data="lb_period_alltime"
                )
            ],
            [
                InlineKeyboardButton(
                    "POINTS" if lb_type != "points" else f"• POINTS •",
                    callback_data="lb_type_points"
                ),
                InlineKeyboardButton(
                    "RENAMES" if lb_type != "renames" else f"• RENAMES •",
                    callback_data="lb_type_renames"
                ),
                InlineKeyboardButton(
                    "FILES" if lb_type != "files" else f"• FILES •",
                    callback_data="lb_type_files"
                )
            ],
            [InlineKeyboardButton("🔄 Refresh", callback_data="lb_refresh_")]
        ])
        
        if isinstance(message, CallbackQuery):
            await msg.edit_text(text, reply_markup=buttons)
            await message.answer("Leaderboard updated!")
        else:
            await msg.reply(text, reply_markup=buttons)
            
    except Exception as e:
        logger.error(f"Error showing leaderboard UI: {e}")
        if isinstance(message, CallbackQuery):
            await message.answer("Failed to load leaderboard", show_alert=True)

@Client.on_callback_query(filters.regex(r'^lb_period_'))
async def leaderboard_period_callback(client: Client, callback: CallbackQuery):
    """Handle leaderboard period changes"""
    try:
        user_id = callback.from_user.id
        period = callback.data.split('_')[-1]  # daily, weekly, monthly, alltime
        
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
    """Handle leaderboard type changes"""
    try:
        user_id = callback.from_user.id
        lb_type = callback.data.split('_')[-1]  # points, renames, files
        
        if lb_type not in ["points", "renames", "files"]:
            await callback.answer("Invalid type", show_alert=True)
            return
            
        await hyoshcoder.set_leaderboard_type(user_id, lb_type)
        await show_leaderboard_ui(client, callback)
        await callback.answer(f"Showing {lb_type} leaderboard")
    except Exception as e:
        await callback.answer("Failed to update type", show_alert=True)
        logger.error(f"Type callback error: {e}")
