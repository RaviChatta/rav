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

from config import settings  # make sure you're importing the instance, not the class

@Client.on_message(filters.command("genpoints") & filters.private)
async def generate_point_link(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        db = hyoshcoder

        if not all([settings.BOT_USERNAME, settings.TOKEN_ID_LENGTH, settings.SHORTENER_POINT_REWARD]):
            logger.error("Missing required settings")
            return await message.reply("⚠️ Configuration error. Please contact admin.")

        # Generate a deep link token
        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"

        # 🔁 Use a new random shortener each time
        shortener = settings.get_random_shortener()
        shorted_link = shortener["domain"]
        shorted_api = shortener["api"]

        # Attempt to shorten the link
        short_url = await get_shortlink(
            url=shorted_link,
            api=shorted_api,
            link=deep_link
        )

        # Fallback if shortening failed
        if not isinstance(short_url, str) or not short_url.startswith(('http://', 'https://')):
            logger.warning(f"Invalid short URL format: {short_url}")
            short_url = deep_link

        # Save to DB
        try:
            await db.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
            logger.info(f"Point link saved to DB for user {user_id}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            return await message.reply("❌ Failed to save point link. Please try again.")

        # Send reply
        bot_reply = await message.reply(
            f"**🎁 Get {settings.SHORTENER_POINT_REWARD} Points**\n\n"
            f"**🔗 Click below link and complete tasks:**\n{short_url}\n\n"
            "**🕒 Link valid 30 seconds | 🧬 verify more links to get more points**",
            disable_web_page_preview=True
        )

        # Auto-delete after 30s
        await asyncio.sleep(30)
        await message.delete()
        await bot_reply.delete()

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

        # ✅ Use a new random shortener for each user
        shortener = settings.get_random_shortener()
        shorted_link = shortener["domain"]
        shorted_api = shortener["api"]

        # Attempt to shorten the deep link
        short_url = await get_shortlink(url=shorted_link, api=shorted_api, link=deep_link)

        if not isinstance(short_url, str) or not short_url.startswith(("http://", "https://")):
            short_url = deep_link

        # Save the generated point link
        await hyoshcoder.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)

        # Prepare buttons and caption
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])

        caption = (
            "**🎁 Free Points Menu**\n\n"
            "Earn points by:\n"
            f"1. **Referring users** – `{refer_link}`\n"
            f"   ➤ {settings.REFER_POINT_REWARD} points per referral\n"
            f"2. **Watching sponsored content** –\n"
            f"   ➤ {settings.SHORTENER_POINT_REWARD} points\n\n"
            f"🎯 Your points link:\n`{short_url}`\n\n"
            "⏱ Points are added automatically!"
        )

        # Optional image (if you use `get_random_photo`)
        try:
            img = await get_random_photo()
            await message.reply_photo(
                photo=img,
                caption=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )
        except:
            await message.reply_text(
                text=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )

        # Delete both after 30 seconds
        await asyncio.sleep(30)
        await message.delete()

    except Exception as e:
        logger.error(f"Error in /freepoints: {e}", exc_info=True)
        await message.reply_text("❌ Failed to generate free points. Try again.")


