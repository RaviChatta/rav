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
from helpers.utils import get_random_photo, get_random_animation, get_shortlink
from database.data import hyoshcoder
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN

@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "freepoints"
]))
async def command_handler(client: Client, message: Message):
    user_id = message.from_user.id
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
                        pass  # Already referred
                    elif referrer_id != user_id:
                        referrer = await hyoshcoder.read_user(referrer_id)
                        if referrer:
                            await hyoshcoder.set_referrer(user_id, referrer_id)
                            await hyoshcoder.add_points(referrer_id, reward)
                            cap = f"🎉 {message.from_user.mention} joined the bot through your referral! You received {reward} points."
                            await client.send_message(chat_id=referrer_id, text=cap)
                        else:
                            await message.reply("❌ The user who invited you does not exist.")
                
                # Then handle campaign
                elif args[0].startswith("adds_"):
                    unique_code = args[0].replace("adds_", "")
                    user = await hyoshcoder.get_user_by_code(unique_code)
                    
                    if user:
                        reward = await hyoshcoder.get_expend_points(user["_id"])
                        if reward > 0:
                            await hyoshcoder.add_points(user["_id"], reward)
                            await hyoshcoder.set_expend_points(user["_id"], 0, None)
                            cap = f"🎉 You earned {reward} points!"
                            await client.send_message(chat_id=user["_id"], text=cap)
                    else:
                        await message.reply("❌ The link is invalid or already used.")

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

        elif cmd in ["leaderboard", "lb"]:
            await show_leaderboard_ui(client, message)

        elif cmd == "freepoints":
            me = await client.get_me()
            unique_code = str(uuid.uuid4())[:8]
            invite_link = f"https://t.me/{me.username}?start=refer_{user_id}"
            points_link = f"https://t.me/{me.username}?start=adds_{unique_code}"
            
            # Generate shortlink if configured
            if settings.SHORTED_LINK and settings.SHORTED_LINK_API:
                try:
                    shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, points_link)
                except Exception as e:
                    logger.error(f"Shortlink error: {e}")
                    shortlink = points_link
            else:
                shortlink = points_link
            
            points = random.randint(5, 20)
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Share Bot", url=invite_link)],
                [InlineKeyboardButton("Watch Ad", url=shortlink)],
                [InlineKeyboardButton("Back", callback_data="help")]
            ])
            
            caption = (
                "**✨ Free Points System**\n\n"
                "Earn points by helping grow our community:\n\n"
                f"🔹 Share Bot: Get 10 points per referral\n"
                f"🔹 Watch Ads: Earn 5-20 points per ad\n"
                f"⭐ Premium Bonus: 2x points multiplier\n\n"
                f"🎁 You can earn up to {points} points right now!"
            )
            
            await message.reply_text(caption, reply_markup=buttons)

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

        elif cmd == "help":
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("ᴀᴜᴛᴏʀᴇɴᴀᴍᴇ", callback_data='file_names'),
                 InlineKeyboardButton('ᴛʜᴜᴍʙɴᴀɪʟ', callback_data='thumbnail'),
                 InlineKeyboardButton('ᴄᴀᴘᴛɪᴏɴ', callback_data='caption')],
                [InlineKeyboardButton('ᴍᴇᴛᴀᴅᴀᴛᴀ', callback_data='meta'),
                 InlineKeyboardButton('ꜱᴇᴛ ᴍᴇᴅɪᴀ', callback_data='setmedia'),
                 InlineKeyboardButton('ꜱᴇᴛ ᴅᴜᴍᴘ', callback_data='setdump')],
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
        await message.reply_text("An error occurred. Please try again later.")

