import random
import asyncio
import secrets
import uuid
import string
import time
import pytz

import psutil
import logging
from urllib.parse import quote
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
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
from pyrogram.errors import FloodWait, ChatAdminRequired, PeerIdInvalid, QueryIdInvalid , ChannelPrivate ,   UserNotParticipant 
from pyrogram.enums import ChatMemberStatus, ParseMode

from config import settings
from scripts import Txt
from helpers.utils import get_random_photo, get_random_animation, get_shortlink
from plugins.rename import *
from database.data import hyoshcoder

logger = logging.getLogger(__name__)

EMOJI = {
    'error': '❌',
    'success': '✅',
    'warning': '⚠️',
    'points': '✨',
    'premium': '⭐',
    'referral': '👥',
    'rename': '📝',
    'stats': '📊',
    'admin': '🛠️',
    'clock': '⏳',
    'link': '🔗',
    'money': '💰',
    'file': '📁',
    'video': '🎥'
}

async def auto_delete_message(message: Message, delay: int = 30):
    """Automatically delete a message after a specified delay."""
    try:
        await asyncio.sleep(delay)
        await message.delete()
        logger.info(f"Auto-deleted message {message.id} in chat {message.chat.id}")
    except Exception as e:
        logger.error(f"Error auto-deleting message {message.id}: {str(e)}")

async def send_auto_delete_message(
    client: Client,
    chat_id: int,
    text: str,
    delete_after: int = 30,
    **kwargs
) -> Message:
    """Send a message that will auto-delete after specified time."""
    msg = await client.send_message(chat_id, text, **kwargs)
    asyncio.create_task(auto_delete_message(msg, delete_after))
    return msg

