import random
import uuid
import asyncio
import logging
import html
import time
from urllib.parse import quote
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto
)
from typing import Optional, Dict, Any
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, Message
from pyrogram.errors import ChannelInvalid, ChannelPrivate, ChatAdminRequired, FloodWait, ChatWriteForbidden
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from collections import defaultdict
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)
ADMIN_USER_ID = settings.ADMIN
# Constants
#METADATA_TIMEOUT = 60  # seconds
POINT_RANGE = range(5, 21)  # 5-20 points
# Global state tracker
metadata_states: Dict[int, Dict[str, Any]] = {}
metadata_waiting = defaultdict(dict)
set_metadata_state = {}  # Global state tracker
METADATA_ON = [
    [InlineKeyboardButton('Metadata Enabled', callback_data='metadata_1'),
     InlineKeyboardButton('✅', callback_data='metadata_1')],
    [InlineKeyboardButton('Set Custom Metadata', callback_data='set_metadata'),
     InlineKeyboardButton('Back', callback_data='help')]
]

METADATA_OFF = [
    [InlineKeyboardButton('Metadata Disabled', callback_data='metadata_0'),
     InlineKeyboardButton('❌', callback_data='metadata_0')],
    [InlineKeyboardButton('Set Custom Metadata', callback_data='set_metadata'),
     InlineKeyboardButton('Back', callback_data='help')]
]
SHARE_MESSAGE = """
🚀 *Discover This Amazing Bot!* 🚀

I'm using this awesome file renaming bot with these features:
- Automatic file renaming
- Custom metadata editing
- Thumbnail customization
- Sequential file processing
- And much more!

Join me using this link: {invite_link}
"""

@Client.on_message(filters.private & filters.text & ~filters.command(['start']))
async def process_metadata_text(client, message: Message):
    user_id = message.from_user.id
    
    if user_id not in metadata_states:
        return
        
    try:
        if message.text.lower() == "/cancel":
            await message.reply("🚫 Metadata update cancelled", 
                            reply_markup=InlineKeyboardMarkup(
                                [[InlineKeyboardButton("Back to Metadata", callback_data="meta")]]
                            ))
        else:
            await hyoshcoder.set_metadata_code(user_id, message.text)
            bool_meta = await hyoshcoder.get_metadata(user_id)
            
            await message.reply(
                f"✅ <b>Success!</b>\nMetadata set to:\n<code>{message.text}</code>",
                reply_markup=InlineKeyboardMarkup(METADATA_ON if bool_meta else METADATA_OFF)
            )
            
        metadata_states.pop(user_id, None)
        
    except Exception as e:
        await message.reply(f"❌ Error: {str(e)}")
        metadata_states.pop(user_id, None)

async def cleanup_metadata_states():
    while True:
        await asyncio.sleep(300)  # Clean every 5 minutes
        current_time = time.time()
        expired = [uid for uid, state in metadata_states.items() 
                    if current_time - state.get('timestamp', 0) > 300]
        for uid in expired:
            metadata_states.pop(uid, None)

