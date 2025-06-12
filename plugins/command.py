import string
import random
import asyncio
import secrets
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
from shortzy import Shortzy  # Make sure this is installed
from database.data import hyoshcoder
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
from os import makedirs, path as ospath
import sys
import os
from config import settings
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
import logging

logger = logging.getLogger(__name__)

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
    try:
        user_id = message.from_user.id
        db = hyoshcoder  # Make sure this is properly defined

        if not all([settings.BOT_USERNAME, settings.TOKEN_ID_LENGTH, settings.SHORTENER_POINT_REWARD]):
            logger.error("Missing required settings")
            return await message.reply("⚠️ Configuration error. Please contact admin.")

        # 1. Generate unique ID
        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))

        # 2. Create deep link
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"
        logger.info(f"Generated deep link for user {user_id}: {deep_link}")

        # 3. Shorten the link with retry mechanism
        short_url = await get_shortlink(
            url=settings.SHORTED_LINK,
            api=settings.SHORTED_LINK_API,
            link=deep_link
        )

        # 4. Validate shortened URL
        if not isinstance(short_url, str) or not short_url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid short URL format: {short_url}")
            short_url = deep_link

        # 5. Save to database
        try:
            await db.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
            logger.info(f"Point link saved to DB for user {user_id}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            return await message.reply("❌ Failed to save point link. Please try again.")

        # 6. Send response
        await message.reply(
            f"**🎁 Get {settings.SHORTENER_POINT_REWARD} Points**\n\n"
            f"**🔗 Click below link and complete tasks:**\n{short_url}\n\n"
            "**🕒 Link valid for 24 hours | 🧬 One-time use only**",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Unexpected error in generate_point_link: {str(e)}", exc_info=True)
        await message.reply("❌ An unexpected error occurred. Please try again later.")

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

        await hyoshcoder.users.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "points.balance": point_data['points'],
                    "points.total_earned": point_data['points']
                }
            }
        )


        await hyoshcoder.mark_point_used(point_id)

        await message.reply(f"✅ Sᴜᴄᴄᴇss! {point_data['points']} ᴘᴏɪɴᴛs ᴀᴅᴅᴇᴅ ᴛᴏ ʏᴏᴜʀ ᴀᴄᴄᴏᴜɴᴛ!")

    except Exception as e:
        logging.error(f"Error during point redemption: {e}")
        await message.reply("**Aɴ ᴇʀʀᴏʀ ᴏᴄᴄᴜʀʀᴇᴅ. Pʟᴇᴀsᴇ ᴛʀʏ ᴀɢᴀɪɴ.**")
@Client.on_message(filters.command("refer") & filters.private)
async def refer(client, message):
    user_id = message.from_user.id
    user = await hyoshcoder.users.find_one({"_id": user_id})
    
    if not user or not user.get("referral_code"):
        referral_code = secrets.token_hex(4)
        await hyoshcoder.users.update_one(
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
        f"**You get 100 Pᴏɪɴᴛs for every successful referral!**"
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
            user_id = user.id
            
            # Add user to database
            await hyoshcoder.add_user(user_id)
            
            # Handle /start with arguments
            if args:
                arg = args[0]
            
                # Handle referral code (e.g. /start ref_ABC123)
                if arg.startswith("ref_"):
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
                                {"$inc": {"points": settings.REFER_POINT_REWARD}}  # <-- changed to points
                            )
                            try:
                                await client.send_message(
                                    referrer["_id"],
                                    f"🎉 You received {settings.REFER_POINT_REWARD} points for referring {user.mention}!"
                                )
                            except Exception:
                                pass
            
                # Handle point redemption link (e.g. /start XYZ123)
                else:
                    await handle_point_redemption(client, message, arg)
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
       