async def send_welcome_media(
    client: Client,
    chat_id: int,
    caption: str,
    reply_markup: InlineKeyboardMarkup = None
) -> bool:
    """Send welcome media with proper fallback handling."""
    try:
        # Try animation first
        anim = await get_random_animation()
        if anim:
            await client.send_animation(
                chat_id=chat_id,
                animation=anim,
                caption=caption,
                reply_markup=reply_markup
            )
            return True
        
        # Fallback to photo
        img = await get_random_photo()
        if img:
            await client.send_photo(
                chat_id=chat_id,
                photo=img,
                caption=caption,
                reply_markup=reply_markup
            )
            return True
        
        # Final fallback to text
        await client.send_message(
            chat_id=chat_id,
            text=caption,
            reply_markup=reply_markup
        )
        return True
        
    except Exception as e:
        logger.error(f"Error sending welcome media: {e}")
        # Try text-only fallback
        try:
            await client.send_message(
                chat_id=chat_id,
                text=caption,
                reply_markup=reply_markup
            )
            return True
        except Exception as fallback_error:
            logger.error(f"Fallback error: {fallback_error}")
            return False

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client: Client, message: Message):
    """Handle thumbnail setting."""
    try:
        mkn = await send_auto_delete_message(client, message.chat.id, "Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await mkn.edit("**Thumbnail saved successfully ✅**")
    except Exception as e:
        logger.error(f"Error setting thumbnail: {e}")
        await send_auto_delete_message(
            client,
            message.chat.id,
            f"{EMOJI['error']} Failed to save thumbnail",
            delete_after=15
        )

async def process_referral(client: Client, referrer_id: int, referred_id: int, referral_code: str):
    """Process a referral transaction."""
    try:
        # Get database client from hyoshcoder
        db_client = hyoshcoder._client
        
        async with await db_client.start_session() as session:
            async with session.start_transaction():
                # Record the referral
                await hyoshcoder.global_referrals.insert_one(
                    {
                        "referrer_id": referrer_id,
                        "referred_id": referred_id,
                        "referral_code": referral_code,
                        "timestamp": datetime.now(),
                        "status": "pending"
                    },
                    session=session
                )

                # Update both users' records
                await hyoshcoder.users.update_one(
                    {"_id": referred_id},
                    {"$set": {"referral.referrer_id": referrer_id}},
                    session=session
                )

                # Add points to referrer
                await hyoshcoder.users.update_one(
                    {"_id": referrer_id},
                    {
                        "$inc": {
                            "referral.referred_count": 1,
                            "referral.referral_earnings": settings.REFER_POINT_REWARD,
                            "points.balance": settings.REFER_POINT_REWARD
                        },
                        "$addToSet": {"referral.referred_users": referred_id}
                    },
                    session=session
                )

                # Add points to referred user
                await hyoshcoder.users.update_one(
                    {"_id": referred_id},
                    {"$inc": {"points.balance": settings.REFER_POINT_REWARD}},
                    session=session
                )

                # Mark referral as completed
                await hyoshcoder.global_referrals.update_one(
                    {"referrer_id": referrer_id, "referred_id": referred_id},
                    {"$set": {"status": "completed"}},
                    session=session
                )

        return True
    except Exception as e:
        logger.error(f"Error processing referral: {e}")
        return False
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
			
@Client.on_message(filters.command("mystats") & filters.private)
async def mystats_command(client: Client, message: Message):
    """Handle /mystats command to show user statistics."""
    try:
        user_id = message.from_user.id
        img = await get_random_photo()
        
        # Get user stats with proper date handling
        stats = await hyoshcoder.get_user_file_stats(user_id)
        points = await hyoshcoder.get_points(user_id)
        premium_status = await hyoshcoder.check_premium_status(user_id)
        user_data = await hyoshcoder.read_user(user_id)
        referral_stats = user_data.get('referral', {})
        
        # Ensure we have default values if stats are None
        if stats is None:
            stats = {
                'total_renamed': 0,
                'today': 0,
                'this_week': 0,
                'this_month': 0
            }
        else:
            # Convert any integer timestamps to proper datetime objects
            if isinstance(stats.get('last_updated'), int):
                stats['last_updated'] = datetime.fromtimestamp(stats['last_updated'])
        
        text = (
            f"📊 <b>Your Statistics</b>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>💰 Points</b>\n"
            f"┣ <i>Balance:</i> <code>{points}</code>\n"
            f"┗ <i>Referral Earnings:</i> <code>{referral_stats.get('referral_earnings', 0)}</code>\n\n"
            f"<b>🌟 Premium</b>\n"
            f"┗ <i>Status:</i> {'<code>Active</code> ' + EMOJI['success'] if premium_status.get('is_premium', False) else '<code>Inactive</code> ' + EMOJI['error']}\n\n"
            f"<b>👥 Referrals</b>\n"
            f"┗ <i>Count:</i> <code>{referral_stats.get('referred_count', 0)}</code>\n\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>📁 Files Renamed</b>\n"
            f"┣ <i>Total:</i> <code>{stats.get('total_renamed', 0)}</code>\n"
            f"┣ <i>Today:</i> <code>{stats.get('today', 0)}</code>\n"
            f"┣ <i>This Week:</i> <code>{stats.get('this_week', 0)}</code>\n"
            f"┗ <i>This Month:</i> <code>{stats.get('this_month', 0)}</code>\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        
        if img:
            msg = await message.reply_photo(
                photo=img,
                caption=text
            )
        else:
            msg = await message.reply_text(text)
            
        asyncio.create_task(auto_delete_message(msg, 60))
        asyncio.create_task(auto_delete_message(message, 60))

    except Exception as e:
        logger.error(f"Error in mystats command: {e}")
        msg = await message.reply_text("⚠️ Error loading statistics. Please try again later.")
        asyncio.create_task(auto_delete_message(msg, 30))

@Client.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    """Handle /status command to show bot statistics."""
    try:
        # Get system information
        process = psutil.Process()
        mem_info = process.memory_info()
        cpu_usage = psutil.cpu_percent()
        
        # Get bot uptime
        uptime_seconds = time.time() - process.create_time()
        uptime = str(timedelta(seconds=uptime_seconds)).split(".")[0]
        
        # Get database stats
        total_users = await hyoshcoder.total_users_count()
        total_files = await hyoshcoder.total_renamed_files()
        
        text = (
            f"🤖 <b>Bot Status</b>\n\n"
            f"⏱ <b>Uptime:</b> {uptime}\n"
            f"💾 <b>Memory Usage:</b> {mem_info.rss/1024/1024:.2f} MB\n"
            f"⚡ <b>CPU Usage:</b> {cpu_usage}%\n\n"
            f"👥 <b>Total Users:</b> {total_users}\n"
            f"📝 <b>Files Renamed:</b> {total_files}\n\n"
            f"📅 <b>Last Update:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await message.reply_text(text)
        
    except Exception as e:
        logger.error(f"Error in status command: {e}")
        await message.reply_text("⚠️ Could not retrieve status information. Please try again later.")

@Client.on_message(filters.command(["mystats", "status"]) & filters.private)
async def additional_commands(client: Client, message: Message):
    """Handle additional commands."""
    try:
        cmd = message.command[0].lower()
        
        if cmd == "mystats":
            await mystats_command(client, message)
        elif cmd == "status":
            await status_command(client, message)
            
        asyncio.create_task(auto_delete_message(message, settings.AUTO_DELETE_TIME))
        
    except Exception as e:
        logger.error(f"Error in additional commands: {e}")
        msg = await message.reply_text("⚠️ An error occurred. Please try again.")
        asyncio.create_task(auto_delete_message(msg, 30))
@Client.on_message(filters.command("genpoints") & filters.private)
async def generate_point_link(client: Client, message: Message):
    """Generate a points earning link for users."""
    try:
        user_id = message.from_user.id
        db = hyoshcoder

        # Validate required settings
        if not all([settings.BOT_USERNAME, settings.TOKEN_ID_LENGTH, settings.SHORTENER_POINT_REWARD]):
            logger.error("Missing required settings for genpoints")
            return await send_auto_delete_message(
                client,
                message.chat.id,
                "⚠️ Configuration error. Please contact admin.",
                delete_after=30
            )

        # Generate point ID and deep link
        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"

        # Get random shortener
        shortener = settings.get_random_shortener()
        if not shortener:
            logger.error("No shortener configured")
            return await send_auto_delete_message(
                client,
                message.chat.id,
                "⚠️ No URL shortener configured. Please contact admin.",
                delete_after=30
            )

        # Shorten the link with error handling
        short_url = deep_link  # Default to deep link if shortening fails
        try:
            shortened = await get_shortlink(
                url=shortener["domain"],
                api=shortener["api"],
                link=deep_link
            )
            if isinstance(shortened, str) and shortened.startswith(('http://', 'https://')):
                short_url = shortened
            else:
                logger.warning(f"Invalid short URL format: {shortened}")
        except Exception as e:
            logger.error(f"Error shortening URL: {e}")

        # Save to database (without expiration)
        try:
            await db.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
            logger.info(f"Point link saved for user {user_id}")
        except Exception as db_error:
            logger.error(f"Database error: {db_error}")
            return await send_auto_delete_message(
                client,
                message.chat.id,
                "❌ Failed to save point link. Please try again.",
                delete_after=30
            )

        # Send the points link (removed expiration mention)
        bot_reply = await message.reply(
            f"**🎁 Get {settings.SHORTENER_POINT_REWARD} Points**\n\n"
            f"**🔗 Click below link and complete verification:**\n{short_url}\n\n"
            "**🧬 Verify more links to get more points**",
            disable_web_page_preview=True
        )

        # Auto-delete both messages after 30 seconds
        asyncio.create_task(auto_delete_message(message, 30))
        asyncio.create_task(auto_delete_message(bot_reply, 30))

    except Exception as e:
        logger.error(f"Unexpected error in generate_point_link: {str(e)}", exc_info=True)
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ An unexpected error occurred. Please try again later.",
            delete_after=30
        )

@Client.on_message(filters.command("refer") & filters.private)
async def refer(client: Client, message: Message):
    """Generate referral link with quick share button."""
    try:
        user_id = message.from_user.id
        user = await hyoshcoder.get_user(user_id)
        
        if not user:
            await hyoshcoder.add_user(user_id)
            user = await hyoshcoder.get_user(user_id)
        
        # Generate or get referral code
        referral_code = user.get("referral", {}).get("referral_code")
        if not referral_code:
            referral_code = secrets.token_hex(4).upper()
            await hyoshcoder.users.update_one(
                {"_id": user_id},
                {"$set": {"referral.referral_code": referral_code}},
                upsert=True
            )

        # Get referral stats
        referred_count = user.get("referral", {}).get("referred_count", 0)
        referral_earnings = user.get("referral", {}).get("referral_earnings", 0)
        
        # Create referral link
        refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
        
        # Create share button
        share_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Quick Share", url=f"tg://msg_url?url={quote(refer_link)}&text=Join%20using%20my%20referral%20link%20to%20get%20{settings.REFER_POINT_REWARD}%20free%20points!")]
        ])
        
        # Send message
        msg = await message.reply_text(
            f"🌟 <b>Your Referral Program</b>\n\n"
            f"🔗 <b>Your Referral Link:</b>\n<code>{refer_link}</code>\n\n"
            f"📊 <b>Stats:</b>\n"
            f"┣ Total Referrals: <code>{referred_count}</code>\n"
            f"┣ Earnings: <code>{referral_earnings}</code> points\n"
            f"┗ Points per Referral: <code>{settings.REFER_POINT_REWARD}</code>\n\n"
            f"💡 <b>How it works:</b>\n"
            f"1. Share your link with friends\n"
            f"2. When they join using your link\n"
            f"3. You both get <code>{settings.REFER_POINT_REWARD}</code> points!",
            reply_markup=share_button,
            disable_web_page_preview=True
        )
        
        asyncio.create_task(auto_delete_message(msg, 60))

    except Exception as e:
        logger.error(f"Error in refer command: {e}")
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ Failed to generate referral link. Please try again.",
            delete_after=30
        )

