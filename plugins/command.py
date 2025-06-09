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
                    try:
                        code = args[0].replace("adds_", "").strip()
                        if not code:
                            await message.reply("❌ Missing campaign code")
                            return
                
                        # Get campaign with proper datetime comparison
                        campaign = await hyoshcoder.campaigns.find_one({
                            "code": code,
                            "active": True,
                            "expires_at": {"$gt": datetime.now(pytz.UTC)}
                        })
                
                        if not campaign:
                            await message.reply("❌ Invalid or expired campaign link")
                            return
                
                        # Check view limits
                        if campaign["used_views"] >= campaign["max_views"]:
                            await message.reply("⚠️ This campaign has reached its view limit")
                            return
                
                        # Process redemption
                        async with await hyoshcoder.start_session() as session:
                            async with session.start_transaction():
                                # Verify campaign again within transaction
                                fresh_campaign = await hyoshcoder.campaigns.find_one(
                                    {"_id": campaign["_id"]},
                                    session=session
                                )
                                
                                if fresh_campaign["used_views"] >= fresh_campaign["max_views"]:
                                    await session.abort_transaction()
                                    await message.reply("⚠️ Campaign limit was just reached")
                                    return
                
                                # Update campaign views
                                await hyoshcoder.campaigns.update_one(
                                    {"_id": campaign["_id"]},
                                    {"$inc": {"used_views": 1}},
                                    session=session
                                )
                
                                # Calculate points with premium multiplier
                                user = await hyoshcoder.users.find_one(
                                    {"_id": message.from_user.id},
                                    {"premium.ad_multiplier": 1},
                                    session=session
                                )
                                multiplier = user.get("premium", {}).get("ad_multiplier", 1.0)
                                points = int(campaign["points_per_view"] * multiplier)
                
                                # Add points to user
                                await hyoshcoder.add_points(
                                    user_id=message.from_user.id,
                                    points=points,
                                    session=session,
                                    reason=f"Campaign: {campaign.get('name', 'Unknown')}"
                                )
                
                                # Record transaction
                                await hyoshcoder.transactions.insert_one({
                                    "user_id": message.from_user.id,
                                    "type": "campaign_reward",
                                    "amount": points,
                                    "timestamp": datetime.now(pytz.UTC),
                                    "campaign_id": campaign["_id"]
                                }, session=session)
                
                        # Success message
                        success_msg = (
                            f"🎉 You earned {points} points!\n\n"
                            f"Campaign: {campaign.get('name', 'Unknown')}\n"
                            f"Views remaining: {campaign['max_views'] - campaign['used_views'] - 1}"
                        )
                        
                        try:
                            await message.reply(success_msg)
                        except PeerIdInvalid:
                            logger.warning(f"Couldn't message user {message.from_user.id}")
                            # You might want to refund the points here if messaging fails
                
                    except Exception as e:
                        logger.error(f"Campaign redemption error: {str(e)}", exc_info=True)
                        await message.reply("⚠️ An error occurred. Please try again later.")

                # Handle points link redemption
                elif args[0].startswith("points_"):
                    code = args[0].replace("points_", "")
                    result = await hyoshcoder.claim_expend_points(user_id, code)
                    
                    if result["success"]:
                        await message.reply_text(
                            f"🎉 You claimed {result['points']} points!\n"
                            "Thanks for supporting the bot!"
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
async def addthumbs(client, message: Message):
    """Handle thumbnail upload and processing"""
    try:
        folder = "thumbnails"
        makedirs(folder, exist_ok=True)

        file_path = ospath.join(folder, f"thumb_{message.from_user.id}.jpg")
        await message.download(file_path)

        try:
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
                img.save(file_path, "JPEG", quality=85)
        except Exception as e:
            logger.warning(f"Thumbnail processing error: {str(e)}")

        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await message.reply_text("**Thumbnail saved successfully ✅**")

    except Exception as e:
        await message.reply_text(f"❌ Error saving thumbnail: {e}")

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