@Client.on_message(filters.command("freepoints") & filters.private)
async def freepoints(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        user = await hyoshcoder.users.find_one({"_id": user_id})
        
        # Generate referral link if not exists
        if not user or not user.get("referral_code"):
            referral_code = secrets.token_hex(4)
            await hyoshcoder.users.update_one(
                {"_id": user_id},
                {"$set": {"referral_code": referral_code}},
                upsert=True
            )
        else:
            referral_code = user["referral_code"]
        
        refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
        
        # Generate a points link
        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"
        short_url = await get_shortlink(
            url=settings.SHORTED_LINK,
            api=settings.SHORTED_LINK_API,
            link=deep_link
        )
        
        # Save the points link
        await hyoshcoder.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)

        # Create buttons
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("🔗 Share Referral", url=f"https://t.me/share/url?url={quote(refer_link)}&text=Join%20this%20awesome%20bot!"),
                InlineKeyboardButton("💰 Earn Points", url=short_url)
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])
        
        caption = (
            "**🎁 Free Points Menu**\n\n"
            "**1. Referral Program**\n"
            f"🔗 Your link: `{refer_link}`\n"
            "• Earn 100 points for each successful referral\n\n"
            "**2. Earn Points**\n"
            f"🔗 Click here: {short_url}\n"
            f"• Get {settings.SHORTENER_POINT_REWARD} points instantly\n\n"
            "**3. Watch Ads**\n"
            "• Coming soon!\n\n"
            "Your points will be added automatically when someone uses your links."
        )
        
        img = await get_random_photo()
        if img:
            await message.reply_photo(
                photo=img,
                caption=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
        else:
            await message.reply_text(
                text=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
            
    except Exception as e:
        logger.error(f"Error in freepoints command: {e}")
        await message.reply_text("⚠️ An error occurred. Please try again later.")
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

# --- Command to show leaderboard ---
@Client.on_message(filters.command(["leaderboard", "lb"]))
async def leaderboard_command(client: Client, message: Message):
    try:
        lb_type = "referrals"  # defaulting to referrals now
        if len(message.command) > 1:
            arg = message.command[1].lower()
            if arg in ["points", "renames", "referrals"]:
                lb_type = arg

        sent = await show_leaderboard_ui(client, message, lb_type)
        await asyncio.sleep(60)
        await sent.delete()
        await message.delete()
    except Exception as e:
        logger.error(f"Leaderboard command error: {e}")
        await message.reply_text("⚠️ Error loading leaderboard. Please try again.")

# --- Show leaderboard UI ---
async def show_leaderboard_ui(client: Client, message: Union[Message, CallbackQuery], lb_type: str = None):
    try:
        msg = message if isinstance(message, Message) else message.message
        user_id = message.from_user.id
        period = await hyoshcoder.get_leaderboard_period(user_id)
        lb_type = lb_type or await hyoshcoder.get_leaderboard_type(user_id)

        leaders = []
        if lb_type == "referrals":
            raw = await hyoshcoder.get_referral_leaderboard(period, limit=10)
            leaders = []
            for idx, user in enumerate(raw):
                try:
                    # Try to get user info to display proper name
                    user_info = await client.get_users(user['_id'])
                    username = user_info.username or user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"@{username}" if user_info.username else user_info.first_name,
                        'value': user.get('total_referrals', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })
                except Exception:
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"User {user['_id']}",
                        'value': user.get('total_referrals', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })
        elif lb_type == "renames":
            raw = await hyoshcoder.get_renames_leaderboard(period, limit=10)
            leaders = []
            for idx, user in enumerate(raw):
                try:
                    user_info = await client.get_users(user['_id'])
                    username = user_info.username or user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"@{username}" if user_info.username else user_info.first_name,
                        'value': user.get('value', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })
                except Exception:
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"User {user['_id']}",
                        'value': user.get('value', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })
        else:  # points
            raw = await hyoshcoder.get_leaderboard(period, limit=10)
            leaders = []
            for idx, user in enumerate(raw):
                try:
                    user_info = await client.get_users(user['_id'])
                    username = user_info.username or user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"@{username}" if user_info.username else user_info.first_name,
                        'value': user.get('points', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })
                except Exception:
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': f"User {user['_id']}",
                        'value': user.get('points', 0),
                        'rank': idx + 1,
                        'is_premium': user.get('is_premium', False)
                    })

        emoji = {"points": "⭐", "renames": "📁", "referrals": "🎯"}.get(lb_type, "🏆")
        period_display = {"daily": "Daily", "weekly": "Weekly", "monthly": "Monthly", "alltime": "All-Time"}.get(period, period.capitalize())
        title = f"🏆 **{period_display} {lb_type.capitalize()} Leaderboard**\n\n"

        if not leaders:
            body = "No data yet. Start using the bot to enter the leaderboard!"
        else:
            body = ""
            for user in leaders:
                line = f"**{user['rank']}.** {user['username']} — `{user['value']}` {emoji}"
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
                InlineKeyboardButton("REFERRALS" if lb_type != "referrals" else "• REFERRALS •", callback_data="lb_type_referrals")
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
            await message.answer("⚠️ Failed to load leaderboard.", show_alert=True)

# --- Period Callback ---
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
        await callback.answer(f"Showing {period.capitalize()} leaderboard")
    except Exception as e:
        logger.error(f"Period callback error: {e}")
        await callback.answer("Failed to update period", show_alert=True)

# --- Type Callback ---
@Client.on_callback_query(filters.regex(r'^lb_type_'))
async def leaderboard_type_callback(client: Client, callback: CallbackQuery):
    try:
        user_id = callback.from_user.id
        lb_type = callback.data.split('_')[-1]
        if lb_type not in ["points", "renames", "referrals"]:
            await callback.answer("Invalid type", show_alert=True)
            return
        await hyoshcoder.set_leaderboard_type(user_id, lb_type)
        await show_leaderboard_ui(client, callback)
        await callback.answer(f"Showing {lb_type.capitalize()} leaderboard")
    except Exception as e:
        logger.error(f"Type callback error: {e}")
        await callback.answer("Failed to update type", show_alert=True)
