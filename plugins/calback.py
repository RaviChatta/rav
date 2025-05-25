import random
import uuid
import asyncio
import logging
import html
from urllib.parse import quote
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto
)
from typing import Optional, Dict
from pyrogram.errors import FloodWait, ChatWriteForbidden
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)

# Constants
METADATA_TIMEOUT = 60  # seconds
POINT_RANGE = range(5, 21)  # 5-20 points
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

class CallbackActions:
    @staticmethod
    async def handle_home(client: Client, query: CallbackQuery):
        """Handle home button callback"""
        buttons = [
            [InlineKeyboardButton("✨ My Commands ✨", callback_data='help')],
            [
                InlineKeyboardButton("💎 My Stats", callback_data='mystats'),
                InlineKeyboardButton("🏆 Leaderboard", callback_data='leaderboard')
            ],
            [
                InlineKeyboardButton("🆕 Updates", url='https://t.me/Raaaaavi'),
                InlineKeyboardButton("🛟 Support", url='https://t.me/Raaaaavi')
            ],
            [
                InlineKeyboardButton("📜 About", callback_data='about'),
                InlineKeyboardButton("🧑‍💻 Source", callback_data='source')
            ]
        ]
        
        return {
            'caption': Txt.START_TXT.format(query.from_user.mention),
            'reply_markup': InlineKeyboardMarkup(buttons)
        }

    @staticmethod
    async def handle_help(client: Client, query: CallbackQuery, user_id: int):
        """Handle help menu callback"""
        try:
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
            
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
            auto_rename_text = "Auto-Rename ✅" if auto_rename_status else "Auto-Rename ❌"

            buttons = [
                [InlineKeyboardButton("• Automatic Renaming Format •", callback_data='file_names')],
                [
                    InlineKeyboardButton('• Thumbnail', callback_data='thumbnail'), 
                    InlineKeyboardButton('Caption •', callback_data='caption')
                ],
                [
                    InlineKeyboardButton('• Metadata', callback_data='meta'), 
                    InlineKeyboardButton('Set Media •', callback_data='setmedia')
                ],
                [
                    InlineKeyboardButton('• Set Dump', callback_data='setdump'), 
                    InlineKeyboardButton('View Dump •', callback_data='viewdump')
                ],
                [
                    InlineKeyboardButton(f'• {btn_sec_text}', callback_data='sequential'), 
                    InlineKeyboardButton('Premium •', callback_data='premiumx')
                ],
                [
                    InlineKeyboardButton(f'• Extract from: {src_txt}', callback_data='toggle_src'),
                    InlineKeyboardButton(f'• {auto_rename_text}', callback_data='toggle_auto_rename')
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
    async def handle_metadata_toggle(client: Client, query: CallbackQuery, user_id: int, data: str):
        """Handle metadata toggle and customization"""
        try:
            if data.startswith("metadata_"):
                is_enabled = data.split("_")[1] == '1'
                await hyoshcoder.set_metadata(user_id, bool_meta=is_enabled)
                user_metadata = await hyoshcoder.get_metadata_code(user_id) or "Not set"
                
                buttons = [
                    [
                        InlineKeyboardButton(
                            f"🟢 ON" if is_enabled else "🔴 OFF",
                            callback_data=f"metadata_{int(not is_enabled)}"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "✏️ Edit Metadata Code",
                            callback_data="custom_metadata"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "🔙 Back to Settings",
                            callback_data="help"
                        )
                    ]
                ]
                
                return {
                    'text': (
                        f"📝 <b>Metadata Settings</b>\n\n"
                        f"<b>Status:</b> {'🟢 Enabled' if is_enabled else '🔴 Disabled'}\n"
                        f"<b>Current Code:</b>\n<code>{html.escape(user_metadata)}</code>\n\n"
                        f"<i>Metadata will be embedded in processed files</i>"
                    ),
                    'reply_markup': InlineKeyboardMarkup(buttons),
                    'parse_mode': enums.ParseMode.HTML
                }
            
            elif data == "custom_metadata":
                await query.message.delete()
                current_meta = await hyoshcoder.get_metadata_code(user_id) or ""
                
                request_msg = await client.send_message(
                    chat_id=user_id,
                    text=(
                        "<b>✏️ Edit Metadata Code</b>\n\n"
                        f"<b>Current:</b>\n<code>{html.escape(current_meta)}</code>\n\n"
                        "📝 <b>Send new metadata text</b> (max 200 characters)\n"
                        f"⏳ <i>Timeout: {METADATA_TIMEOUT} seconds</i>\n\n"
                        "<b>Example:</b>\n<code>Processed by @YourBot</code>"
                    ),
                    parse_mode=enums.ParseMode.HTML,
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("❌ Cancel", callback_data="metadata_cancel")]
                    ])
                )
                
                try:
                    metadata_msg = await client.listen.Message(
                        filters.text & filters.user(user_id),
                        timeout=METADATA_TIMEOUT
                    )
                    
                    if len(metadata_msg.text) > 200:
                        raise ValueError("Maximum 200 characters allowed")
                    
                    await hyoshcoder.set_metadata_code(user_id, metadata_msg.text)
                    
                    await client.send_message(
                        chat_id=user_id,
                        text=(
                            "✅ <b>Metadata Updated!</b>\n\n"
                            f"<code>{html.escape(metadata_msg.text)}</code>"
                        ),
                        parse_mode=enums.ParseMode.HTML
                    )
                    
                    await asyncio.sleep(3)
                    await request_msg.delete()
                    if metadata_msg:
                        await metadata_msg.delete()
                        
                except asyncio.TimeoutError:
                    await client.send_message(
                        chat_id=user_id,
                        text="⏳ <b>Timed out</b>\nMetadata update cancelled.",
                        parse_mode=enums.ParseMode.HTML
                    )
                except Exception as e:
                    await client.send_message(
                        chat_id=user_id,
                        text=f"❌ <b>Error:</b>\n{html.escape(str(e))}",
                        parse_mode=enums.ParseMode.HTML
                    )
                
                return None
                
        except Exception as e:
            logger.error(f"Metadata handler error: {e}", exc_info=True)
            return {
                'text': "❌ An error occurred while processing metadata settings",
                'reply_markup': InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ]),
                'parse_mode': enums.ParseMode.HTML
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
        
        elif data in ["metadata_1", "metadata_0", "custom_metadata"]:
            response = await CallbackActions.handle_metadata_toggle(client, query, user_id, data)
            if not response:
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
        
        elif data == "meta":
            buttons = [
                [InlineKeyboardButton("• Close", callback_data="close"), 
                 InlineKeyboardButton("Back •", callback_data="help")]
            ]
            response = {
                'caption': Txt.SEND_METADATA,
                'reply_markup': InlineKeyboardMarkup(buttons)
            }
        
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
                'photo': thumb
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
        
        elif data == "toggle_auto_rename":
            await hyoshcoder.toggle_auto_rename(user_id)
            response = await CallbackActions.handle_help(client, query, user_id)
        
        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except Exception as e:
                logger.warning(f"Error deleting message: {e}")
            return
        
        elif data.startswith("cancel_"):
            file_id = data.split("_", 1)[1]
            if file_id in renaming_operations:
                del renaming_operations[file_id]
            await query.message.edit_text("❌ Processing cancelled by user")
            return
        
        else:
            await query.answer("Unknown callback", show_alert=True)
            return

        # Send response
        if response:
            try:
                if 'photo' in response:
                    if query.message.photo:
                        await query.message.edit_media(
                            media=InputMediaPhoto(
                                media=response['photo'] or await get_random_photo(),
                                caption=response['caption']
                            ),
                            reply_markup=response['reply_markup']
                        )
                    else:
                        await query.message.delete()
                        await client.send_photo(
                            chat_id=query.message.chat.id,
                            photo=response['photo'] or await get_random_photo(),
                            caption=response['caption'],
                            reply_markup=response['reply_markup']
                        )
                else:
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