@Client.on_message(filters.command("referralboard") & filters.private)
async def referral_leaderboard(client: Client, message: Message):
    """Show beautifully formatted top referrers leaderboard."""
    try:
        # Get top 10 referrers with proper names
        top_referrers = await hyoshcoder.users.aggregate([
            {"$match": {"referral.referred_count": {"$gt": 0}}},
            {"$sort": {"referral.referred_count": -1}},
            {"$limit": 10},
            {"$project": {
                "username": 1,
                "first_name": 1,
                "referred_count": "$referral.referred_count",
                "earnings": "$referral.referral_earnings"
            }}
        ]).to_list(length=10)

        if not top_referrers:
            return await message.reply("📭 No referral data available yet. Be the first!")

        # Format leaderboard with columns
        leaderboard_header = "🏆 <b>TOP REFERRERS LEADERBOARD</b>\n\n"
        leaderboard_header += "<b>Rank  Name               Referrals  Points</b>\n"
        leaderboard_header += "───────────────────────────────────\n"
        
        leaderboard_rows = []
        medal_emojis = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]
        
        for idx, user in enumerate(top_referrers):
            # Get the best available display name
            display_name = user.get("username", "")
            if not display_name:
                display_name = user.get("first_name", "Anonymous")[:15]
            else:
                display_name = f"@{display_name}"[:15]
            
            # Format the row with fixed-width columns
            rank = medal_emojis[idx] if idx < 3 else f"{idx+1}."
            referrals = str(user.get("referred_count", 0)).rjust(3)
            points = str(user.get("earnings", 0)).rjust(5)
            
            leaderboard_rows.append(
                f"{rank.ljust(4)} {display_name.ljust(17)} {referrals}      {points}\n"
            )

        leaderboard_footer = "\n💎 Each referral earns you +{settings.REFER_POINT_REWARD} points!"

        # Combine all parts
        text = leaderboard_header + "".join(leaderboard_rows) + leaderboard_footer

        # Create working inline button
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Get Your Referral Link", callback_data="get_referral_link")]
        ])

        msg = await message.reply_text(
            text,
            reply_markup=buttons,
            disable_web_page_preview=True,
            parse_mode=ParseMode.HTML
        )
        
        asyncio.create_task(auto_delete_message(msg, 60))

    except Exception as e:
        logger.error(f"Error in referral leaderboard: {e}")
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ Failed to load leaderboard. Please try again.",
            delete_after=30
        )

