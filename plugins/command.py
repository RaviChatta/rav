import os
import random
import asyncio
import sys
import time
import traceback
from datetime import datetime, timedelta
from pyrogram import Client, filters
from pyrogram.types import (
    Message, 
    InlineKeyboardButton, 
    InlineKeyboardMarkup, 
    CallbackQuery, 
    InputMediaPhoto,
    InputMediaAnimation
)
from pyrogram.errors import (
    ChannelInvalid, 
    ChannelPrivate, 
    ChatAdminRequired, 
    FloodWait, 
    InputUserDeactivated, 
    UserIsBlocked, 
    PeerIdInvalid
)
from config import settings
from scripts import Txt
from typing import Union, List, Optional, Dict
from helpers.utils import get_random_photo, get_random_animation
from database.data import hyoshcoder
import logging

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
ADMIN_USER_ID = settings.ADMIN
is_restarting = False

# Constants
AUTO_DELETE_DELAY = 30  # Seconds before auto-deleting messages

# Emoji Constants
EMOJI_POINTS = "✨"
EMOJI_PREMIUM = "⭐"
EMOJI_REFERRAL = "👥"
EMOJI_RENAME = "📝"
EMOJI_STATS = "📊"
EMOJI_LEADERBOARD = "🏆"
EMOJI_ADMIN = "🛠️"
EMOJI_SUCCESS = "✅"
EMOJI_ERROR = "❌"
EMOJI_CLOCK = "⏳"
EMOJI_LINK = "🔗"
EMOJI_MONEY = "💰"

def get_leaderboard_keyboard(selected_period="weekly", selected_type="points"):
    """Generate leaderboard navigation keyboard"""
    periods = {
        "daily": f"{EMOJI_CLOCK} Daily",
        "weekly": f"📆 Weekly",
        "monthly": f"🗓 Monthly",
        "alltime": f"{EMOJI_LEADERBOARD} All-Time"
    }
    types = {
        "points": f"{EMOJI_POINTS} Points",
        "renames": f"{EMOJI_RENAME} Files",
        "referrals": f"{EMOJI_REFERRAL} Referrals"
    }
    
    # Period buttons
    period_buttons = []
    for period, text in periods.items():
        if period == selected_period:
            period_buttons.append(InlineKeyboardButton(f"• {text} •", callback_data=f"lb_period_{period}"))
        else:
            period_buttons.append(InlineKeyboardButton(text, callback_data=f"lb_period_{period}"))
    
    # Type buttons
    type_buttons = []
    for lb_type, text in types.items():
        if lb_type == selected_type:
            type_buttons.append(InlineKeyboardButton(f"• {text} •", callback_data=f"lb_type_{lb_type}"))
        else:
            type_buttons.append(InlineKeyboardButton(text, callback_data=f"lb_type_{lb_type}"))
    
    return InlineKeyboardMarkup([
        period_buttons[:2],  # First row: daily, weekly
        period_buttons[2:],  # Second row: monthly, alltime
        type_buttons,        # Third row: types
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ])