@Client.on_message(filters.command(["view_dump", "viewdump"]) & filters.private)
async def view_dump_channel(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        if channel_id:
            await message.reply_text(
                f"**Current Dump Channel:** `{channel_id}`",
                quote=True
            )
        else:
            await message.reply_text(
                "No dump channel is currently set.",
                quote=True
            )
    except Exception as e:
        logger.error(f"Error viewing dump channel: {e}")
        await message.reply_text(
            "❌ Failed to retrieve dump channel info.",
            quote=True
        )


@Client.on_message(filters.command(["del_dump", "deldump"]) & filters.private)
async def delete_dump_channel(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        if channel_id:
            # Assuming hyoshcoder.set_user_channel(user_id, None) clears it properly
            success = await hyoshcoder.set_user_channel(user_id, None)
            if success:
                await message.reply_text(
                    f"✅ Channel `{channel_id}` has been removed from your dump list.",
                    quote=True
                )
            else:
                await message.reply_text(
                    "❌ Failed to remove dump channel. Please try again.",
                    quote=True
                )
        else:
            await message.reply_text(
                "No dump channel is currently set.",
                quote=True
            )
    except Exception as e:
        logger.error(f"Error deleting dump channel: {e}")
        await message.reply_text(
            "❌ Failed to remove dump channel. Please try again.",
            quote=True
        )

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
@Client.on_callback_query(filters.regex(r"^setmedia_(document|video)$"))
async def set_media_preference_handler(client: Client, callback_query: CallbackQuery):
    media_type = callback_query.data.split("_")[1]  # 'document' or 'video'
    user_id = callback_query.from_user.id

    success = await hyoshcoder.set_media_preference(user_id, media_type)
    if success:
        await callback_query.answer(f"Media type set to {media_type.capitalize()} ✅", show_alert=True)
        await callback_query.message.edit_text(f"✅ Your media preference has been set to: **{media_type.capitalize()}**")
    else:
        await callback_query.answer("Failed to update media preference ❌", show_alert=True)
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

    buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton("MY COMMANDS", callback_data='help')],
        [InlineKeyboardButton("My Stats", callback_data='mystats')],
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

async def handle_premium(client: Client, message: Message):
    await message.reply_text(
        "🌟 <b>Premium Membership Not Available</b>\n\n"
        "Premium is not available at the moment. Meanwhile, use your points to unlock benefits!\n\n"
        "Generate more points with:\n"
        "/genpoints or /freepoints\n\n"
        "Keep collecting points and stay tuned for Premium features like:\n"
        "• 2x Points Multiplier\n"
        "• Priority Processing\n"
        "• No Ads\n"
        "• Extended File Size Limits\n\n"
        "Start earning points now!"
    )



async def handle_help(client: Client, message: Message):
    user_id = message.from_user.id
    img = await get_random_photo()
    sequential_status = await hyoshcoder.get_sequential_mode(user_id)
    src_info = await hyoshcoder.get_src_info(user_id)

    btn_seq_text = "ˢᵉᑫ✅" if sequential_status else "ˢᵉᑫ❌"
    src_txt = "File name" if src_info == "file_name" else "File caption"

    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("ᴬᵁᵀᴼ", callback_data='file_names'),
            InlineKeyboardButton("ᵀᴴᵁᴹᴮ", callback_data='thumbnail'),
            InlineKeyboardButton("ᶜᴬᴾᵀᴵᴼᴺ", callback_data='caption')
        ],
        [
            InlineKeyboardButton("ᴹᴱᵀᴬ", callback_data='meta'),
            InlineKeyboardButton("ᴹᴱᴰᴵᴬ", callback_data='setmedia'),
            InlineKeyboardButton("ᴰᵁᴹᴾ", callback_data='setdump')
        ],
        [
            InlineKeyboardButton(btn_seq_text, callback_data='sequential'),
            InlineKeyboardButton("ᴾᴿᴱᴹ", callback_data='premiumx'),
            InlineKeyboardButton(f"ˢᴿᶜ: {src_txt}", callback_data='toggle_src')
        ],
        [
            InlineKeyboardButton("ᴴᴼᴹᴱ", callback_data='home')
        ]
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

from pyrogram.errors import ChatAdminRequired, PeerIdInvalid

async def handle_set_dump(client: Client, message: Message, args: list):
    if len(args) == 0:
        return await message.reply_text(
            "❗️ Please provide the dump channel ID after the command.\n"
            "Example: `/set_dump -1001234567890`",
            quote=True
        )

    channel_id = args[0]

    try:
        # Try getting chat info
        chat = await client.get_chat(channel_id)

        # Check if bot is a member
        member = await client.get_chat_member(channel_id, client.me.id)
        if not member or not member.can_post_messages:
            return await message.reply_text(
                "❌ I need to be **admin with posting permissions** in that channel.\n"
                "Please make me admin and try again."
            )

        # Save to database
        await hyoshcoder.set_user_channel(message.from_user.id, channel_id)
        await message.reply_text(
            f"✅ Channel `{channel_id}` has been successfully set as your dump channel.",
            quote=True
        )

    except PeerIdInvalid:
        await message.reply_text(
            "❌ Invalid channel ID format.\n"
            "Make sure to use full ID like: `-1001234567890`",
            quote=True
        )
    except ChatAdminRequired:
        await message.reply_text(
            "❌ I'm not an admin in that channel.\n"
            "Please promote me and try again.",
            quote=True
        )
    except Exception as e:
        await message.reply_text(
            f"❌ Error: `{str(e)}`\n\n"
            "Ensure the channel exists, and I'm a member with proper rights.",
            quote=True
        )