@Client.on_callback_query(filters.regex("^get_referral_link$"))
async def get_referral_link_callback(client: Client, callback_query: CallbackQuery):
    """Handle referral link button from leaderboard."""
    try:
        # Delete the leaderboard message
        await callback_query.message.delete()
        
        # Create a new message with the referral link
        user_id = callback_query.from_user.id
        user = await hyoshcoder.get_user(user_id)
        
        if not user:
            await hyoshcoder.add_user(user_id)
            user = await hyoshcoder.get_user(user_id)
        
        # Generate or get referral code
        referral_code = user.get("referral", {}).get("referral_code")
        if not referral_code:
            referral_code = secrets.token_hex(4).upper()
            await hyoshcoder.users.update_one(
                {"_id": user_id},
                {"$set": {"referral.referral_code": referral_code}},
                upsert=True
            )

        refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
        
        # Create share button
        share_button = InlineKeyboardMarkup([
            [InlineKeyboardButton("📤 Share Link", url=f"tg://msg_url?url={quote(refer_link)}&text=Join%20using%20my%20referral%20link%20to%20get%20{settings.REFER_POINT_REWARD}%20free%20points!")]
        ])
        
        await callback_query.message.reply_text(
            f"🔗 <b>Your Personal Referral Link:</b>\n"
            f"<code>{refer_link}</code>\n\n"
            f"📊 <b>Current Reward:</b> {settings.REFER_POINT_REWARD} points per referral",
            reply_markup=share_button,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Error in referral callback: {e}")
        await callback_query.answer(
            "Failed to generate referral link",
            show_alert=True
        )
@Client.on_message(filters.command("freepoints") & filters.private)
async def freepoints(client: Client, message: Message):
    """Handle free points generation."""
    try:
        user_id = message.from_user.id
        user = await hyoshcoder.users.find_one({"_id": user_id})

        # Generate or get referral code
        referral_code = user.get("referral_code") if user else None
        if not referral_code:
            referral_code = secrets.token_hex(4)
            await hyoshcoder.users.update_one(
                {"_id": user_id},
                {"$set": {"referral_code": referral_code}},
                upsert=True
            )

        refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"

        # Generate point ID and deep link
        point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
        deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"

        # Get random shortener
        shortener = settings.get_random_shortener()
        if not shortener:
            return await send_auto_delete_message(
                client,
                message.chat.id,
                "⚠️ No URL shortener configured. Please contact admin.",
                delete_after=30
            )

        # Shorten the link with proper error handling
        short_url = deep_link  # Default to deep link
        try:
            shortened = await get_shortlink(
                url=shortener["domain"],
                api=shortener["api"],
                link=deep_link
            )
            if isinstance(shortened, str) and shortened.startswith(("http://", "https://")):
                short_url = shortened
            else:
                logger.warning(f"Invalid short URL format: {shortened}")
        except Exception as e:
            logger.error(f"Error shortening URL: {e}")

        # Save point link (without expiration)
        try:
            await hyoshcoder.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
        except Exception as db_error:
            logger.error(f"Database error saving point link: {db_error}")
            return await send_auto_delete_message(
                client,
                message.chat.id,
                "❌ Failed to generate points link. Please try again.",
                delete_after=30
            )

        # Prepare response
        buttons = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton("🛡️ ᴠᴇʀɪꜰʏ", url=short_url)
  
                ]
            ]
        )
        
        caption = (
            "**🎁 Free Points Menu**\n\n"
            "Earn points by:\n"
            f"1. **Referring users** – `/refer`\n"
            f"   ➤ {settings.REFER_POINT_REWARD} points per referral\n"
            f"2. **Verify To Get Points** –\n"
            f"   ➤ {settings.SHORTENER_POINT_REWARD} points per view\n\n"
            f"🎯 Your points link:\n{short_url}\n\n"
            "⏱ Points will be added automatically!\n"
            f"⌛ This message will be deleted in {settings.AUTO_DELETE_TIME} seconds."
        )

        # Send response with auto-delete
        try:
            img = await get_random_photo()
            if img:
                msg = await message.reply_photo(
                    photo=img,
                    caption=caption,
                    reply_markup=buttons
                )
            else:
                msg = await message.reply_text(
                    text=caption,
                    reply_markup=buttons,
                    disable_web_page_preview=True
                )
        except Exception as e:
            logger.error(f"Error sending freepoints message: {e}")
            msg = await message.reply_text(
                text=caption,
                reply_markup=buttons,
                disable_web_page_preview=True
            )

        # Auto-delete
        asyncio.create_task(auto_delete_message(msg, settings.AUTO_DELETE_TIME))
        asyncio.create_task(auto_delete_message(message, settings.AUTO_DELETE_TIME))

    except Exception as e:
        logger.error(f"Error in /freepoints: {e}", exc_info=True)
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ Failed to generate free points. Try again.",
            delete_after=30
        )

@Client.on_message(filters.command(["view_dump", "viewdump"]) & filters.private)
async def view_dump_channel(client: Client, message: Message):
    """View current dump channel setting."""
    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        
        if channel_id:
            msg = await message.reply_text(
                f"**Current Dump Channel:** `{channel_id}`",
                quote=True
            )
        else:
            msg = await message.reply_text(
                "No dump channel is currently set.",
                quote=True
            )
        
        asyncio.create_task(auto_delete_message(msg, 30))
        asyncio.create_task(auto_delete_message(message, 30))

    except Exception as e:
        logger.error(f"Error viewing dump channel: {e}")
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ Failed to retrieve dump channel info.",
            delete_after=30
        )