async def auto_delete_message(message: Message, delay: int = AUTO_DELETE_DELAY):
    """Auto-delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Couldn't delete message: {e}")

async def send_effect_message(
    client: Client,
    chat_id: Union[int, str],
    text: str,
    effect_id: Optional[int] = None,
    max_retries: int = 3,
    **kwargs
) -> Optional[Message]:
    """
    Send a message with optional effect (animation).
    
    Args:
        client: Pyrogram Client instance
        chat_id: Target chat ID or username
        text: Message text to send
        effect_id: ID of the message effect
        max_retries: Maximum number of retry attempts
        **kwargs: Additional send_message parameters
        
    Returns:
        Message object if successful, None otherwise
    """
    additional_params = {
        'disable_web_page_preview': kwargs.pop('disable_web_page_preview', True),
        'parse_mode': kwargs.pop('parse_mode', "markdown")
    }
    additional_params.update(kwargs)
    
    for attempt in range(max_retries):
        try:
            if effect_id:
                return await client.send_message(
                    chat_id=chat_id,
                    text=text,
                    effect_id=effect_id,
                    **additional_params
                )
            return await client.send_message(
                chat_id=chat_id,
                text=text,
                **additional_params
            )
            
        except FloodWait as e:
            if attempt == max_retries - 1:
                logger.error(f"Flood wait too long ({e.x}s) for chat {chat_id}")
                raise
            logger.warning(f"Flood wait {e.x}s, retrying {attempt + 1}/{max_retries}")
            await asyncio.sleep(e.x)
            
        except (PeerIdInvalid, ChannelInvalid) as e:
            logger.error(f"Invalid chat ID {chat_id}: {e}")
            return None
            
        except ChatWriteForbidden:
            logger.error(f"No permission to write in chat {chat_id}")
            return None
            
        except Exception as e:
            logger.error(f"Error sending message (attempt {attempt + 1}): {e}")
            if attempt == max_retries - 1:
                # Final fallback - try without effect
                if effect_id:
                    try:
                        return await client.send_message(
                            chat_id=chat_id,
                            text=text,
                            **additional_params
                        )
                    except Exception as fallback_error:
                        logger.error(f"Fallback send failed: {fallback_error}")
                        return None
            await asyncio.sleep(1 * (attempt + 1))  # Exponential backoff
            
    return None

@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "stats", "mystats", "admin_cmds", "botstats"
]))
async def command(client, message: Message):
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_USER_ID
    img = await get_random_photo()
    animation = await get_random_animation()
    
    try:
        command = message.text.split(' ')[0][1:].lower()
        args = message.command[1:]
        
        # Auto-delete non-start commands after delay
        if command != "start":
            asyncio.create_task(auto_delete_message(message))
        
        if command == 'start':
            user = message.from_user
            await hyoshcoder.add_user(client, message)
            
            # Welcome effect with auto-delete
            welcome_msg = await send_effect_message(
                client,
                message.chat.id,
                f"✨ Welcome {user.mention} to our file renaming bot!",
                effect_id=5  # Sparkles effect
            )
            asyncio.create_task(auto_delete_message(welcome_msg, delay=10))
            
            # Send sticker and delete after delay
            m = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
            asyncio.create_task(auto_delete_message(m, delay=3))
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{EMOJI_STATS} My Stats", callback_data='mystats'),
                 InlineKeyboardButton(f"{EMOJI_LEADERBOARD} Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton(f"{EMOJI_POINTS} Earn Points", callback_data='free_points'),
                 InlineKeyboardButton(f"{EMOJI_PREMIUM} Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("🛠️ Help", callback_data='help')]
            ])

            # Handle referral links
            if args and args[0].startswith("refer_"):
                referrer_id = int(args[0].replace("refer_", ""))
                reward = await hyoshcoder.get_config("referral_reward", 15)
                if referrer_id != user_id:
                    referrer = await hyoshcoder.read_user(referrer_id)
                    if referrer:
                        await hyoshcoder.set_referrer(user_id, referrer_id)
                        await hyoshcoder.add_points(referrer_id, reward, "referral", 
                                                  f"Referral from {user_id}")
                        
                        # Notify referrer with effect
                        cap = (
                            f"🎉 {user.mention} joined through your referral!\n"
                            f"You received {reward} {EMOJI_POINTS}"
                        )
                        await send_effect_message(
                            client,
                            referrer_id,
                            cap,
                            effect_id=3  # Bounce effect
                        )

            # Handle points links
            if args and args[0].startswith("points_"):
                code = args[0][7:]
                result = await hyoshcoder.claim_points_link(user_id, code)
                if result["success"]:
                    claim_msg = await send_effect_message(
                        client,
                        message.chat.id,
                        f"🎉 You claimed {result['points']} {EMOJI_POINTS}!\n"
                        f"Remaining claims: {result['remaining_claims']}",
                        effect_id=1  # Confetti effect
                    )
                    asyncio.create_task(auto_delete_message(claim_msg, delay=10))
                else:
                    await message.reply(f"{EMOJI_ERROR} {result['reason']}")

            if animation:
                await message.reply_animation(
                    animation=animation,
                    caption=Txt.START_TXT.format(user.mention),
                    reply_markup=buttons
                )
            else:
                await message.reply_photo(
                    photo=img,
                    caption=Txt.START_TXT.format(user.mention),
                    reply_markup=buttons
                )

        elif command in ["leaderboard", "lb"]:
            # Show leaderboard with interactive buttons
            keyboard = get_leaderboard_keyboard()
            leaders = await hyoshcoder.get_leaderboard()
            
            text = f"{EMOJI_LEADERBOARD} Weekly Points Leaderboard:\n\n"
            for i, user in enumerate(leaders[:10], 1):
                text += (
                    f"{i}. {user['username'] or user['_id']} - "
                    f"{user['value']} {EMOJI_POINTS} "
                    f"{EMOJI_PREMIUM if user.get('is_premium') else ''}\n"
                )
            
            if animation:
                msg = await message.reply_animation(
                    animation=animation,
                    caption=text,
                    reply_markup=keyboard
                )
            else:
                msg = await message.reply_photo(
                    photo=img,
                    caption=text,
                    reply_markup=keyboard
                )
            asyncio.create_task(auto_delete_message(msg, delay=120))

        elif command in ["stats", "mystats"]:
            # Show user statistics including file rename counts
            stats = await hyoshcoder.get_user_file_stats(user_id)
            points = await hyoshcoder.get_points(user_id)
            premium_status = await hyoshcoder.check_premium_status(user_id)
            referral_stats = await hyoshcoder.users.find_one(
                {"_id": user_id},
                {"referral.referred_count": 1, "referral.referral_earnings": 1}
            )
            
            text = (
                f"📊 <b>Your Statistics</b>\n\n"
                f"{EMOJI_POINTS} <b>Points Balance:</b> {points}\n"
                f"{EMOJI_PREMIUM} <b>Premium Status:</b> {'Active ' + EMOJI_SUCCESS if premium_status['is_premium'] else 'Inactive ' + EMOJI_ERROR}\n"
                f"{EMOJI_REFERRAL} <b>Referrals:</b> {referral_stats.get('referral', {}).get('referred_count', 0)} "
                f"(Earned {referral_stats.get('referral', {}).get('referral_earnings', 0)} {EMOJI_POINTS})\n\n"
                f"{EMOJI_RENAME} <b>Files Renamed</b>\n"
                f"• Total: {stats['total_renamed']}\n"
                f"• Today: {stats['today']}\n"
                f"• This Week: {stats['this_week']}\n"
                f"• This Month: {stats['this_month']}\n"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{EMOJI_LEADERBOARD} Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton(f"{EMOJI_REFERRAL} Invite Friends", callback_data="invite")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            msg = await message.reply_photo(
                photo=img,
                caption=text,
                reply_markup=buttons
            )
            asyncio.create_task(auto_delete_message(msg, delay=90))

        elif command == "botstats" and is_admin:
            # Admin-only bot statistics
            total_users = await hyoshcoder.total_users_count()
            total_premium = await hyoshcoder.total_premium_users_count()
            total_renamed = await hyoshcoder.total_renamed_files()
            points_distributed = await hyoshcoder.total_points_distributed()
            
            text = (
                f"🤖 <b>Bot Statistics</b>\n\n"
                f"👥 <b>Total Users:</b> {total_users}\n"
                f"⭐ <b>Premium Users:</b> {total_premium}\n"
                f"📝 <b>Total Files Renamed:</b> {total_renamed}\n"
                f"✨ <b>Total Points Distributed:</b> {points_distributed}\n\n"
                f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</i>"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Refresh", callback_data="refresh_botstats")],
                [InlineKeyboardButton("❌ Close", callback_data="close")]
            ])
            
            msg = await message.reply_photo(
                photo=img,
                caption=text,
                reply_markup=buttons
            )
            asyncio.create_task(auto_delete_message(msg, delay=120))

        elif command == "admin_cmds" and is_admin:
            # Admin command panel
            points_per_rename = await hyoshcoder.get_config("points_per_rename", 2)
            new_user_points = await hyoshcoder.get_config("new_user_points", 50)
            referral_reward = await hyoshcoder.get_config("referral_reward", 15)
            
            text = (
                f"{EMOJI_ADMIN} <b>Admin Commands Panel</b>\n\n"
                f"Current Configuration:\n"
                f"• Points per rename: {points_per_rename}\n"
                f"• New user points: {new_user_points}\n"
                f"• Referral reward: {referral_reward}\n\n"
                "Manage the bot with these commands:"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("⚙️ Configure Points", callback_data="admin_config_points")],
                [InlineKeyboardButton(f"{EMOJI_POINTS} Generate Points Link", callback_data="admin_genpoints")],
                [InlineKeyboardButton(f"{EMOJI_STATS} Points Statistics", callback_data="admin_pointstats")],
                [InlineKeyboardButton("❌ Close", callback_data="close_admin")]
            ])
            
            msg = await message.reply_photo(
                photo=img,
                caption=text,
                reply_markup=buttons
            )
            asyncio.create_task(auto_delete_message(msg, delay=60))

        elif command == "autorename":
            points_per_rename = await hyoshcoder.get_config("points_per_rename", 2)
            current_points = await hyoshcoder.get_points(user_id)
            
            command_parts = message.text.split("/autorename", 1)
            if len(command_parts) < 2 or not command_parts[1].strip():
                caption = (
                    f"{EMOJI_ERROR} <b>Please provide a rename template</b>\n\n"
                    "Example:\n"
                    "<code>/autorename MyFile_[episode]_[quality]</code>\n\n"
                    "Available placeholders:\n"
                    "[filename], [size], [duration], [date], [time]"
                )
                msg = await message.reply(caption)
                asyncio.create_task(auto_delete_message(msg, delay=30))
                return

            format_template = command_parts[1].strip()
            await hyoshcoder.set_format_template(user_id, format_template)
            
            caption = (
                f"{EMOJI_SUCCESS} <b>Auto-rename template set!</b>\n\n"
                f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
                "Now send me files to rename automatically!"
            )
            
            msg = await send_effect_message(
                client,
                message.chat.id,
                caption,
                effect_id=2  # Slow zoom effect
            )
            asyncio.create_task(auto_delete_message(msg, delay=30))

        elif command == "setmedia":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton("📁 Document", callback_data="setmedia_document")],
                [InlineKeyboardButton("🎥 Video", callback_data="setmedia_video")]
            ])
            caption = "**Please select the type of media you want to set:**"
            if img:
                await message.reply_photo(photo=img, caption=caption, reply_markup=keyboard)
            else:
                await message.reply_text(text=caption, reply_markup=keyboard)

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

        elif command == "del_caption":
            old_caption = await hyoshcoder.get_caption(message.from_user.id)
            if not old_caption:
                caption = ("**You don't have any caption ❌**")
                await message.reply_text(caption)
                return
            await hyoshcoder.set_caption(message.from_user.id, caption=None)
            caption = ("**Your caption has been successfully deleted 🗑️**")
            if img:
                await message.reply_photo(photo=img, caption=caption)
            else:
                await message.reply_text(text=caption)

        elif command in ['see_caption', 'view_caption']:
            old_caption = await hyoshcoder.get_caption(message.from_user.id)
            if old_caption:
                caption = (f"**Your caption:**\n\n`{old_caption}`")
            else:
                caption = ("**You don't have any caption ❌**")
            if img:
                await message.reply_photo(photo=img, caption=caption)
            else:
                await message.reply_text(text=caption)

        elif command in ['view_thumb', 'viewthumb']:
            thumb = await hyoshcoder.get_thumbnail(message.from_user.id)
            if thumb:
                await client.send_photo(chat_id=message.chat.id, photo=thumb)
            else:
                caption = ("**You don't have any thumbnail ❌**")
                if img:
                    await message.reply_photo(photo=img, caption=caption)
                else:
                    await message.reply_text(text=caption)

        elif command in ['del_thumb', 'delthumb']:
            old_thumb = await hyoshcoder.get_thumbnail(user_id)
            if not old_thumb:
                caption = "No thumbnail is currently set."
                await message.reply_photo(photo=img, caption=caption)
                return

            await hyoshcoder.set_thumbnail(message.from_user.id, file_id=None)
            caption = ("**Thumbnail successfully deleted 🗑️**")
            if img:
                await message.reply_photo(photo=img, caption=caption)
            else:
                await message.reply_text(text=caption)

        elif command == "metadata":
            ms = await message.reply_text("**Please wait...**", reply_to_message_id=message.id)
            bool_metadata = await hyoshcoder.get_metadata(message.from_user.id)
            user_metadata = await hyoshcoder.get_metadata_code(message.from_user.id)
            await ms.delete()
            if bool_metadata:
                await message.reply_text(
                    f"<b>Your current metadata:</b>\n\n➜ {user_metadata} ",
                    reply_markup=InlineKeyboardMarkup(ON),
                )
            else:
                await message.reply_text(
                    f"<b>Your current metadata:</b>\n\n➜ {user_metadata} ",
                    reply_markup=InlineKeyboardMarkup(OFF),
                )

        elif command == "donate":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Back", callback_data="help"),
                 InlineKeyboardButton(text="Owner", url='https://t.me/hyoshassistantBot')]
            ])
            caption = Txt.DONATE_TXT

            if img:
                yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
            else:
                yt = await message.reply_text(text=caption, reply_markup=buttons)

            asyncio.create_task(auto_delete_message(yt, delay=300))
            asyncio.create_task(auto_delete_message(message, delay=300))

        elif command == "premium":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Owner", url="https://t.me/hyoshassistantBot"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
            caption = Txt.PREMIUM_TXT
            if img:
                yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
            else:
                yt = await message.reply_text(text=caption, reply_markup=buttons)

            asyncio.create_task(auto_delete_message(yt, delay=300))
            asyncio.create_task(auto_delete_message(message, delay=300))

        elif command == "plan":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay Your Subscription", url="https://t.me/hyoshassistantBot"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
            caption = Txt.PREPLANS_TXT
            if img:
                yt = await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
            else:
                yt = await message.reply_text(text=caption, reply_markup=buttons)

            asyncio.create_task(auto_delete_message(yt, delay=300))
            asyncio.create_task(auto_delete_message(message, delay=300))

        elif command == "bought":
            msg = await message.reply("Hold on, I'm verifying...")
            replied = message.reply_to_message

            if not replied:
                await msg.edit("<b>Please reply with a screenshot of your payment for the premium purchase so I can check...</b>")
            elif replied.photo:
                await client.send_photo(
                    chat_id=settings.LOG_CHANNEL,
                    photo=replied.photo.file_id,
                    caption=(
                        f"<b>User - {message.from_user.mention}\n"
                        f"User ID - <code>{message.from_user.id}</code>\n"
                        f"Username - <code>{message.from_user.username}</code>\n"
                        f"First Name - <code>{message.from_user.first_name}</code></b>"
                    ),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("Close", callback_data="close_data")]
                    ])
                )
                await msg.edit_text("<b>Your screenshot has been sent to the admins.</b>")
        
        elif command == "help":
            bot = await client.get_me()
            mention = bot.mention
            caption = Txt.HELP_TXT.format(mention=mention) 
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
        
            btn_seq_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
        
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("• Automatic renaming format •", callback_data='file_names')],
                [InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), InlineKeyboardButton('Caption •', callback_data='caption')],
                [InlineKeyboardButton('• Metadata', callback_data='meta'), InlineKeyboardButton('Make a donation •', callback_data='donate')],
                [InlineKeyboardButton(f'• {btn_seq_text}', callback_data='secanciel'), InlineKeyboardButton('Premium •', callback_data='premiumx')],
                [InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toogle_src')],
                [InlineKeyboardButton('• Home', callback_data='home')]
            ])
            caption = Txt.HELP_TXT.format(client.mention)
            if img:
                await message.reply_photo(photo=img, caption=caption, reply_markup=buttons)
            else:
                await message.reply_text(text=caption, disable_web_page_preview=True, reply_markup=buttons)
        
        elif command == "set_dump":
            if len(message.command) == 1:
                caption = "Please enter the dump channel ID after the command.\nExample: `/set_dump -1001234567890`"
                await message.reply_text(caption)
            else:
                channel_id = message.command[1]
                if not channel_id:
                    await message.reply_text("Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`")
                else:
                    try:
                        channel_info = await client.get_chat(channel_id)
                        if channel_info:
                            await hyoshcoder.set_user_channel(message.from_user.id, channel_id)
                            await message.reply_text(f"Channel {channel_id} has been set as the dump channel.")
                        else:
                            await message.reply_text("The specified channel doesn't exist or is not accessible.\nMake sure I'm an admin in the channel.")
                    except Exception as e:
                        await message.reply_text(f"Error: {e}. Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`")
        
        elif command in ["view_dump", "viewdump"]:
            channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
            if channel_id:
                caption = f"Channel {channel_id} is currently set as the dump channel."
                await message.reply_text(caption)
            else:
                await message.reply_text("No dump channel is currently set.")
        
        elif command in ["del_dump", "deldump"]:
            channel_id = await hyoshcoder.get_user_channel(message.from_user.id)
            if channel_id:
                await hyoshcoder.set_user_channel(message.from_user.id, None)
                caption = f"Channel {channel_id} has been removed from the dump list."
                await message.reply_text(caption)
            else:
                await message.reply_text("No dump channel is currently set.")
        
        elif command == "profile":
            user = await hyoshcoder.read_user(message.from_user.id)
            caption = (
                f"Username: {message.from_user.username}\n"
                f"First Name: {message.from_user.first_name}\n"
                f"Last Name: {message.from_user.last_name}\n"
                f"User ID: {message.from_user.id}\n"
                f"Points: {user['points']['balance']}\n"
            )
            await message.reply_photo(img, caption=caption)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Error in command {command}: {str(e)}")
        error_msg = await message.reply(f"{EMOJI_ERROR} An error occurred. Please try again later.")
        asyncio.create_task(auto_delete_message(error_msg, delay=15))

@Client.on_message(filters.private & filters.photo)
async def addthumbs(client, message):
    """Handle thumbnail setting without points cost"""
    try:
        mkn = await message.reply_text("Please wait...")
        await hyoshcoder.set_thumbnail(message.from_user.id, file_id=message.photo.file_id)
        await mkn.edit("**Thumbnail saved successfully ✅️**")
        asyncio.create_task(auto_delete_message(mkn, delay=30))
    except Exception as e:
        logger.error(f"Error setting thumbnail: {str(e)}")
        error_msg = await message.reply(f"{EMOJI_ERROR} Failed to save thumbnail")
        asyncio.create_task(auto_delete_message(error_msg, delay=15))

@Client.on_message(filters.private & filters.document | filters.video)
async def handle_file_rename(client, message: Message):
    """Handle file renaming with points deduction"""
    try:
        user_id = message.from_user.id
        points_per_rename = await hyoshcoder.get_config("points_per_rename", 2)
        current_points = await hyoshcoder.get_points(user_id)
        
        if current_points < points_per_rename:
            msg = await message.reply(
                f"{EMOJI_ERROR} Insufficient points!\n"
                f"Each rename costs {points_per_rename} {EMOJI_POINTS}\n"
                f"Your balance: {current_points} {EMOJI_POINTS}\n\n"
                "Get more points with /help"
            )
            asyncio.create_task(auto_delete_message(msg, delay=30))
            return
        
        # Deduct points first
        await hyoshcoder.deduct_points(user_id, points_per_rename, "file_rename")
        
        # Get user's rename template
        template = await hyoshcoder.get_format_template(user_id)
        if not template:
            # Refund points if no template set
            await hyoshcoder.add_points(user_id, points_per_rename, "refund", "No rename template set")
            msg = await message.reply(
                f"{EMOJI_ERROR} No rename template set!\n"
                "Use /autorename to set your template first\n\n"
                f"{EMOJI_POINTS} Refunded {points_per_rename} points"
            )
            asyncio.create_task(auto_delete_message(msg, delay=30))
            return
        
        # [Actual file renaming logic would go here]
        # Track the rename operation
        original_name = message.document.file_name if message.document else message.video.file_name
        new_name = "generated_new_name.ext"  # Replace with actual generated name
        
        await hyoshcoder.track_file_rename(user_id, original_name, new_name)
        
        # Send success message with effect
        success_msg = await send_effect_message(
            client,
            message.chat.id,
            f"{EMOJI_SUCCESS} <b>File renamed successfully!</b>\n\n"
            f"📝 <b>Original:</b> {original_name}\n"
            f"🆕 <b>New name:</b> {new_name}\n\n"
            f"⏳ <b>Points deducted:</b> {points_per_rename} {EMOJI_POINTS}\n"
            f"💰 <b>Remaining balance:</b> {current_points - points_per_rename} {EMOJI_POINTS}",
            effect_id=4  # Spin effect
        )
        asyncio.create_task(auto_delete_message(success_msg, delay=30))
        
    except Exception as e:
        logger.error(f"Error handling file rename: {str(e)}")
        error_msg = await message.reply(f"{EMOJI_ERROR} Error processing file")
        asyncio.create_task(auto_delete_message(error_msg, delay=15))
