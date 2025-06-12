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
    Message,
    User
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
from shortzy import Shortzy
from database.data import hyoshcoder
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
import logging

logger = logging.getLogger(__name__)

EMOJI = {
    'error': '❌',
    'success': '✅',
    'warning': '⚠️'
}

async def send_response(client, chat_id, text, delete_after=None):
    msg = await client.send_message(chat_id, text)
    if delete_after:
        asyncio.create_task(auto_delete_message(msg, delete_after))
    return msg

async def auto_delete_message(message, delay):
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass

@Client.on_message(filters.command("genpoints") & filters.private)
async def generate_point_link(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        db = hyoshcoder

        if not all([settings.BOT_USERNAME, settings.TOKEN_ID_LENGTH, settings.SHORTENER_POINT_REWARD]):
            logger.error("Missing required settings")
            return await message.reply("⚠️ Configuration error. Please contact admin.")

        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"
        
        short_url = await get_shortlink(
            url=settings.SHORTED_LINK,
            api=settings.SHORTED_LINK_API,
            link=deep_link
        )

        if not isinstance(short_url, str) or not short_url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid short URL format: {short_url}")
            short_url = deep_link

        try:
            await db.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
            logger.info(f"Point link saved to DB for user {user_id}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            return await message.reply("❌ Failed to save point link. Please try again.")

        await message.reply(
            f"**🎁 Get {settings.SHORTENER_POINT_REWARD} Points**\n\n"
            f"**🔗 Click below link and complete tasks:**\n{short_url}\n\n"
            "**🕒 Link valid for 24 hours | 🧬 One-time use only**",
            disable_web_page_preview=True
        )

    except Exception as e:
        logger.error(f"Unexpected error in generate_point_link: {str(e)}", exc_info=True)
        await message.reply("❌ An unexpected error occurred. Please try again later.")

@Client.on_message(filters.command("refer") & filters.private)
async def refer(client, message):
    try:
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
            f"**You get {settings.REFER_POINT_REWARD} points for every successful referral!**"
        )
    except Exception as e:
        logger.error(f"Error in refer command: {e}")
        await message.reply_text("❌ Failed to generate referral link. Please try again.")

@Client.on_message(filters.command("freepoints") & filters.private)
async def freepoints(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        user = await hyoshcoder.users.find_one({"_id": user_id})
        
        # Generate referral code if not exists
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
        
        # Generate points link
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
                InlineKeyboardButton("🔗 Share Referral", url=f"https://t.me/share/url?url={quote(refer_link)}"),
                InlineKeyboardButton("💰 Earn Points", url=short_url)
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])
        
        caption = (
            "**🎁 Free Points Menu**\n\n"
            "Earn points by:\n"
            f"1. **Sharing** our bot - Earn {settings.REFER_POINT_REWARD} points per referral\n"
            f"2. **Watching ads** - Earn {settings.SHORTENER_POINT_REWARD} points instantly\n\n"
            f"🔗 Your referral link: `{refer_link}`\n"
            f"💰 Your points link: `{short_url}`\n\n"
            "Your points will be added automatically!"
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
        await message.reply_text("❌ Failed to load free points options. Please try again.")

@Client.on_message(filters.command(["view_dump", "viewdump"]) & filters.private)
async def view_dump_channel(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        if channel_id:
            await message.reply_text(
                f"**Current Dump Channel:** {channel_id}"
            )
        else:
            await message.reply_text("No dump channel is currently set.")
    except Exception as e:
        logger.error(f"Error viewing dump channel: {e}")
        await message.reply_text("❌ Failed to retrieve dump channel info.")

@Client.on_message(filters.command(["del_dump", "deldump"]) & filters.private)
async def delete_dump_channel(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        if channel_id:
            await hyoshcoder.set_user_channel(user_id, None)
            await message.reply_text(
                f"**Channel {channel_id} has been removed from dump list.**"
            )
        else:
            await message.reply_text("No dump channel is currently set.")
    except Exception as e:
        logger.error(f"Error deleting dump channel: {e}")
        await message.reply_text("❌ Failed to remove dump channel. Please try again.")

async def handle_point_redemption(client: Client, message: Message, point_id: str):
    try:
        user_id = message.from_user.id
        point_data = await hyoshcoder.get_point_link(point_id)

        if not point_data:
            return await message.reply("**Invalid or expired link...**")

        if point_data['used']:
            return await message.reply("**This link has already been used...**")

        expiry_utc = point_data['expiry'].replace(tzinfo=pytz.UTC)

        if datetime.now(pytz.UTC) > expiry_utc:
            return await message.reply("**Point link expired...**")

        if point_data['user_id'] != user_id:
            return await message.reply("**This link belongs to another user...**")

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
        await message.reply(f"✅ Success! {point_data['points']} points added to your account!")

    except Exception as e:
        logging.error(f"Error during point redemption: {e}")
        await message.reply("**An error occurred. Please try again.**")

@Client.on_message(filters.command(["start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "freepoints", "genpoints",
    "leaderboard", "lb"]) & filters.private)
async def command_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        cmd = message.command[0].lower()
        args = message.command[1:]

        if cmd == 'start':
            await handle_start_command(client, message, args)
        elif cmd == "autorename":
            await handle_autorename(client, message, args)
        elif cmd == "setmedia":
            await handle_setmedia(client, message)
        elif cmd == "set_caption":
            await handle_set_caption(client, message, args)
        elif cmd in ["del_caption", "delcaption"]:
            await handle_del_caption(client, message)
        elif cmd in ["see_caption", "view_caption"]:
            await handle_view_caption(client, message)
        elif cmd in ["viewthumb", "view_thumb"]:
            await handle_view_thumb(client, message)
        elif cmd in ["del_thumb", "delthumb"]:
            await handle_del_thumb(client, message)
        elif cmd == "metadata":
            await handle_metadata(client, message)
        elif cmd in ["donate", "premium", "plan", "bought"]:
            await handle_premium(client, message)
        elif cmd == "help":
            await handle_help(client, message)
        elif cmd == "set_dump":
            await handle_set_dump(client, message, args)
        elif cmd in ["leaderboard", "lb"]:
            await handle_leaderboard(client, message)
        elif cmd == "freepoints":
            await freepoints(client, message)
        elif cmd == "genpoints":
            await generate_point_link(client, message)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Command error: {e}")
        await message.reply_text("⚠️ An error occurred. Please try again.")

async def handle_start_command(client: Client, message: Message, args: list):
    user = message.from_user
    user_id = user.id
    await hyoshcoder.add_user(user_id)
    
    if args:
        arg = args[0]
        if arg.startswith("ref_"):
            await handle_referral(client, user, arg[4:])
        else:
            await handle_point_redemption(client, message, arg)
        return

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

    anim = await get_random_animation()
    img = await get_random_photo()
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

async def handle_referral(client: Client, user: User, referral_code: str):
    referrer = await hyoshcoder.col.find_one({"referral_code": referral_code})
    if referrer and referrer["_id"] != user.id:
        updated = await hyoshcoder.col.update_one(
            {"_id": referrer["_id"]},
            {"$addToSet": {"referrals": user.id}}
        )
        if updated.modified_count > 0:
            await hyoshcoder.col.update_one(
                {"_id": referrer["_id"]},
                {"$inc": {"points": settings.REFER_POINT_REWARD}}
            )
            try:
                await client.send_message(
                    referrer["_id"],
                    f"🎉 You received {settings.REFER_POINT_REWARD} points for referring {user.mention}!"
                )
            except Exception:
                pass

async def handle_autorename(client: Client, message: Message, args: list):
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
    await hyoshcoder.set_format_template(message.from_user.id, format_template)
    await message.reply_text(
        f"✅ <b>Auto-rename template set!</b>\n\n"
        f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
        "Now send me files to rename automatically!"
    )

async def handle_setmedia(client: Client, message: Message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📁 Document", callback_data="setmedia_document")],
        [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
    ])
    await message.reply_text(
        "**Please select the type of media you want to set:**",
        reply_markup=keyboard
    )

async def handle_set_caption(client: Client, message: Message, args: list):
    if len(args) == 0:
        caption = (
            "**Provide the caption\n\nExample : `/set_caption 📕Name ➠ : {filename} \n\n🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**"
        )
        await message.reply_text(caption)
        return
    
    new_caption = message.text.split(" ", 1)[1]
    await hyoshcoder.set_caption(message.from_user.id, new_caption)
    
    img = await get_random_photo()
    caption = "**Your caption has been saved successfully ✅**"
    
    if img:
        await message.reply_photo(photo=img, caption=caption)
    else:
        await message.reply_text(text=caption)

async def handle_del_caption(client: Client, message: Message):
    await hyoshcoder.set_caption(message.from_user.id, None)
    await message.reply_text("✅ Caption removed successfully!")

async def handle_view_caption(client: Client, message: Message):
    current_caption = await hyoshcoder.get_caption(message.from_user.id) or "No caption set"
    await message.reply_text(
        f"📝 <b>Current Caption:</b>\n{current_caption}"
    )

async def handle_view_thumb(client: Client, message: Message):
    thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
    if thumb:
        await message.reply_photo(thumb, caption="Your current thumbnail")
    else:
        await message.reply_text("No thumbnail set")

async def handle_del_thumb(client: Client, message: Message):
    await hyoshcoder.set_thumbnail(message.from_user.id, None)
    await message.reply_text("✅ Thumbnail removed successfully!")

async def handle_metadata(client: Client, message: Message):
    bool_meta = await hyoshcoder.get_metadata(message.from_user.id)
    meta_code = await hyoshcoder.get_metadata_code(message.from_user.id) or "Not set"
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton(
                "✅ Metadata Enabled" if bool_meta else "❌ Metadata Disabled",
                callback_data=f"metadata_{int(not bool_meta)}"
            )
        ],
        [
            InlineKeyboardButton("Set Custom Metadata", callback_data="set_metadata"),
            InlineKeyboardButton("Back", callback_data="help")
        ]
    ])
    
    await message.reply_text(
        f"📝 <b>Metadata Settings</b>\n\n"
        f"Status: {'Enabled ✅' if bool_meta else 'Disabled ❌'}\n"
        f"Current Code:\n<code>{meta_code}</code>",
        reply_markup=keyboard
    )