@Client.on_message(filters.command(["del_dump", "deldump"]) & filters.private)
async def delete_dump_channel(client: Client, message: Message):
    """Remove dump channel setting."""
    if not message.from_user:
        return  # Ignore if not from a user

    try:
        user_id = message.from_user.id
        channel_id = await hyoshcoder.get_user_channel(user_id)
        
        if not channel_id:
            msg = await message.reply_text(
                "ℹ️ No dump channel is currently set.",
                quote=True
            )
            asyncio.create_task(auto_delete_message(msg, 30))
            asyncio.create_task(auto_delete_message(message, 30))
            return

        # Clear the channel setting
        success = await hyoshcoder.set_user_channel(user_id, None)
        
        if not success:
            logger.warning(f"Failed to clear dump channel for user {user_id}")
            raise ValueError("Database operation failed")

        msg = await message.reply_text(
            f"✅ Successfully removed dump channel `{channel_id}`.",
            quote=True
        )
        
        # Log the successful removal
        logger.info(f"User {user_id} removed dump channel {channel_id}")

    except ValueError as e:
        msg = await message.reply_text(
            "❌ Failed to remove dump channel due to a system error. Please try again.",
            quote=True
        )
    except Exception as e:
        logger.error(f"Error deleting dump channel for user {user_id}: {e}", exc_info=True)
        msg = await message.reply_text(
            "❌ An unexpected error occurred. Please try again later.",
            quote=True
        )
    finally:
        # Ensure messages are scheduled for deletion
        if 'msg' in locals():
            asyncio.create_task(auto_delete_message(msg, 30))
        asyncio.create_task(auto_delete_message(message, 30))

async def handle_set_dump(client: Client, message: Message, args: List[str]):
    """Handle setting dump channel with proper validation."""
    if not message.from_user:
        return  # Ignore if not from a user
    
    if len(args) == 0:
        return await send_auto_delete_message(
            client,
            message.chat.id,
            "❗️ Please provide the dump channel ID after the command.\n"
            "Example: `/set_dump -1001234567890`",
            delete_after=30
        )

    channel_id = args[0].strip()
    user_id = message.from_user.id

    try:
        # Validate channel ID format
        if not channel_id.startswith('-100') or not channel_id[4:].isdigit():
            raise ValueError("Invalid channel ID format. Must be like -1001234567890")

        # Convert to integer for validation
        channel_id_int = int(channel_id)
        
        # Check if bot has admin rights in the channel
        try:
            member = await client.get_chat_member(channel_id_int, client.me.id)
            if not member or not getattr(member, 'privileges', None) or not member.privileges.can_post_messages:
                raise ValueError("I need admin rights with post permissions in that channel")
        except PeerIdInvalid:
            raise ValueError("Channel not found or I'm not a member")
        except ChatAdminRequired:
            raise ValueError("I don't have admin rights in that channel")
        except ChannelPrivate:
            raise ValueError("Channel is private or I'm not a member")

        # Save to database
        success = await hyoshcoder.set_user_channel(user_id, channel_id)
        if not success:
            raise ValueError("Failed to save channel to database")

        msg = await message.reply_text(
            f"✅ Channel `{channel_id}` has been successfully set as your dump channel.",
            quote=True
        )
        
        asyncio.create_task(auto_delete_message(msg, 30))
        asyncio.create_task(auto_delete_message(message, 30))

    except ValueError as e:
        await send_auto_delete_message(
            client,
            message.chat.id,
            f"❌ Error: {str(e)}\n\n"
            "Ensure the channel exists, and I'm an admin with posting rights.",
            delete_after=30
        )
    except Exception as e:
        logger.error(f"Error setting dump channel: {e}", exc_info=True)
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ An unexpected error occurred while setting dump channel. Please try again.",
            delete_after=30
@Client.on_message(filters.command("setmedia") & filters.private)
async def handle_setmedia(client: Client, message: Message):
    """Handle media preference setting."""
    try:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("• Document •", callback_data="setmedia_document")],
            [InlineKeyboardButton("• ᴠɪᴅᴇᴏ •", callback_data="setmedia_video")]
        ])
        
        msg = await message.reply_text(
            "**Please select the type of media you want to set:**",
            reply_markup=keyboard
        )
        
        asyncio.create_task(auto_delete_message(msg, 60))
        asyncio.create_task(auto_delete_message(message, 60))

    except Exception as e:
        logger.error(f"Error in setmedia command: {e}")
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ Failed to set media preference. Please try again.",
            delete_after=30
        )

@Client.on_callback_query(filters.regex(r"^setmedia_(document|video)$"))
async def set_media_preference_handler(client: Client, callback_query: CallbackQuery):
    """Handle media preference selection from callback."""
    try:
        media_type = callback_query.data.split("_")[1]
        user_id = callback_query.from_user.id

        success = await hyoshcoder.set_media_preference(user_id, media_type)
        if success:
            await callback_query.answer(
                f"Media type set to {media_type.capitalize()} ✅",
                show_alert=True
            )
            
            # Edit original message to confirm
            await callback_query.message.edit_text(
                f"✅ Your media preference has been set to: **{media_type.capitalize()}**"
            )
            
            # Auto-delete after confirmation
            asyncio.create_task(auto_delete_message(callback_query.message, 30))
        else:
            await callback_query.answer(
                "Failed to update media preference ❌",
                show_alert=True
            )

    except Exception as e:
        logger.error(f"Error setting media preference: {e}")
        await callback_query.answer(
            "An error occurred. Please try again.",
            show_alert=True
        )