# ... [rest of your existing code remains the same]
@Client.on_message(filters.private & filters.photo)
async def addthumbs(client: Client, message: Message):
    try:
        m = await message.reply_text("Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, message.photo.file_id)
        await m.edit_text("**Thumbnail saved successfully ✅**")
    except Exception as e:
        await message.reply_text(f"❌ Error saving thumbnail: {e}")

@Client.on_message(filters.command(["leaderboard", "lb"]))
async def leaderboard_command(client: Client, message: Message):
    await show_leaderboard_ui(client, message)

@Client.on_callback_query(filters.regex(r'^lb_period_'))
async def leaderboard_period_callback(client: Client, callback_query: CallbackQuery):
    """Handle leaderboard period changes"""
    user_id = callback_query.from_user.id
    period = callback_query.data.split('_')[-1]  # daily, weekly, monthly, alltime
    
    await hyoshcoder.set_leaderboard_period(user_id, period)
    await show_leaderboard_ui(client, callback_query.message)

@Client.on_callback_query(filters.regex(r'^lb_type_'))
async def leaderboard_type_callback(client: Client, callback_query: CallbackQuery):
    """Handle leaderboard type changes"""
    user_id = callback_query.from_user.id
    lb_type = callback_query.data.split('_')[-1]  # points, renames, referrals
    
    await hyoshcoder.set_leaderboard_type(user_id, lb_type)
    await show_leaderboard_ui(client, callback_query.message)

async def show_leaderboard_ui(client: Client, message: Union[Message, CallbackQuery]):
    """Display leaderboard with proper formatting and navigation"""
    if isinstance(message, CallbackQuery):
        user_id = message.from_user.id
        message = message.message  # Get the Message object from CallbackQuery
    else:
        user_id = message.from_user.id
    
    period = await hyoshcoder.get_leaderboard_period(user_id)
    lb_type = await hyoshcoder.get_leaderboard_type(user_id)
    
    leaders = await hyoshcoder.get_leaderboard(period, lb_type)
    
    if not leaders:
        text = "No leaderboard data available yet. Be the first to earn points!"
        buttons = InlineKeyboardMarkup([
            [InlineKeyboardButton("Back", callback_data="help")]
        ])
    else:
        # Format leaderboard message
        emoji = {
            "points": "✨",
            "renames": "📁",
            "referrals": "👥"
        }.get(lb_type, "🏆")
        
        text = (
            f"🏆 {period.capitalize()} {lb_type.capitalize()} Leaderboard:\n\n"
            f"{emoji} Top Performers {emoji}\n\n"
        )
        
        for i, user in enumerate(leaders[:10], 1):
            username = user.get('username', f"User {user.get('_id', 'N/A')}")
            value = user.get('value', 0)
            text += f"{i}. {username} - {value} {emoji}\n"
            if user.get('is_premium', False):
                text += "   ⭐ Premium User\n"
        
        # Create buttons for leaderboard navigation
        buttons = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("Daily", callback_data="lb_period_daily"),
                InlineKeyboardButton("Weekly", callback_data="lb_period_weekly"),
                InlineKeyboardButton("Monthly", callback_data="lb_period_monthly"),
                InlineKeyboardButton("All-Time", callback_data="lb_period_alltime")
            ],
            [
                InlineKeyboardButton("Points", callback_data="lb_type_points"),
                InlineKeyboardButton("Files", callback_data="lb_type_renames"),
                InlineKeyboardButton("Referrals", callback_data="lb_type_referrals")
            ],
            [InlineKeyboardButton("Back", callback_data="help")]
        ])
    
    # Edit or reply based on context
    if isinstance(message, Message) and message.reply_markup is None:
        await message.reply_text(text, reply_markup=buttons)
    else:
        await message.edit_text(text, reply_markup=buttons)
@Client.on_message(filters.private & filters.command("start") & filters.regex(r'points_'))
async def handle_points_link(client: Client, message: Message):
    try:
        code = message.text.split("_")[1]
        user_id = message.from_user.id
        
        result = await hyoshcoder.claim_points_link(user_id, code)
        
        if result["success"]:
            await message.reply_text(
                f"🎉 You claimed {result['points']} points!\n"
                f"Remaining claims: {result['remaining_claims']}"
            )
        else:
            await message.reply_text(f"❌ Could not claim points: {result['reason']}")
    except Exception as e:
        logger.error(f"Points link claim error: {e}")
        await message.reply_text("❌ Invalid points link")
