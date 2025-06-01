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
from pyrogram.enums import ChatMemberStatus
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
        await message.reply_text("⚠️ An error occurred. Please try again.")




@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    mkn = await message.reply_text("Please wait...")

    try:
        # Download the photo
        file_path = await message.download()

        # Crop and enhance image locally
        with Image.open(file_path) as img:
            img = img.convert("RGB")
            w, h = img.size
            min_edge = min(w, h)
            left = (w - min_edge) // 2
            top = (h - min_edge) // 2
            img = img.crop((left, top, left + min_edge, top + min_edge))
            img = img.resize((320, 320), Image.LANCZOS)
            img = ImageEnhance.Sharpness(img).enhance(1.2)
            img = ImageEnhance.Contrast(img).enhance(1.1)
            img = ImageEnhance.Brightness(img).enhance(1.05)
            # No upload needed — only processed locally

        # Save the original Telegram photo file_id
        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)

        # Confirm and auto-delete message after 5 seconds
        success = await mkn.edit_text("**Thumbnail saved successfully ✅️**")
        await asyncio.sleep(5)
        await success.delete()

    except Exception as e:
        await mkn.edit_text(f"❌ Error saving thumbnail: {e}")


@Client.on_message(filters.command(["leaderboard", "lb"]))
async def leaderboard_command(client: Client, message: Message):
    await show_leaderboard_ui(client, message)

@Client.on_callback_query(filters.regex(r'^lb_(period|type)_'))
async def leaderboard_callback(client: Client, callback: CallbackQuery):
    """Handle all leaderboard button presses"""
    user_id = callback.from_user.id
    data_parts = callback.data.split('_')
    
    if data_parts[1] == "period":
        period = data_parts[2]  # daily, weekly, monthly, alltime
        await hyoshcoder.set_leaderboard_period(user_id, period)
    else:
        lb_type = data_parts[2]  # points, renames, referrals
        await hyoshcoder.set_leaderboard_type(user_id, lb_type)
    
    await show_leaderboard_ui(client, callback.message)
    
@Client.on_callback_query(filters.regex(r'^lb_type_'))
async def leaderboard_type_callback(client: Client, callback_query: CallbackQuery):
    """Handle leaderboard type changes"""
    user_id = callback_query.from_user.id
    lb_type = callback_query.data.split('_')[-1]  # points, renames, referrals
    
    await hyoshcoder.set_leaderboard_type(user_id, lb_type)
    await show_leaderboard_ui(client, callback_query.message)

async def show_leaderboard_ui(client: Client, message: Union[Message, CallbackQuery]):
    """Improved leaderboard display with working buttons"""
    user_id = message.from_user.id if isinstance(message, Message) else message.from_user.id
    msg = message if isinstance(message, Message) else message.message
    
    period = await hyoshcoder.get_leaderboard_period(user_id)
    lb_type = await hyoshcoder.get_leaderboard_type(user_id)
    
    leaders = await hyoshcoder.get_leaderboard(period, lb_type)
    
    if not leaders:
        text = "📊 No leaderboard data yet!"
        buttons = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data="help")]])
    else:
        emoji = {"points": "⭐", "renames": "📁", "referrals": "👥"}.get(lb_type, "🏆")
        text = f"🏆 {period.upper()} {lb_type.upper()} LEADERBOARD:\n\n"
        
        for i, user in enumerate(leaders[:10], 1):
            username = user.get('username', f"User {user['_id']}")
            value = user['value']
            text += f"{i}. {username} - {value} {emoji}\n"
            if user.get('is_premium'):
                text += "   💎 PREMIUM\n"
    
    # Active button styling
    active_btn_style = {"text": f"• {period.upper()} •" if "period" in callback.data else f"• {lb_type.upper()} •"}
    
    buttons = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("DAILY", callback_data="lb_period_daily"),
            InlineKeyboardButton("WEEKLY", callback_data="lb_period_weekly"),
            InlineKeyboardButton("MONTHLY", callback_data="lb_period_monthly"),
            InlineKeyboardButton("ALL-TIME", callback_data="lb_period_alltime")
        ],
        [
            InlineKeyboardButton("POINTS", callback_data="lb_type_points"),
            InlineKeyboardButton("FILES", callback_data="lb_type_renames"),
            InlineKeyboardButton("REFERRALS", callback_data="lb_type_referrals")
        ],
        [InlineKeyboardButton("BACK", callback_data="help")]
    ])
    
    try:
        if isinstance(message, CallbackQuery):
            await msg.edit_text(text, reply_markup=buttons)
        else:
            await msg.reply_text(text, reply_markup=buttons)
    except Exception as e:
        logger.error(f"Leaderboard error: {e}")
@Client.on_message(filters.private & filters.command("start") & filters.regex(r'adds_'))
async def handle_ad_link(client: Client, message: Message):
    try:
        unique_code = message.text.split("adds_")[1]
        user_id = message.from_user.id
        
        # Check if the code exists and hasn't been used
        user_data = await hyoshcoder.get_user_by_code(unique_code)
        
        if not user_data:
            await message.reply_text("❌ The link is invalid or already used.")
            return
            
        if user_data.get('ad_code_used', False):
            await message.reply_text("❌ This ad link has already been used.")
            return
            
        reward = user_data.get('ad_reward', 0)
        
        if reward <= 0:
            await message.reply_text("❌ No reward available for this link.")
            return
            
        # Add points and mark code as used
        await hyoshcoder.add_points(user_id, reward, "ad_reward", f"Ad reward from code {unique_code}")
        await hyoshcoder.mark_ad_code_used(unique_code)
        
        await message.reply_text(f"🎉 You earned {reward} points!")
        
        # Notify the user who shared the link
        if user_data['_id'] != user_id:
            try:
                await client.send_message(
                    user_data['_id'],
                    f"🎉 Someone used your ad link! You earned {reward//2} points."
                )
                await hyoshcoder.add_points(user_data['_id'], reward//2, "referral_ad", f"Bonus for ad link usage by {user_id}")
            except Exception as e:
                logger.error(f"Error notifying referrer: {e}")
                
    except Exception as e:
        logger.error(f"Ad link error: {e}")
        await message.reply_text("An error occurred. Please try again later.")
@Client.on_message(filters.private & filters.command("start") & filters.regex(r'points_'))
async def handle_points_link(client: Client, message: Message):
    try:
        code = message.text.split("points_")[1]
        user_id = message.from_user.id
        
        result = await hyoshcoder.claim_expend_points(user_id, code)
        
        if result["success"]:
            await message.reply_text(
                f"🎉 You claimed {result['points']} points!\n"
                "Thanks for supporting the bot!"
            )
        else:
            await message.reply_text(f"❌ Could not claim points: {result['error']}")
            
    except Exception as e:
        logger.error(f"Points link claim error: {e}")
        await message.reply_text("❌ Invalid points link")
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