@Client.on_message((filters.group | filters.private) & filters.command("leaderboard"))
async def leaderboard_handler(bot: Client, message: Message):
    try:
        user_id = message.from_user.id if message.from_user else None
        period = await hyoshcoder.get_leaderboard_period(user_id) if user_id else "weekly"
        lb_type = await hyoshcoder.get_leaderboard_type(user_id) if user_id else "points"

        async def generate_leaderboard(period_filter, lb_type_filter):
            # Get leaderboard data based on type
            if lb_type_filter == "points":
                leaders = await hyoshcoder.get_leaderboard(period_filter, limit=10)
                value_key = "points"
                emoji = "⭐"
            elif lb_type_filter == "renames":
                leaders = await hyoshcoder.get_renames_leaderboard(period_filter, limit=10)
                value_key = "total_renames"
                emoji = "📁"
            else:  # referrals
                leaders = await hyoshcoder.get_referral_leaderboard(period_filter, limit=10)
                value_key = "total_referrals"
                emoji = "🎁"

            # Prepare leaderboard display
            period_name = {
                "daily": "Today's",
                "weekly": "This Week's",
                "monthly": "This Month's",
                "alltime": "All-Time"
            }.get(period_filter, period_filter.capitalize())
            
            title = f"🏆 <b>{period_name} Leaderboard - {emoji} {lb_type_filter.capitalize()}</b>\n\n"
            
            if not leaders:
                return None
            
            leaderboard = [title]
            
            # Get user's rank if available
            user_rank = None
            user_value = 0
            
            if user_id:
                if lb_type_filter == "points":
                    user_data = await hyoshcoder.get_user(user_id)
                    if user_data:
                        user_value = user_data["points"]["balance"]
                        user_rank = await hyoshcoder.users.count_documents({
                            "points.balance": {"$gt": user_value},
                            "ban_status.is_banned": False
                        }) + 1
                elif lb_type_filter == "renames":
                    user_stats = await hyoshcoder.file_stats.aggregate([
                        {"$match": {"user_id": user_id}},
                        {"$group": {"_id": None, "total": {"$sum": 1}}}
                    ]).to_list(1)
                    if user_stats:
                        user_value = user_stats[0]["total"]
                        user_rank = await hyoshcoder.file_stats.aggregate([
                            {"$group": {"_id": "$user_id", "total": {"$sum": 1}}},
                            {"$match": {"total": {"$gt": user_value}}},
                            {"$count": "total"}
                        ]).to_list(1)
                        user_rank = (user_rank[0]["total"] + 1) if user_rank else 1
                else:  # referrals
                    user_data = await hyoshcoder.get_user(user_id)
                    if user_data:
                        user_value = user_data["referral"]["referred_count"]
                        user_rank = await hyoshcoder.users.count_documents({
                            "referral.referred_count": {"$gt": user_value},
                            "ban_status.is_banned": False
                        }) + 1
            
            # Format leaderboard entries
            for idx, user in enumerate(leaders, 1):
                try:
                    # Try to get fresh user info from Telegram
                    tg_user = await bot.get_users(int(user["_id"]))
                    name = html.escape(tg_user.first_name or "Anonymous")
                    username = f"@{tg_user.username}" if tg_user.username else "No UN"
                except Exception:
                    # Fallback to stored username or user ID
                    name = html.escape(user.get("username", f"User {user['_id']}"))
                    username = f"@{user['username']}" if user.get("username") else "No UN"
                
                premium_tag = " 💎" if user.get("is_premium", False) else ""
                leaderboard.append(
                    f"{idx}. <b>{name}</b> "
                    f"(<code>{username}</code>) ➜ "
                    f"<i>{user.get(value_key, 0)} {lb_type_filter} {emoji}{premium_tag}</i>"
                )
            
            # Add user's rank if available
            if user_rank is not None:
                leaderboard.append(f"\n<b>Your Rank:</b> {user_rank} with {user_value} {lb_type_filter}")
            
            leaderboard.append(f"\nLast updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
            leaderboard.append(f"\n<i>**This message will auto-delete in {settings.LEADERBOARD_DELETE_TIMER} seconds**</i>")
            
            return "\n".join(leaderboard)
        
        # Generate initial leaderboard
        leaderboard_text = await generate_leaderboard(period, lb_type)
        
        if not leaderboard_text:
            no_data_msg = await message.reply_text("<blockquote>No leaderboard data available yet!</blockquote>")
            await asyncio.sleep(10)
            await no_data_msg.delete()
            return
        
        # Create inline keyboard
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("DAILY" if period != "daily" else "• DAILY •", callback_data=f"lb_period_daily_{lb_type}"),
                InlineKeyboardButton("WEEKLY" if period != "weekly" else "• WEEKLY •", callback_data=f"lb_period_weekly_{lb_type}"),
                InlineKeyboardButton("MONTHLY" if period != "monthly" else "• MONTHLY •", callback_data=f"lb_period_monthly_{lb_type}")
            ],
            [
                InlineKeyboardButton("ALLTIME" if period != "alltime" else "• ALLTIME •", callback_data=f"lb_period_alltime_{lb_type}"),
            ],
            [
                InlineKeyboardButton("POINTS" if lb_type != "points" else "• POINTS •", callback_data=f"lb_type_points_{period}"),
                InlineKeyboardButton("RENAMES" if lb_type != "renames" else "• RENAMES •", callback_data=f"lb_type_renames_{period}"),
                InlineKeyboardButton("REFERRALS" if lb_type != "referrals" else "• REFERRALS •", callback_data=f"lb_type_referrals_{period}")
            ]
        ])
        
        sent_msg = await message.reply_text(
            leaderboard_text,
            reply_markup=keyboard
        )
        
        # Callback handler for leaderboard updates
        @Client.on_callback_query(filters.regex(r"^lb_(period|type)_"))
        async def leaderboard_callback(client: Client, callback_query: CallbackQuery):
            if callback_query.from_user.id != user_id:
                await callback_query.answer("This is not your leaderboard!", show_alert=True)
                return
            
            data_parts = callback_query.data.split("_")
            filter_type = data_parts[1]  # "period" or "type"
            selected_value = data_parts[2]  # "daily", "points", etc.
            
            # Update user preferences
            if filter_type == "period":
                if user_id:
                    await hyoshcoder.set_leaderboard_period(user_id, selected_value)
                period = selected_value
            else:  # type
                if user_id:
                    await hyoshcoder.set_leaderboard_type(user_id, selected_value)
                lb_type = selected_value
            
            # Generate updated leaderboard
            new_leaderboard = await generate_leaderboard(period, lb_type)
            
            if not new_leaderboard:
                await callback_query.answer("No data available for this filter", show_alert=True)
                return
            
            # Update keyboard with current selections
            new_keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("DAILY" if period != "daily" else "• DAILY •", callback_data=f"lb_period_daily_{lb_type}"),
                    InlineKeyboardButton("WEEKLY" if period != "weekly" else "• WEEKLY •", callback_data=f"lb_period_weekly_{lb_type}"),
                    InlineKeyboardButton("MONTHLY" if period != "monthly" else "• MONTHLY •", callback_data=f"lb_period_monthly_{lb_type}")
                ],
                [
                    InlineKeyboardButton("ALLTIME" if period != "alltime" else "• ALLTIME •", callback_data=f"lb_period_alltime_{lb_type}"),
                ],
                [
                    InlineKeyboardButton("POINTS" if lb_type != "points" else "• POINTS •", callback_data=f"lb_type_points_{period}"),
                    InlineKeyboardButton("RENAMES" if lb_type != "renames" else "• RENAMES •", callback_data=f"lb_type_renames_{period}"),
                    InlineKeyboardButton("REFERRALS" if lb_type != "referrals" else "• REFERRALS •", callback_data=f"lb_type_referrals_{period}")
                ]
            ])
            
            try:
                await callback_query.message.edit_text(
                    new_leaderboard,
                    reply_markup=new_keyboard
                )
                await callback_query.answer()
            except Exception as e:
                logger.error(f"Error updating leaderboard: {e}")
                await callback_query.answer("Error updating leaderboard", show_alert=True)
        
        # Auto-delete messages
        async def delete_messages():
            await asyncio.sleep(settings.LEADERBOARD_DELETE_TIMER)
            try:
                await sent_msg.delete()
            except:
                pass
            try:
                await message.delete()
            except:
                pass
        
        asyncio.create_task(delete_messages())
        
    except Exception as e:
        error_msg = await message.reply_text(
            "<b>Error generating leaderboard!</b>\n"
            f"<code>{str(e)}</code>\n\n"
            f"**This message will self-destruct in {settings.LEADERBOARD_DELETE_TIMER} seconds.**"
        )
        await asyncio.sleep(settings.LEADERBOARD_DELETE_TIMER)
        await error_msg.delete()