async def handle_premium(client: Client, message: Message):
    await message.reply_text(
        "🌟 <b>Premium Membership</b>\n\n"
        "Get access to exclusive features:\n"
        "• 2x Points Multiplier\n"
        "• Priority Processing\n"
        "• No Ads\n"
        "• Extended File Size Limits\n\n"
        "Contact @Raaaaavi for premium access!"
    )

async def handle_help(client: Client, message: Message):
    img = await get_random_photo()
    sequential_status = await hyoshcoder.get_sequential_mode(message.from_user.id)
    src_info = await hyoshcoder.get_src_info(message.from_user.id)
    src_txt = "File name" if src_info == "file_name" else "File caption"
    btn_sec_text = f"Sequential {'✅' if sequential_status else '❌'}"
    
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

async def handle_set_dump(client: Client, message: Message, args: list):
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
            await hyoshcoder.set_user_channel(message.from_user.id, channel_id)
            await message.reply_text(
                f"**Channel {channel_id} has been set as the dump channel.**"
            )
    except Exception as e:
        await message.reply_text(
            f"Error: {e}\n"
            "Please enter a valid channel ID.\n"
            "Example: `/set_dump -1001234567890`"
        )

async def handle_leaderboard(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        period = await hyoshcoder.get_leaderboard_period(user_id)
        lb_type = await hyoshcoder.get_leaderboard_type(user_id)

        leaders = []
        if lb_type == "referrals":
            raw = await hyoshcoder.get_referral_leaderboard(period, limit=10)
            leaders = []
            for idx, user in enumerate(raw):
                try:
                    user_info = await client.get_users(user['_id'])
                    username = f"@{user_info.username}" if user_info.username else user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': username,
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
                    username = f"@{user_info.username}" if user_info.username else user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': username,
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
        else:
            raw = await hyoshcoder.get_leaderboard(period, limit=10)
            leaders = []
            for idx, user in enumerate(raw):
                try:
                    user_info = await client.get_users(user['_id'])
                    username = f"@{user_info.username}" if user_info.username else user_info.first_name
                    leaders.append({
                        '_id': str(user['_id']),
                        'username': username,
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

        emoji = {
            "points": "⭐",
            "renames": "📁",
            "referrals": "🎁"
        }.get(lb_type, "🏆")
        
        period_name = {
            "daily": "Daily",
            "weekly": "Weekly",
            "monthly": "Monthly",
            "alltime": "All-Time"
        }.get(period, period.capitalize())
        
        title = f"🏆 **{period_name} Leaderboard - {emoji} {lb_type.capitalize()}**\n\n"
        
        if not leaders:
            body = "No data yet. Start using the bot to enter the leaderboard!"
        else:
            body = ""
            for user in leaders:
                premium_tag = " 💎" if user.get('is_premium') else ""
                body += f"**{user['rank']}.** {user['username']} — `{user['value']}` {emoji}{premium_tag}\n"

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
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])

        img = await get_random_photo()
        if img:
            await message.reply_photo(
                photo=img,
                caption=title + body,
                reply_markup=keyboard
            )
        else:
            await message.reply_text(
                text=title + body,
                reply_markup=keyboard
            )

    except Exception as e:
        logger.error(f"Error in leaderboard command: {e}")
        await message.reply_text("⚠️ Error loading leaderboard. Please try again.")