class CallbackActions:

    @staticmethod
    async def handle_help(client: Client, query: CallbackQuery, user_id: int):
        """Handle help menu callback"""
        try:
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
    
            buttons = [
                [
                    InlineKeyboardButton("AutoRename", callback_data='file_names'),
                    InlineKeyboardButton('Thumbnail', callback_data='thumbnail'),
                    InlineKeyboardButton('Caption', callback_data='caption')
                ],
                [
                    InlineKeyboardButton('Metadata', callback_data='meta'),
                    InlineKeyboardButton('Set Media', callback_data='setmedia'),
                    InlineKeyboardButton('Set Dump', callback_data='setdump')
                ],
                [
                    InlineKeyboardButton(btn_sec_text, callback_data='sequential'),
                    InlineKeyboardButton('Premium', callback_data='premiumx'),
                    InlineKeyboardButton(f'Source: {src_txt}', callback_data='toggle_src')
                ],
                [InlineKeyboardButton('• Home', callback_data='home')]
            ]
            return {
                'caption': Txt.HELP_TXT.format(client.mention),
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        except Exception as e:
            logger.error(f"Help menu error: {e}")
            return {
                'caption': "❌ Error loading help menu",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="home")]
                ])
            }

    @staticmethod
    async def handle_stats(client: Client, query: CallbackQuery, user_id: int):
        """Handle user stats callback"""
        try:
            stats = await hyoshcoder.get_user_file_stats(user_id)
            points = await hyoshcoder.get_points(user_id)
            premium_status = await hyoshcoder.check_premium_status(user_id)
            user_data = await hyoshcoder.read_user(user_id)
            
            # Handle referral stats safely
            referral_stats = user_data.get('referral', {})
            referred_count = referral_stats.get('referred_count', 0)
            referral_earnings = referral_stats.get('referral_earnings', 0)
            
            text = (
                f"📊 <b>Your Statistics</b>\n\n"
                f"✨ <b>Points Balance:</b> {points}\n"
                f"⭐ <b>Premium Status:</b> {'Active ✅' if premium_status.get('is_premium', False) else 'Inactive ❌'}\n"
                f"👥 <b>Referrals:</b> {referred_count} "
                f"(Earned {referral_earnings} ✨)\n\n"
                f"📝 <b>Files Renamed</b>\n"
                f"• Total: {stats.get('total_renamed', 0)}\n"
                f"• Today: {stats.get('today', 0)}\n"
                f"• This Week: {stats.get('this_week', 0)}\n"
                f"• This Month: {stats.get('this_month', 0)}\n"
            )
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🏆 Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton("👥 Invite Friends", callback_data="invite")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            return {
                'caption': text,
                'reply_markup': buttons
            }
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return {
                'caption': "❌ Failed to load statistics",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
            }

    @staticmethod
    def get_leaderboard_keyboard(selected_period: str = "weekly", selected_type: str = "points"):
        """Generate leaderboard navigation keyboard"""
        periods = {
            "daily": "⏳ Daily",
            "weekly": "📆 Weekly", 
            "monthly": "🗓 Monthly",
            "alltime": "🏆 All-Time"
        }
        types = {
            "points": "✨ Points",
            "renames": "📝 Files",
            "referrals": "👥 Referrals"
        }
        
        period_buttons = []
        for period, text in periods.items():
            if period == selected_period:
                period_buttons.append(InlineKeyboardButton(f"• {text} •", callback_data=f"lb_period_{period}"))
            else:
                period_buttons.append(InlineKeyboardButton(text, callback_data=f"lb_period_{period}"))
        
        type_buttons = []
        for lb_type, text in types.items():
            if lb_type == selected_type:
                type_buttons.append(InlineKeyboardButton(f"• {text} •", callback_data=f"lb_type_{lb_type}"))
            else:
                type_buttons.append(InlineKeyboardButton(text, callback_data=f"lb_type_{lb_type}"))
        
        return InlineKeyboardMarkup([
            period_buttons[:2],
            period_buttons[2:],
            type_buttons,
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])

    @staticmethod
    async def handle_leaderboard(client: Client, query: CallbackQuery, period: str = "weekly", type: str = "points"):
        """Handle leaderboard callback - showing top 8"""
        try:
            leaders = await hyoshcoder.get_leaderboard(period, type)
            if not leaders:
                return {
                    'caption': "📭 No leaderboard data available yet",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="help")]
                    ])
                }
            
            type_display = {
                "points": "Points",
                "renames": "Files Renamed",
                "referrals": "Referrals"
            }.get(type, "Points")
            
            period_display = {
                "daily": "Daily",
                "weekly": "Weekly",
                "monthly": "Monthly", 
                "alltime": "All-Time"
            }.get(period, "Weekly")
            
            text = f"🏆 {period_display} {type_display} Leaderboard (Top 8):\n\n"
            for i, user in enumerate(leaders[:8], 1):
                username = user.get('username', f"User {user['_id']}")
                value = user.get('value', 0)
                text += f"{i}. {username} - {value} {type_display} {'⭐' if user.get('is_premium', False) else ''}\n"
            
            return {
                'caption': text,
                'reply_markup': CallbackActions.get_leaderboard_keyboard(period, type)
            }
        except Exception as e:
            logger.error(f"Leaderboard error: {e}")
            return {
                'caption': "❌ Failed to load leaderboard",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
            }

    @staticmethod
    async def handle_free_points(client: Client, query: CallbackQuery, user_id: int):
        """Improved free points verification and distribution"""
        try:
            me = await client.get_me()
            unique_code = str(uuid.uuid4())[:8]
            invite_link = f"https://t.me/{me.username}?start=refer_{user_id}"
            
            # Get points configuration safely
            config = await hyoshcoder.get_config("points_config") or {}
            ad_config = config.get('ad_watch', {})
            min_points = ad_config.get('min_points', 5)
            max_points = ad_config.get('max_points', 20)
            referral_bonus = config.get('referral_bonus', 10)
            premium_multiplier = config.get('premium_multiplier', 2)
            
            # Generate random points
            points = random.randint(min_points, max_points)
            
            # Check if user is premium for multiplier
            premium_status = await hyoshcoder.check_premium_status(user_id)
            if premium_status.get('is_premium', False):
                points = int(points * premium_multiplier)
            
            # Track the points distribution
            if not await hyoshcoder.set_expend_points(user_id, points, unique_code):
                raise Exception("Failed to track points distribution")
            
            # Generate shareable links
            points_link = f"https://t.me/{me.username}?start=adds_{unique_code}"
            shortlink = await get_shortlink(
                settings.SHORTED_LINK, 
                settings.SHORTED_LINK_API, 
                points_link
            ) if all([settings.SHORTED_LINK, settings.SHORTED_LINK_API]) else points_link
            
            share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(SHARE_MESSAGE.format(invite_link=invite_link))}"
            
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Watch Ad", url=shortlink)],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            caption = (
                "**✨ Free Points System**\n\n"
                "Earn points by helping grow our community:\n\n"
                f"🔹 **Share Bot**: Get {referral_bonus} points per referral\n"
                f"🔹 **Watch Ads**: Earn {min_points}-{max_points} points per ad\n"
                f"⭐ **Premium Bonus**: {premium_multiplier}x points multiplier\n\n"
                f"🎁 You can earn up to {points} points right now!"
            )
            
            return {
                'caption': caption,
                'reply_markup': buttons
            }
        except Exception as e:
            logger.error(f"Free points error: {e}")
            return {
                'caption': "❌ Error processing request. Please try again later.",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
            }

    @staticmethod
    async def handle_set_media(client: Client, query: CallbackQuery, user_id: int):
        """Handle media preference setting"""
        try:
            current_pref = await hyoshcoder.get_media_preference(user_id)
            buttons = [
                [
                    InlineKeyboardButton("Video" + (" ✅" if current_pref == "video" else ""), 
                                      callback_data="setmedia_video"),
                    InlineKeyboardButton("Document" + (" ✅" if current_pref == "document" else ""), 
                                      callback_data="setmedia_document")
                ],
                [InlineKeyboardButton("Back", callback_data="help")]
            ]
            
            return {
                'caption': "📁 <b>Set Media Preference</b>\n\n"
                          "Choose how you want media files to be sent:",
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        except Exception as e:
            logger.error(f"Set media error: {e}")
            return {
                'caption': "❌ Error loading media settings",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="help")]
                ])
            }

    @staticmethod
    async def handle_set_dump(client: Client, query: CallbackQuery, user_id: int):
        """Handle dump channel setting"""
        try:
            current_dump = await hyoshcoder.get_user_channel(user_id)
            buttons = [
                [InlineKeyboardButton("Set Dump Channel", callback_data="setdump_channel")],
                [InlineKeyboardButton("Back", callback_data="help")]
            ]
            
            return {
                'caption': f"📤 <b>Current Dump Channel</b>: {current_dump or 'Not set'}\n\n"
                          "You can set a channel where renamed files will be automatically forwarded.",
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        except Exception as e:
            logger.error(f"Set dump error: {e}")
            return {
                'caption': "❌ Error loading dump settings",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("Back", callback_data="help")]
                ])
            }

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    """Main callback query handler with improved error handling"""
    data = query.data
    user_id = query.from_user.id
    
    try:
        # Always answer the callback first to prevent client-side issues
        await query.answer()
        
        response = None
        
        if data == "home":
            response = await CallbackActions.handle_home(client, query)
        
        elif data == "help":
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "mystats":
            response = await CallbackActions.handle_stats(client, query, user_id)
        
        elif data == "leaderboard":
            response = await CallbackActions.handle_leaderboard(client, query)
        
        elif data.startswith("lb_"):
            parts = data.split("_")
            if len(parts) == 3:
                period = parts[2] if parts[1] == "period" else "weekly"
                type = parts[2] if parts[1] == "type" else "points"
                
                await hyoshcoder.set_leaderboard_period(user_id, period)
                await hyoshcoder.set_leaderboard_type(user_id, type)
                
                response = await CallbackActions.handle_leaderboard(client, query, period, type)
        
        # Metadata toggle handler
        elif data in ["meta", "metadata_0", "metadata_1"]:
            if data.startswith("metadata_"):
                enable = data.endswith("_1")
                await hyoshcoder.set_metadata(user_id, enable)
            
            bool_meta = await hyoshcoder.get_metadata(user_id)
            meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
            
            await query.message.edit_text(
                f"<b>Current Metadata:</b>\n\n➜ {meta_code}",
                reply_markup=InlineKeyboardMarkup(METADATA_ON if bool_meta else METADATA_OFF)
            )
            await query.answer(f"Metadata {'enabled' if bool_meta else 'disabled'}")
            return
        
        elif data == "set_metadata":
            try:
                metadata_states[user_id] = {
                    "waiting": True,
                    "timestamp": time.time(),
                    "original_msg": query.message.id
                }
                
                prompt = await query.message.edit_text(
                    "📝 <b>Send new metadata text</b>\n\n"
                    "Example: <code>Lakshmi Ganapathi Films</code>\n"
                    f"Current: {await hyoshcoder.get_metadata_code(user_id) or 'None'}\n\n"
                    "Reply with text or /cancel",
                    reply_markup=InlineKeyboardMarkup(
                        [[InlineKeyboardButton("❌ Cancel", callback_data="meta")]]
                    )
                )
                
                metadata_states[user_id]["prompt_id"] = prompt.id
                return
                
            except Exception as e:
                metadata_states.pop(user_id, None)
                await query.answer(f"Error: {str(e)}", show_alert=True)
                return
        
        elif data == "freepoints":
            response = await CallbackActions.handle_free_points(client, query, user_id)
        
        elif data == "caption":
            buttons = [
                [InlineKeyboardButton("• Support", url='https://t.me/Raaaaavi'), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.CAPTION_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data.startswith("setmedia"):
            if "_" in data:
                media_type = data.split("_")[1]
                await hyoshcoder.set_media_preference(user_id, media_type)
                await query.answer(f"Media preference set to {media_type}")
                response = await CallbackActions.handle_set_media(client, query, user_id)
            else:
                response = await CallbackActions.handle_set_media(client, query, user_id)
        
        elif data == "setdump":
            response = await CallbackActions.handle_set_dump(client, query, user_id)
        
        elif data.startswith("setdump_channel"):
            # This would be handled by a message handler for /set_dump command
            await query.answer("Please use /set_dump command followed by channel ID", show_alert=True)
            return
        
        elif data == "file_names":
            format_template = await hyoshcoder.get_format_template(user_id) or "Not set"
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.FILE_NAME_TXT.format(format_template=format_template),
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "thumbnail":
            thumb = await hyoshcoder.get_thumbnail(user_id)
            buttons = [
                [InlineKeyboardButton("• View Thumbnail", callback_data="showThumb")],
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.THUMBNAIL_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons),
                'photo': thumb  # Changed from 'thumb' to 'photo' for clarity
            }
        
        elif data == "showThumb":
            thumb = await hyoshcoder.get_thumbnail(user_id)
            caption = "Here is your current thumbnail" if thumb else "No thumbnail set"
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': caption,
                'reply_markup': InlineKeyboardMarkup(buttons),
                'photo': thumb
            }
        
        elif data == "source":
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="home")]
            ]
            response = {
                'caption': Txt.SOURCE_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "premiumx":
            buttons = [
                [InlineKeyboardButton("• Free Points", callback_data="freepoints")],
                [InlineKeyboardButton("• Back", callback_data="help")]
            ]
            response = {
                'caption': Txt.PREMIUM_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
        elif data == "about":
            buttons = [
                [
                    InlineKeyboardButton("• Support", url='https://t.me/Raaaaavi'), 
                    InlineKeyboardButton("Commands •", callback_data="help")
                ],
                [
                    InlineKeyboardButton("• Developer", url='https://t.me/Raaaaavi'), 
                    InlineKeyboardButton("Network •", url='https://t.me/Raaaaavi')
                ],
                [InlineKeyboardButton("• Back •", callback_data="home")]
            ]
            response = {
                'caption': Txt.ABOUT_TXT,
                'reply_markup': InlineKeyboardMarkup(buttons),
                'disable_web_page_preview': True
            }
        
        elif data == "sequential":
            await hyoshcoder.toggle_sequential_mode(user_id)
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "toggle_src":
            await hyoshcoder.toggle_src_info(user_id)
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except Exception as e:
                logger.warning(f"Error deleting message: {e}")
            return
        
        else:
            await query.answer("Unknown callback", show_alert=True)
            return

        # Send response
        if response:
            try:
                if 'photo' in response:
                    # Handle media messages
                    if query.message.photo:
                        # Editing existing photo message
                        await query.message.edit_media(
                            media=InputMediaPhoto(
                                media=response['photo'] or await get_random_photo(),
                                caption=response['caption']
                            ),
                            reply_markup=response['reply_markup']
                        )
                    else:
                        # Converting text message to photo
                        await query.message.delete()
                        await client.send_photo(
                            chat_id=query.message.chat.id,
                            photo=response['photo'] or await get_random_photo(),
                            caption=response['caption'],
                            reply_markup=response['reply_markup']
                        )
                else:
                    # Handle text messages
                    await query.message.edit_text(
                        text=response.get('caption', response.get('text', '')),
                        reply_markup=response['reply_markup'],
                        disable_web_page_preview=response.get('disable_web_page_preview', False),
                        parse_mode=response.get('parse_mode', enums.ParseMode.HTML)
                    )
            except Exception as e:
                logger.error(f"Failed to update message: {e}")
                await query.answer("Failed to update - please try again", show_alert=True)
            
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb_handler(client, query)
    except ChatWriteForbidden:
        logger.warning(f"Can't write in chat with {user_id}")
        await query.answer("I don't have permission to send messages here", show_alert=True)
    except Exception as e:
        logger.error(f"Callback error: {e}", exc_info=True)
        try:
            await query.answer("❌ An error occurred", show_alert=True)
        except:
            pass

# Start the cleanup task
asyncio.create_task(cleanup_metadata_states())