async def handle_start_command(client: Client, message: Message, args: List[str]):
    """Handle start command with referral and point redemption."""
    user = message.from_user
    user_id = user.id
    
    # Add user to database if not exists
    if not await hyoshcoder.get_user(user_id):
        await hyoshcoder.add_user(user_id)

    # Check for referral link
    if len(args) > 0 and args[0].startswith("ref_"):
        referral_code = args[0][4:]
        
        # Get referrer's user_id from code
        referrer = await hyoshcoder.users.find_one({"referral.referral_code": referral_code})
        
        if referrer and referrer["_id"] != user_id:
            # Check if user already has a referrer
            user_data = await hyoshcoder.get_user(user_id)
            if user_data.get("referral", {}).get("referrer_id"):
                await message.reply_text(
                    "ℹ️ You were already referred by another user. "
                    "Referral codes can only be used once per account."
                )
                return
            
            # Process the referral
            success = await process_referral(client, referrer["_id"], user_id, referral_code)
            
            if success:
                # Notify both users
                try:
                    await client.send_message(
                        referrer["_id"],
                        f"🎉 New referral! You received {settings.REFER_POINT_REWARD} "
                        f"points for {user.mention} joining with your link."
                    )
                except Exception as e:
                    logger.error(f"Failed to notify referrer: {e}")
                
                await message.reply_text(
                    f"🎉 You received {settings.REFER_POINT_REWARD} points "
                    f"for joining via referral!"
                )
            else:
                await message.reply_text(
                    "❌ Failed to process referral. Please try again."
                )
        else:
            await message.reply_text("❌ Invalid referral code")
    
    # Handle point redemption link
    elif len(args) > 0:
        await handle_point_redemption(client, message, args[0])
        return


    # Send welcome message
    m = await message.reply_sticker("CAACAgIAAxkBAAI0WGg7NBOpULx2heYfHhNpqb9Z1ikvAAL6FQACgb8QSU-cnfCjPKF6HgQ")
    await asyncio.sleep(3)
    await m.delete()

    # Prepare buttons
    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("• ᴍʏ ᴄᴏᴍᴍᴀɴᴅꜱ •", callback_data='help')],  # Single-row button
        [
            InlineKeyboardButton("• ꜱᴛᴀᴛꜱ •", callback_data='mystats'),
            InlineKeyboardButton("• ᴇᴀʀɴ ᴘᴏɪɴᴛꜱ •", callback_data='freepoints')
        ],
        [
            InlineKeyboardButton("• Updates •", url='https://t.me/TFIBOTS'),
            InlineKeyboardButton("• Support •", url='https://t.me/TFIBOTS_SUPPORT')
        ]
    ])

    # Send welcome message with media
    try:
        # Try to send with media first
        media_sent = await send_welcome_media(
            client=client,
            chat_id=message.chat.id,
            caption=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )
        
        if not media_sent:
            # Fallback to text if media fails
            await message.reply_text(
                text=Txt.START_TXT.format(user.mention),
                reply_markup=buttons
            )
    except Exception as e:
        logger.error(f"Error in welcome message: {e}")
        # Final fallback if everything fails
        await message.reply_text(
            text=Txt.START_TXT.format(user.mention),
            reply_markup=buttons
        )


async def handle_autorename(client: Client, message: Message, args: List[str]):
    """Handle the /autorename command to set rename template."""
    if not args:
        msg = await message.reply_text(
            "/autorename ᴏɴᴇ ᴘᴜɴᴄʜ ᴍᴀɴ [Sseason - EPepisode - [Quality] [Dual]\n\n"
            "⟩ ᴄᴏᴍᴍᴀɴᴅ:\n"
            "/autorename – ᴜꜱᴇ ᴘʟᴀᴄᴇʜᴏʟᴅᴇʀꜱ ᴛᴏ ᴍᴀɴᴀɢᴇ ꜰɪʟᴇɴᴀᴍᴇꜱ."
        )

        asyncio.create_task(auto_delete_message(msg, 60))
        asyncio.create_task(auto_delete_message(message, 60))
        return

    format_template = ' '.join(args)
    await hyoshcoder.set_format_template(message.from_user.id, format_template)
    
    msg = await message.reply_text(
        f"✅ <b>Auto-rename template set!</b>\n\n"
        f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
        "Now send me files to rename automatically!"
    )
    asyncio.create_task(auto_delete_message(msg, 60))
    asyncio.create_task(auto_delete_message(message, 60))

async def handle_set_caption(client: Client, message: Message, args: List[str]):
    """Handle /set_caption command to set custom caption."""
    if not args:
        msg = await message.reply_text(
            "**Provide the caption\n\nExample : `/set_caption 📕Name ➠ : {filename} \n\n"
            "🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**"
        )
        asyncio.create_task(auto_delete_message(msg, 60))
        asyncio.create_task(auto_delete_message(message, 60))
        return
    
    new_caption = message.text.split(" ", 1)[1]
    await hyoshcoder.set_caption(message.from_user.id, new_caption)
    
    img = await get_random_photo()
    caption = "**Your caption has been saved successfully ✅**"
    
    if img:
        msg = await message.reply_photo(photo=img, caption=caption)
    else:
        msg = await message.reply_text(text=caption)
    
    asyncio.create_task(auto_delete_message(msg, 60))
    asyncio.create_task(auto_delete_message(message, 60))

async def handle_del_caption(client: Client, message: Message):
    """Handle /del_caption command to remove caption."""
    await hyoshcoder.set_caption(message.from_user.id, None)
    msg = await message.reply_text("✅ Caption removed successfully!")
    asyncio.create_task(auto_delete_message(msg, 30))
    asyncio.create_task(auto_delete_message(message, 30))

async def handle_view_caption(client: Client, message: Message):
    """Handle /view_caption command to show current caption."""
    current_caption = await hyoshcoder.get_caption(message.from_user.id) or "No caption set"
    msg = await message.reply_text(f"📝 <b>Current Caption:</b>\n{current_caption}")
    asyncio.create_task(auto_delete_message(msg, 60))
    asyncio.create_task(auto_delete_message(message, 60))

