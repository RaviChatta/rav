import os
import random
import asyncio
import logging
from datetime import datetime
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from pyrogram.errors import FloodWait, ChatWriteForbidden
from config import settings
from scripts import Txt
from helpers.utils import get_random_photo, get_random_animation
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ADMIN_USER_ID = settings.ADMIN
AUTO_DELETE_DELAY = 30  # Seconds before auto-deleting messages

# Emoji Constants
EMOJI = {
    'points': "✨",
    'premium': "⭐",
    'referral': "👥",
    'rename': "📝",
    'stats': "📊",
    'leaderboard': "🏆",
    'admin': "🛠️",
    'success': "✅",
    'error': "❌",
    'clock': "⏳",
    'link': "🔗",
    'money': "💰",
    'file': "📁",
    'video': "🎥"
}

async def auto_delete_message(message: Message, delay: int = AUTO_DELETE_DELAY):
    """Auto-delete message after delay"""
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception as e:
        logger.warning(f"Couldn't delete message: {e}")

async def send_response(
    client: Client,
    chat_id: int,
    text: str,
    reply_markup=None,
    photo=None,
    animation=None,
    delete_after: int = AUTO_DELETE_DELAY,
    parse_mode: enums.ParseMode = enums.ParseMode.HTML
):
    """Send response with auto-delete and media support"""
    try:
        if animation:
            msg = await client.send_animation(
                chat_id=chat_id,
                animation=animation,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        elif photo:
            msg = await client.send_photo(
                chat_id=chat_id,
                photo=photo,
                caption=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode
            )
        else:
            msg = await client.send_message(
                chat_id=chat_id,
                text=text,
                reply_markup=reply_markup,
                parse_mode=parse_mode,
                disable_web_page_preview=True
            )
        
        if delete_after:
            asyncio.create_task(auto_delete_message(msg, delete_after))
        return msg
    except Exception as e:
        logger.error(f"Response error: {e}")
        try:
            return await client.send_message(
                chat_id=chat_id,
                text="An error occurred while processing this message.",
                parse_mode=None
            )
        except:
            return None

def get_leaderboard_keyboard(selected_period="weekly", selected_type="points"):
    """Generate leaderboard navigation keyboard"""
    periods = {
        "daily": f"{EMOJI['clock']} Daily",
        "weekly": f"📆 Weekly",
        "monthly": f"🗓 Monthly",
        "alltime": f"{EMOJI['leaderboard']} All-Time"
    }
    types = {
        "points": f"{EMOJI['points']} Points",
        "renames": f"{EMOJI['rename']} Files",
        "referrals": f"{EMOJI['referral']} Referrals"
    }
    
    # Create buttons
    period_buttons = [
        InlineKeyboardButton(
            f"• {text} •" if period == selected_period else text,
            callback_data=f"lb_period_{period}"
        ) for period, text in periods.items()
    ]
    
    type_buttons = [
        InlineKeyboardButton(
            f"• {text} •" if lb_type == selected_type else text,
            callback_data=f"lb_type_{lb_type}"
        ) for lb_type, text in types.items()
    ]
    
    return InlineKeyboardMarkup([
        period_buttons[:2],
        period_buttons[2:],
        type_buttons,
        [InlineKeyboardButton("🔙 Back", callback_data="help")]
    ])

@Client.on_message(filters.private & filters.command([
    "start", "autorename", "setmedia", "set_caption", "del_caption", "see_caption",
    "view_caption", "viewthumb", "view_thumb", "del_thumb", "delthumb", "metadata",
    "donate", "premium", "plan", "bought", "help", "set_dump", "view_dump", "viewdump",
    "del_dump", "deldump", "profile", "leaderboard", "lb", "mystats", "freepoints",
    "settitle", "setauthor", "setartist", "setaudio", "setsubtitle", "setvideo"
]))
async def command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    is_admin = user_id == ADMIN_USER_ID
    img = await get_random_photo()
    animation = await get_random_animation()
    
    try:
        # Safely get command and arguments
        command = message.command
        if not command:
            return
            
        cmd = command[0].lower()
        args = command[1:]
        
        # Auto-delete non-start commands after delay
        if cmd != "start":
            asyncio.create_task(auto_delete_message(message))
        
        if cmd == 'start':
            user = message.from_user
            await hyoshcoder.add_user(user_id)
            
            # Welcome message
            welcome_msg = await send_response(
                client,
                message.chat.id,
                f"✨ Welcome {user.mention} to our file renaming bot!",
                delete_after=10
            )
            
            # Send sticker
            m = await message.reply_sticker("CAACAgIAAxkBAALmzGXSSt3ppnOsSl_spnAP8wHC26jpAAJEGQACCOHZSVKp6_XqghKoHgQ")
            asyncio.create_task(auto_delete_message(m, delay=3))
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{EMOJI['stats']} My Stats", callback_data='mystats'),
                 InlineKeyboardButton(f"{EMOJI['leaderboard']} Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton(f"{EMOJI['points']} Earn Points", callback_data='freepoints'),
                 InlineKeyboardButton(f"{EMOJI['premium']} Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("🛠️ Help", callback_data='help')]
            ])

            # Handle referral links
            if len(args) > 0 and args[0].startswith("refer_"):
                try:
                    referrer_id = int(args[0].replace("refer_", ""))
                    config = await hyoshcoder.get_config("points_config") or {}
                    reward = config.get('referral_bonus', 10)
                    
                    if referrer_id != user_id:
                        referrer = await hyoshcoder.read_user(referrer_id)
                        if referrer:
                            await hyoshcoder.set_referrer(user_id, referrer_id)
                            await hyoshcoder.add_points(
                                referrer_id, 
                                reward, 
                                "referral", 
                                f"Referral from {user_id}"
                            )
                            
                            # Notify referrer
                            cap = (
                                f"🎉 {user.mention} joined through your referral!\n"
                                f"You received {reward} {EMOJI['points']}"
                            )
                            await send_response(client, referrer_id, cap)
                except Exception as e:
                    logger.error(f"Referral error: {e}")

            # Handle points links
            if len(args) > 0 and args[0].startswith("points_"):
                try:
                    code = args[0][7:]
                    result = await hyoshcoder.claim_points_link(user_id, code)
                    if result["success"]:
                        await send_response(
                            client,
                            message.chat.id,
                            f"🎉 You claimed {result['points']} {EMOJI['points']}!\n"
                            f"Remaining claims: {result['remaining_claims']}",
                            delete_after=10
                        )
                    else:
                        await message.reply(f"{EMOJI['error']} {result['reason']}")
                except Exception as e:
                    logger.error(f"Points claim error: {e}")

            # Send start message
            await send_response(
                client,
                message.chat.id,
                Txt.START_TXT.format(user.mention),
                reply_markup=buttons,
                photo=img,
                animation=animation,
                delete_after=None  # Don't auto-delete start message
            )

        elif cmd in ["leaderboard", "lb"]:
            try:
                keyboard = get_leaderboard_keyboard()
                leaders = await hyoshcoder.get_leaderboard()
                
                if not leaders:
                    await send_response(
                        client,
                        message.chat.id,
                        "No leaderboard data available yet. Be the first to earn points!",
                        reply_markup=keyboard,
                        photo=img,
                        delete_after=120
                    )
                    return
                
                text = f"{EMOJI['leaderboard']} Weekly Points Leaderboard:\n\n"
                for i, user in enumerate(leaders[:10], 1):
                    username = user.get('username', f"User {user['_id']}")
                    text += (
                        f"{i}. {username} - "
                        f"{user.get('points', {}).get('balance', 0)} {EMOJI['points']} "
                        f"{EMOJI['premium'] if user.get('premium', {}).get('is_premium', False) else ''}\n"
                    )
                
                await send_response(
                    client,
                    message.chat.id,
                    text,
                    reply_markup=keyboard,
                    photo=img,
                    animation=animation,
                    delete_after=120
                )
                
            except Exception as e:
                logger.error(f"Leaderboard error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Couldn't load leaderboard. Please try again later.",
                    delete_after=15
                )

        elif cmd in ["mystats"]:
            try:
                stats = await hyoshcoder.get_user_file_stats(user_id)
                points = await hyoshcoder.get_points(user_id)
                premium_status = await hyoshcoder.check_premium_status(user_id)
                user_data = await hyoshcoder.read_user(user_id)
                referral_stats = user_data.get('referral', {})
                
                text = (
                    f"📊 <b>Your Statistics</b>\n\n"
                    f"{EMOJI['points']} <b>Points Balance:</b> {points}\n"
                    f"{EMOJI['premium']} <b>Premium Status:</b> {'Active ' + EMOJI['success'] if premium_status.get('is_premium', False) else 'Inactive ' + EMOJI['error']}\n"
                    f"{EMOJI['referral']} <b>Referrals:</b> {referral_stats.get('referred_count', 0)} "
                    f"(Earned {referral_stats.get('referral_earnings', 0)} {EMOJI['points']})\n\n"
                    f"{EMOJI['rename']} <b>Files Renamed</b>\n"
                    f"• Total: {stats.get('total_renamed', 0)}\n"
                    f"• Today: {stats.get('today', 0)}\n"
                    f"• This Week: {stats.get('this_week', 0)}\n"
                    f"• This Month: {stats.get('this_month', 0)}\n"
                )
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton(f"{EMOJI['leaderboard']} Leaderboard", callback_data="leaderboard")],
                    [InlineKeyboardButton(f"{EMOJI['referral']} Invite Friends", callback_data="invite")],
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
                
                await send_response(
                    client,
                    message.chat.id,
                    text,
                    reply_markup=buttons,
                    photo=img,
                    delete_after=90
                )
                
            except Exception as e:
                logger.error(f"Stats error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Couldn't load your stats. Please try again later.",
                    delete_after=15
                )

        elif cmd == "autorename":
            try:
                config = await hyoshcoder.get_config("points_config") or {}
                points_per_rename = config.get('per_rename', 2)
                current_points = await hyoshcoder.get_points(user_id)
                
                if len(args) < 1:
                    caption = (
                        f"{EMOJI['error']} <b>Please provide a rename template</b>\n\n"
                        "Example:\n"
                        "<code>/autorename MyFile_[episode]_[quality]</code>\n\n"
                        "Available placeholders:\n"
                        "[filename], [size], [duration], [date], [time]"
                    )
                    await send_response(client, message.chat.id, caption, delete_after=30)
                    return

                format_template = ' '.join(args)
                if len(format_template) > 200:
                    raise ValueError("Template too long (max 200 chars)")

                await hyoshcoder.set_format_template(user_id, format_template)
                
                caption = (
                    f"{EMOJI['success']} <b>Auto-rename template set!</b>\n\n"
                    f"📝 <b>Your template:</b> <code>{format_template}</code>\n\n"
                    "Now send me files to rename automatically!"
                )
                
                await send_response(client, message.chat.id, caption, delete_after=30)
                
            except ValueError as e:
                await send_response(client, message.chat.id, f"{EMOJI['error']} {str(e)}", delete_after=15)
            except Exception as e:
                logger.error(f"Autorename error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Failed to set rename template. Please try again.",
                    delete_after=15
                )

        elif cmd == "setmedia":
            keyboard = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{EMOJI['file']} Document", callback_data="setmedia_document")],
                [InlineKeyboardButton(f"{EMOJI['video']} Video", callback_data="setmedia_video")]
            ])
            caption = "**Please select the type of media you want to set:**"
            await send_response(
                client,
                message.chat.id,
                caption,
                reply_markup=keyboard,
                photo=img,
                delete_after=30
            )

        elif cmd == "set_caption":
            try:
                if len(args) == 0:
                    caption = (
                        "**Provide the caption\n\nExample : `/set_caption 📕Name ➠ : {filename} \n\n🔗 Size ➠ : {filesize} \n\n⏰ Duration ➠ : {duration}`**"
                    )
                    await send_response(client, message.chat.id, caption, delete_after=30)
                    return
                
                new_caption = ' '.join(args)
                if len(new_caption) > 500:
                    raise ValueError("Caption too long (max 500 chars)")
                
                await hyoshcoder.set_caption(user_id, caption=new_caption)
                caption = "**Your caption has been saved successfully ✅**"
                await send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=img,
                    delete_after=30
                )
                    
            except ValueError as e:
                await send_response(client, message.chat.id, f"{EMOJI['error']} {str(e)}", delete_after=15)
            except Exception as e:
                logger.error(f"Set caption error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Failed to save caption",
                    delete_after=15
                )

        elif cmd == "del_caption":
            old_caption = await hyoshcoder.get_caption(user_id)
            if not old_caption:
                caption = "**You don't have any caption ❌**"
                await send_response(client, message.chat.id, caption, delete_after=15)
                return
            
            await hyoshcoder.set_caption(user_id, caption=None)
            caption = "**Your caption has been successfully deleted 🗑️**"
            await send_response(
                client,
                message.chat.id,
                caption,
                photo=img,
                delete_after=30
            )

        elif cmd in ['see_caption', 'view_caption']:
            old_caption = await hyoshcoder.get_caption(user_id)
            if old_caption:
                caption = f"**Your caption:**\n\n`{old_caption}`"
            else:
                caption = "**You don't have any caption ❌**"
            await send_response(
                client,
                message.chat.id,
                caption,
                photo=img,
                delete_after=30
            )

        elif cmd in ['view_thumb', 'viewthumb']:
            thumb = await hyoshcoder.get_thumbnail(user_id)
            if thumb:
                await client.send_photo(chat_id=message.chat.id, photo=thumb)
            else:
                caption = "**You don't have any thumbnail ❌**"
                await send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=img,
                    delete_after=30
                )

        elif cmd in ['del_thumb', 'delthumb']:
            old_thumb = await hyoshcoder.get_thumbnail(user_id)
            if not old_thumb:
                caption = "No thumbnail is currently set."
                await send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=img,
                    delete_after=30
                )
                return

            await hyoshcoder.set_thumbnail(user_id, file_id=None)
            caption = "**Thumbnail successfully deleted 🗑️**"
            await send_response(
                client,
                message.chat.id,
                caption,
                photo=img,
                delete_after=30
            )

        elif cmd == "donate":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton(text="Back", callback_data="help"),
                 InlineKeyboardButton(text="Owner", url='https://t.me/hyoshassistantBot')]
            ])
            await send_response(
                client,
                message.chat.id,
                Txt.DONATE_TXT,
                reply_markup=buttons,
                photo=img,
                delete_after=300
            )

        elif cmd == "premium":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Owner", url="https://t.me/hyoshassistantBot"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
            await send_response(
                client,
                message.chat.id,
                Txt.PREMIUM_TXT,
                reply_markup=buttons,
                photo=img,
                delete_after=300
            )

        elif cmd == "plan":
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay Your Subscription", url="https://t.me/hyoshassistantBot"),
                 InlineKeyboardButton("Close", callback_data="close")]
            ])
            await send_response(
                client,
                message.chat.id,
                Txt.PREPLANS_TXT,
                reply_markup=buttons,
                photo=img,
                delete_after=300
            )

        elif cmd == "bought":
            msg = await send_response(client, message.chat.id, "Hold on, I'm verifying...")
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
        
        elif cmd == "help":
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
        
            btn_seq_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            auto_rename_text = "Auto-Rename ✅" if auto_rename_status else "Auto-Rename ❌"
        
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("• Automatic renaming format •", callback_data='file_names')],
                [InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), 
                 InlineKeyboardButton('Caption •', callback_data='caption')],
                [InlineKeyboardButton('• Metadata', callback_data='meta'), 
                 InlineKeyboardButton('Set Media •', callback_data='setmedia')],
                [InlineKeyboardButton('• Set Dump', callback_data='setdump'), 
                 InlineKeyboardButton('View Dump •', callback_data='viewdump')],
                [InlineKeyboardButton(f'• {btn_seq_text}', callback_data='sequential'), 
                 InlineKeyboardButton('Premium •', callback_data='premiumx')],
                [InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toggle_src'),
                 InlineKeyboardButton(f'• {auto_rename_text}', callback_data='toggle_auto_rename')],
                [InlineKeyboardButton('• Home', callback_data='home')]
            ])
            
            await send_response(
                client,
                message.chat.id,
                Txt.HELP_TXT.format(client.mention),
                reply_markup=buttons,
                photo=img,
                delete_after=None  # Don't auto-delete help message
            )
        
        elif cmd == "set_dump":
            if len(args) == 0:
                caption = "Please enter the dump channel ID after the command.\nExample: `/set_dump -1001234567890`"
                await send_response(client, message.chat.id, caption, delete_after=30)
            else:
                channel_id = args[0]
                try:
                    channel_info = await client.get_chat(channel_id)
                    if channel_info:
                        await hyoshcoder.set_user_channel(user_id, channel_id)
                        caption = f"**Channel {channel_id} has been set as the dump channel.**"
                        await send_response(
                            client,
                            message.chat.id,
                            caption,
                            delete_after=30
                        )
                    else:
                        caption = "The specified channel doesn't exist or is not accessible.\nMake sure I'm an admin in the channel."
                        await send_response(
                            client,
                            message.chat.id,
                            caption,
                            delete_after=30
                        )
                except Exception as e:
                    caption = f"Error: {e}. Please enter a valid channel ID.\nExample: `/set_dump -1001234567890`"
                    await send_response(
                        client,
                        message.chat.id,
                        caption,
                        delete_after=30
                    )
        
        elif cmd in ["view_dump", "viewdump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                caption = f"**Channel {channel_id} is currently set as the dump channel.**"
            else:
                caption = "**No dump channel is currently set.**"
            await send_response(
                client,
                message.chat.id,
                caption,
                delete_after=30
            )
        
        elif cmd in ["del_dump", "deldump"]:
            channel_id = await hyoshcoder.get_user_channel(user_id)
            if channel_id:
                await hyoshcoder.set_user_channel(user_id, None)
                caption = f"**Channel {channel_id} has been removed from the dump list.**"
            else:
                caption = "**No dump channel is currently set.**"
            await send_response(
                client,
                message.chat.id,
                caption,
                delete_after=30
            )
        
        elif cmd == "profile":
            try:
                user_id = await hyoshcoder.read_user(user_id)
                if not user:
                    raise ValueError("User not found")
                
                caption = (
                    f"**User Profile**\n\n"
                    f"👤 Username: @{message.from_user.username}\n"
                    f"🆔 ID: <code>{user_id}</code>\n"
                    f"📝 First Name: {message.from_user.first_name}\n"
                    f"✨ Points: {user.get('points', {}).get('balance', 0)}\n"
                    f"⭐ Premium: {'Yes' if user.get('premium', {}).get('is_premium', False) else 'No'}\n"
                    f"📅 Member Since: {datetime.fromtimestamp(user.get('join_date', 0)).strftime('%Y-%m-%d')}"
                )
                await send_response(
                    client,
                    message.chat.id,
                    caption,
                    photo=img,
                    delete_after=60
                )
            except Exception as e:
                logger.error(f"Profile error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Couldn't load profile",
                    delete_after=15
                )

        elif cmd == "freepoints":
            try:
                config = await hyoshcoder.get_config("points_config") or {}
                ad_config = config.get('ad_watch', {})
                
                min_points = ad_config.get('min_points', 5)
                max_points = ad_config.get('max_points', 20)
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔗 Share Bot", callback_data="invite")],
                    [InlineKeyboardButton("💰 Watch Ad", callback_data="watch_ad")],
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
                
                caption = (
                    "**✨ Free Points System**\n\n"
                    "Earn points by helping grow our community:\n\n"
                    f"🔹 **Share Bot**: Get {config.get('referral_bonus', 10)} points per referral\n"
                    f"🔹 **Watch Ads**: Earn {min_points}-{max_points} points per ad\n\n"
                    f"💎 Premium members earn {config.get('premium_multiplier', 2)}x more points!"
                )
                
                await send_response(
                    client,
                    message.chat.id,
                    caption,
                    reply_markup=buttons,
                    photo=img,
                    delete_after=60
                )
            except Exception as e:
                logger.error(f"Free points error: {e}")
                await send_response(
                    client,
                    message.chat.id,
                    f"{EMOJI['error']} Couldn't load points info",
                    delete_after=15
                )

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Error in command {cmd}: {e}")
        await send_response(
            client,
            message.chat.id,
            f"{EMOJI['error']} An error occurred. Please try again later.",
            delete_after=15
        )

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

@Client.on_message(filters.private & (filters.document | filters.video))
async def handle_file_rename(client, message: Message):
    """Handle file renaming with points deduction"""
    try:
        user_id = message.from_user.id
        config = await hyoshcoder.get_config("points_config") or {}
        points_per_rename = config.get('per_rename', 2)
        current_points = await hyoshcoder.get_points(user_id)
        
        # Check premium status for unlimited renames
        premium_status = await hyoshcoder.check_premium_status(user_id)
        if premium_status.get('is_premium', False) and config.get('premium_unlimited_renames', True):
            points_per_rename = 0
        
        # Check auto-rename status
        auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
        if not auto_rename_status:
            return  # Skip processing if auto-rename is disabled
        
        if current_points < points_per_rename:
            msg = await send_response(
                client,
                message.chat.id,
                f"{EMOJI['error']} Insufficient points!\n"
                f"Each rename costs {points_per_rename} {EMOJI['points']}\n"
                f"Your balance: {current_points} {EMOJI['points']}\n\n"
                "Get more points with /freepoints",
                delete_after=30
            )
            return
        
        # Deduct points (if not premium with unlimited renames)
        if points_per_rename > 0:
            await hyoshcoder.deduct_points(user_id, points_per_rename, "file_rename")
        
        # Get user's rename template
        template = await hyoshcoder.get_format_template(user_id)
        if not template:
            # Refund points if no template set
            if points_per_rename > 0:
                await hyoshcoder.add_points(user_id, points_per_rename, "refund", "No rename template set")
            msg = await send_response(
                client,
                message.chat.id,
                f"{EMOJI['error']} No rename template set!\n"
                "Use /autorename to set your template first\n\n"
                f"{points_per_rename} points refunded" if points_per_rename > 0 else "",
                delete_after=30
            )
            return
        
        # Get file info
        if message.document:
            file = message.document
            file_type = "document"
        else:
            file = message.video
            file_type = "video"
        
        original_name = file.file_name
        file_size = file.file_size
        duration = getattr(file, "duration", 0)
        
        # Generate new filename using template
        new_name = template
        new_name = new_name.replace("[filename]", os.path.splitext(original_name)[0])
        new_name = new_name.replace("[size]", str(round(file_size / (1024 * 1024), 2)) + "MB")
        new_name = new_name.replace("[duration]", str(duration // 60) + "m" + str(duration % 60) + "s")
        new_name = new_name.replace("[date]", datetime.now().strftime("%Y-%m-%d"))
        new_name = new_name.replace("[time]", datetime.now().strftime("%H:%M"))
        
        # Add original extension
        ext = os.path.splitext(original_name)[1]
        new_name += ext
        
        # Track the rename
        await hyoshcoder.track_file_rename(user_id, original_name, new_name)
        
        # Send success message
        success_msg = await send_response(
            client,
            message.chat.id,
            f"{EMOJI['success']} <b>File renamed successfully!</b>\n\n"
            f"📝 <b>Original:</b> {original_name}\n"
            f"🆕 <b>New name:</b> {new_name}\n\n"
            f"{f'⏳ <b>Points deducted:</b> {points_per_rename} {EMOJI['points']}\n' if points_per_rename > 0 else ''}"
            f"💰 <b>Remaining balance:</b> {current_points - points_per_rename} {EMOJI['points']}",
            delete_after=30
        )
        
        # Send the renamed file back to user
        await client.send_document(
            chat_id=message.chat.id,
            document=file.file_id,
            file_name=new_name,
            caption=f"Renamed: {new_name}"
        )
        
    except Exception as e:
        logger.error(f"Error handling file rename: {e}")
        await send_response(
            client,
            message.chat.id,
            f"{EMOJI['error']} Error processing file",
            delete_after=15
        )