async def handle_view_thumb(client: Client, message: Message):
    """Handle /viewthumb command to show current thumbnail."""
    thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
    if thumb:
        msg = await message.reply_photo(thumb, caption="Your current thumbnail")
    else:
        msg = await message.reply_text("No thumbnail set")
    asyncio.create_task(auto_delete_message(msg, 60))
    asyncio.create_task(auto_delete_message(message, 60))

async def handle_del_thumb(client: Client, message: Message):
    """Handle /delthumb command to remove thumbnail."""
    await hyoshcoder.set_thumbnail(message.from_user.id, None)
    msg = await message.reply_text("✅ Thumbnail removed successfully!")
    asyncio.create_task(auto_delete_message(msg, 30))
    asyncio.create_task(auto_delete_message(message, 30))

async def handle_premium(client: Client, message: Message):
    """Handle premium-related commands."""
    msg = await message.reply_text(
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
    asyncio.create_task(auto_delete_message(msg, 60))
    asyncio.create_task(auto_delete_message(message, 60))

async def handle_help(client: Client, message: Message):
    """Handle /help command to show help menu."""
    user_id = message.from_user.id
    img = await get_random_photo()
    sequential_status = await hyoshcoder.get_sequential_mode(user_id)
    src_info = await hyoshcoder.get_src_info(user_id)

    btn_seq_text = "ˢᵉᑫ✅" if sequential_status else "ˢᵉᑫ❌"
    src_txt = "File name" if src_info == "file_name" else "File caption"

    buttons = InlineKeyboardMarkup([
    [
        InlineKeyboardButton("ᴀᴜᴛᴏ", callback_data='file_names'),
        InlineKeyboardButton("ᴛʜᴜᴍʙ", callback_data='thumbnail'),
        InlineKeyboardButton("ᴄᴀᴘᴛɪᴏɴ", callback_data='caption')
    ],
    [
        InlineKeyboardButton("ᴍᴇᴛᴀ", callback_data='meta'),
        InlineKeyboardButton("ᴍᴇᴅɪᴀ", callback_data='setmedia'),
        InlineKeyboardButton("ᴅᴜᴍᴘ", callback_data='setdump')
    ],
    [
        InlineKeyboardButton("sᴇǫ", callback_data='sequential'),
        InlineKeyboardButton("ᴘʀᴇᴍ", callback_data='premiumx'),
        InlineKeyboardButton(f"sʀᴄ: {src_txt}", callback_data='toggle_src')
    ],
    [
        InlineKeyboardButton("◁", callback_data="back"),
        InlineKeyboardButton("• ʜᴏᴍᴇ •", callback_data="home"),
        InlineKeyboardButton("▷", callback_data="next")
    ]
])


    if img:
        msg = await message.reply_photo(
            photo=img,
            caption=Txt.HELP_TXT.format(client.mention),
            reply_markup=buttons
        )
    else:
        msg = await message.reply_text(
            text=Txt.HELP_TXT.format(client.mention),
            reply_markup=buttons
        )
    asyncio.create_task(auto_delete_message(msg, 120))
    asyncio.create_task(auto_delete_message(message, 120))

async def handle_set_dump(client: Client, message: Message, args: List[str]):
    """Handle setting dump channel with comprehensive validation"""
    if not message.from_user:
        return await message.delete()
    
    if len(args) == 0:
        return await send_auto_delete_message(
            client,
            message.chat.id,
            "❗️ Please provide the dump channel ID after the command.\n"
            "Example: `/set_dump -1001234567890`\n\n"
            "To get your channel ID:\n"
            "1. Add me to your channel as admin\n"
            "2. Forward a message from your channel to me\n"
            "3. I'll show you the channel ID",
            delete_after=45
        )

    channel_id = args[0].strip()
    user_id = message.from_user.id

    try:
        # Validate channel ID format
        if not re.match(r'^-100\d+$', channel_id):
            raise ValueError(
                "Invalid channel ID format.\n"
                "Must start with -100 followed by numbers (e.g., -1001234567890)"
            )

        # Convert to integer for validation
        channel_id_int = int(channel_id)
        
        # Check if bot has admin rights in the channel
        try:
            member = await client.get_chat_member(channel_id_int, client.me.id)
            if not member or not member.privileges:
                raise ValueError("I don't have admin rights in that channel")
            
            required_perms = [
                "can_post_messages",
                "can_send_media_messages",
                "can_send_other_messages"
            ]
            
            missing_perms = [
                perm for perm in required_perms
                if not getattr(member.privileges, perm, False)
            ]
            
            if missing_perms:
                raise ValueError(
                    "I'm missing these permissions:\n" +
                    "\n".join(f"• {perm.replace('_', ' ')}" for perm in missing_perms)
		)
        except (PeerIdInvalid, ChannelPrivate):
            raise ValueError(
                "Channel not found or I'm not a member.\n"
                "Please add me to the channel as admin first."
            )

        # Save to database
        success = await hyoshcoder.set_user_channel(user_id, channel_id)
        if not success:
            raise ValueError("Failed to save channel to database. Please try again.")

        # Get channel info for confirmation
        chat = await client.get_chat(channel_id_int)
        
        msg = await message.reply_text(
            f"✅ <b>Dump channel successfully set!</b>\n\n"
            f"<b>Channel:</b> {chat.title}\n"
            f"<b>ID:</b> <code>{channel_id}</code>\n\n"
            "All your renamed files will now be sent here automatically.",
            parse_mode=ParseMode.HTML
        )
        
        asyncio.create_task(auto_delete_message(msg, 45))
        asyncio.create_task(auto_delete_message(message, 45))

    except ValueError as e:
        await send_auto_delete_message(
            client,
            message.chat.id,
            f"❌ <b>Error setting dump channel:</b>\n{str(e)}",
            parse_mode=ParseMode.HTML,
            delete_after=45
        )
    except Exception as e:
        logger.error(f"Error setting dump channel: {e}", exc_info=True)
        await send_auto_delete_message(
            client,
            message.chat.id,
            "❌ An unexpected error occurred while setting dump channel. Please try again.",
            delete_after=30
        )
async def verify_dump_channel(client: Client, channel_id: str) -> Tuple[bool, str]:
    """Verify dump channel exists and has proper permissions"""
    try:
        channel_id_int = int(channel_id)
        chat = await client.get_chat(channel_id_int)
        
        # Check if it's a channel or supergroup
        if chat.type not in ("channel", "supergroup"):
            return False, f"Invalid chat type: {chat.type}"
            
        # Check bot permissions
        member = await client.get_chat_member(channel_id_int, client.me.id)
        if not member or not member.privileges:
            return False, "Bot has no privileges"
            
        # Check required permissions
        required_perms = {
            "can_post_messages": "Post messages",
            "can_send_media_messages": "Send media",
            "can_send_other_messages": "Send other content"
        }
        
        missing_perms = [
            desc for perm, desc in required_perms.items()
            if not getattr(member.privileges, perm, False)
        ]
        
        if missing_perms:
            return False, f"Missing permissions: {', '.join(missing_perms)}"
            
        return True, ""
        
    except PeerIdInvalid:
        return False, "Channel not found"
    except ChannelPrivate:
        return False, "Channel is private"
    except Exception as e:
        logger.error(f"Error verifying channel: {e}")
        return False, f"Verification error: {str(e)[:100]}"
@Client.on_message(filters.command(["start", "help", "autorename", "set_caption", "del_caption", 
                                  "view_caption", "viewthumb", "delthumb", "set_dump",
                                  "view_dump", "del_dump", "freepoints", "genpoints",
                                  "refer", "premium", "donate"]) & filters.private)
async def command_dispatcher(client: Client, message: Message):
    """Dispatch commands to appropriate handlers."""
    try:
        cmd = message.command[0].lower()
        args = message.command[1:]

        # Special case for start command (no auto-delete)
        if cmd == 'start':
            await handle_start_command(client, message, args)
            return

        # Dispatch other commands
        if cmd == "help":
            await handle_help(client, message)
        elif cmd == "autorename":
            await handle_autorename(client, message, args)
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
        elif cmd == "set_dump":
            await handle_set_dump(client, message, args)
        elif cmd in ["view_dump", "viewdump"]:
            await view_dump_channel(client, message)
        elif cmd in ["del_dump", "deldump"]:
            await delete_dump_channel(client, message)
        elif cmd == "freepoints":
            await freepoints(client, message)
        elif cmd == "genpoints":
            await generate_point_link(client, message)
        elif cmd == "refer":
            await refer(client, message)
        elif cmd in ["premium", "donate"]:
            await handle_premium(client, message)

        # Auto-delete the command message
        asyncio.create_task(auto_delete_message(message, settings.AUTO_DELETE_TIME))

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Command dispatcher error: {e}")
        msg = await message.reply_text("⚠️ An error occurred. Please try again.")
        asyncio.create_task(auto_delete_message(msg, 30))
        asyncio.create_task(auto_delete_message(message, 30))
	    
@Client.on_message(filters.command("setdump"))
async def set_dump_via_forward(client: Client, message: Message):
    """Set dump channel by forwarding a channel message"""
    try:
        user_id = message.from_user.id
        
        if not message.reply_to_message or not message.reply_to_message.forward_from_chat:
            return await message.reply(
                "🔧 <b>How to set dump channel:</b>\n"
                "1. Add me as ADMIN to your channel (with ALL permissions)\n"
                "2. Forward any message FROM your channel TO this chat\n"
                "3. Reply to that forwarded message with <code>/set_dump_alt</code>",
                parse_mode=ParseMode.HTML
            )
        
        channel = message.reply_to_message.forward_from_chat
        channel_id = channel.id
        
        # Verify channel type
        chat_type = str(channel.type).lower()
        if 'channel' not in chat_type and 'supergroup' not in chat_type:
            return await message.reply("❌ Only channels and supergroups can be dump channels")
        
        # Verify bot permissions
        try:
            member = await client.get_chat_member(channel_id, client.me.id)
            if not member or not member.privileges:
                return await message.reply("❌ I'm not an admin in that channel")
            
            required_perms = [
                'can_post_messages',
                'can_send_media_messages',
                'can_send_other_messages'
            ]
            
            missing_perms = [
                perm for perm in required_perms
                if not getattr(member.privileges, perm, False)
            ]
            
            if missing_perms:
                return await message.reply(
                    "❌ Missing permissions:\n" + 
                    "\n".join(f"• {perm.replace('_', ' ')}" for perm in missing_perms)
                )
            
            # Save to database
            success = await hyoshcoder.set_user_channel(user_id, str(channel_id))
            if not success:
                return await message.reply("❌ Failed to save channel. Please try again.")
            
            await message.reply(
                f"✅ <b>Dump channel set successfully!</b>\n\n"
                f"<b>Channel:</b> {channel.title}\n"
                f"<b>ID:</b> <code>{channel_id}</code>",
                parse_mode=ParseMode.HTML
            )
            
        except Exception as e:
            await message.reply(f"❌ Error verifying channel: {str(e)[:200]}")
    
    except Exception as e:
        logger.error(f"Error in set_dump_alt: {e}", exc_info=True)
        await message.reply("❌ An error occurred. Please try again.")
