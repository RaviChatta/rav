import random
import uuid
import asyncio
import time
import logging
from pyrogram import Client, filters, enums
from pyrogram.types import (
    CallbackQuery, 
    InlineKeyboardMarkup, 
    InlineKeyboardButton, 
    InputMediaPhoto,
    InputMediaAnimation,
    Message
)
from urllib.parse import quote
from helpers.utils import get_random_photo, get_random_animation, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings
from collections import defaultdict
from threading import Lock
from datetime import datetime, timedelta
from pyrogram.errors import QueryIdInvalid, FloodWait
logger = logging.getLogger(__name__)
ADMIN_USER_ID = settings.ADMIN
      # Seconds to wait for DB operations
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

# Global state tracker
metadata_states = defaultdict(dict)
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
    
    # Check if user is in metadata state and the message isn't a command
    if user_id in metadata_states and not message.text.startswith('/'):
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
    else:
        # Let other handlers process the message
        message.continue_propagation()

async def cleanup_metadata_states():
    while True:
        await asyncio.sleep(300)  # Clean every 5 minutes
        current_time = time.time()
        expired = [uid for uid, state in metadata_states.items() 
                    if current_time - state.get('timestamp', 0) > 300]
        for uid in expired:
            metadata_states.pop(uid, None)
def get_leaderboard_keyboard(selected_period="weekly", selected_type="points"):
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


@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        # Get common resources
        img = await get_random_photo()
        anim = await get_random_animation()
        thumb = await hyoshcoder.get_thumbnail(user_id)
        sequential_status = await hyoshcoder.get_sequential_mode(user_id)
        src_info = await hyoshcoder.get_src_info(user_id)
        src_txt = "File name" if src_info == "file_name" else "File caption"
        btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
        response = None

        if data == "home":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("MY COMMANDS", callback_data='help')],
                [InlineKeyboardButton(f"{EMOJI['stats']} My Stats", callback_data='mystats'),
                 InlineKeyboardButton(f"{EMOJI['leaderboard']} Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton(f"{EMOJI['points']} Earn Points", callback_data='freepoints'),
                 InlineKeyboardButton(f"{EMOJI['premium']} Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("🆕 Updates", url='https://t.me/Raaaaavi'),
                 InlineKeyboardButton("🛟 Support", url='https://t.me/Raaaaavi')]
            ])
            response = {
                'caption': Txt.START_TXT.format(query.from_user.mention),
                'reply_markup': btn,
                'animation': img
            }

        elif data == "help":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("AutoRename", callback_data='file_names'),
                 InlineKeyboardButton('Thumbnail', callback_data='thumbnail'),
                 InlineKeyboardButton('Caption', callback_data='caption')],
                [InlineKeyboardButton('Metadata', callback_data='meta'),
                 InlineKeyboardButton('Set Media', callback_data='setmedia'),
                 InlineKeyboardButton('Set Dump', callback_data='setdump')],
                [InlineKeyboardButton(btn_sec_text, callback_data='sequential'),
                 InlineKeyboardButton('Premium', callback_data='premiumx'),
                 InlineKeyboardButton(f'Source: {src_txt}', callback_data='toggle_src')],
                [InlineKeyboardButton('Home', callback_data='home')]
            ])
            response = {
                'caption': Txt.HELP_TXT.format(client.mention),
                'reply_markup': btn,
                'photo': img
            }

        elif data == "mystats":
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
            
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton(f"{EMOJI['leaderboard']} Leaderboard", callback_data="leaderboard")],
                [InlineKeyboardButton(f"{EMOJI['referral']} Invite Friends", callback_data="invite")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            response = {
                'caption': text,
                'reply_markup': btn,
                'photo': img
            }

        elif data == "leaderboard":
            leaders = await hyoshcoder.get_leaderboard()
            if not leaders:
                response = {
                    'caption': "📭 No leaderboard data available yet",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="help")]
                    ]),
                    'photo': img
                }
            else:
                text = f"{EMOJI['leaderboard']} Weekly Points Leaderboard:\n\n"
                for i, user in enumerate(leaders[:10], 1):
                    username = user.get('username', f"User {user['_id']}")
                    text += f"{i}. {username} - {user.get('points', 0)} {EMOJI['points']} {'⭐' if user.get('premium', False) else ''}\n"
                
                response = {
                    'caption': text,
                    'reply_markup': get_leaderboard_keyboard(),
                    'photo': img
                }

        elif data == "freepoints":
            me = await client.get_me()
            unique_code = str(uuid.uuid4())[:8]
            invite_link = f"https://t.me/{me.username}?start=refer_{user_id}"
            points_link = f"https://t.me/{me.username}?start=adds_{unique_code}"
            shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, points_link)
            share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(SHARE_MESSAGE.format(invite_link=invite_link))}"
            
            points = random.randint(5, 20)
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Watch Ad", url=shortlink)],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            caption = (
                "**✨ Free Points System**\n\n"
                "Earn points by helping grow our community:\n\n"
                f"🔹 **Share Bot**: Get 10 points per referral\n"
                f"🔹 **Watch Ads**: Earn 5-20 points per ad\n"
                f"⭐ **Premium Bonus**: 2x points multiplier\n\n"
                f"🎁 You can earn up to {points} points right now!"
            )
            
            response = {
                'caption': caption,
                'reply_markup': btn,
                'photo': img
            }

        elif data in ["meta", "metadata_0", "metadata_1"]:
            if data.startswith("metadata_"):
                await hyoshcoder.set_metadata(user_id, data.endswith("_1"))
            
            bool_meta = await hyoshcoder.get_metadata(user_id)
            meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
            await query.message.edit_text(
                f"<b>Current Metadata:</b>\n\n➜ {meta_code}",
                reply_markup=InlineKeyboardMarkup(METADATA_ON if bool_meta else METADATA_OFF)
            )
            return

        elif data == "set_metadata":
            metadata_states[user_id] = {
                "waiting": True,
                "timestamp": time.time(),
                "original_msg": query.message.id
            }
            prompt = await query.message.edit_text(
                "📝 <b>Send new metadata text</b>\n\n"
                "Example: <code> CulturedTeluguweeb</code>\n"
                f"Current: {await hyoshcoder.get_metadata_code(user_id) or 'None'}\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Cancel", callback_data="meta")]]
                )
            )
            metadata_states[user_id]["prompt_id"] = prompt.id
            return

        elif data == "file_names":
            format_template = await hyoshcoder.get_format_template(user_id) or "Not set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close"), 
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': Txt.FILE_NAME_TXT.format(format_template=format_template),
                'reply_markup': btn,
                'photo': img
            }

        elif data == "setmedia":
            # Show only video and document options
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Video", callback_data='setmedia_video'),
                 InlineKeyboardButton("Document", callback_data='setmedia_document')],
                [InlineKeyboardButton("Back", callback_data='help')]
            ])
            current_media = await hyoshcoder.get_media_preference(user_id)
            response = {
                'caption': f"🎥 <b>Current Media Preference:</b> {current_media or 'Not set'}\n\n"
                          "Select the type of media you want to receive:",
                'reply_markup': btn,
                'photo': img
            }

        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            if media_type not in ['video', 'document']:
                await query.answer("Invalid media type selected", show_alert=True)
                return
                
            await hyoshcoder.set_media_preference(user_id, media_type)
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data='setmedia')]])
            response = {
                'caption': f"✅ <b>Media preference set to:</b> {media_type.capitalize()}",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "setdump":
            current_dump = await hyoshcoder.get_user_channel(user_id)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Set Dump Channel", callback_data="setdump_instructions")],
                [InlineKeyboardButton("Remove Dump Channel", callback_data="remove_dump")],
                [InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': f"📤 <b>Current Dump Channel</b>: {current_dump or 'Not set'}\n\n"
                          "You can set a channel where renamed files will be automatically forwarded.\n\n"
                          "To set a dump channel:\n"
                          "1. Add me to your channel as admin\n"
                          "2. Use /set_dump command followed by channel ID\n"
                          "(e.g., <code>/set_dump -100123456789</code>)",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "setdump_instructions":
            await query.answer("Please use /set_dump command followed by channel ID", show_alert=True)
            return

        elif data == "remove_dump":
            await hyoshcoder.set_user_channel(user_id, None)
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data='setdump')]])
            response = {
                'caption': "✅ Dump channel removed successfully",
                'reply_markup': btn,
                'photo': img
            }

        elif data in ["sequential", "toggle_src"]:
            if data == "sequential":
                await hyoshcoder.toggle_sequential_mode(user_id)
            else:
                await hyoshcoder.toggle_src_info(user_id)
            # Refresh the help menu
            await cb_handler(client, query)
            return
        elif data == "caption":
            current_caption = await hyoshcoder.get_caption(user_id) or "Not set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Set Caption", callback_data="set_caption")],
                [InlineKeyboardButton("Remove Caption", callback_data="remove_caption")],
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': f"📝 <b>Current Caption:</b>\n{current_caption}\n\n"
                          "You can set a custom caption that will be added to all your renamed files.",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "set_caption":
            metadata_states[user_id] = {
                "waiting": True,
                "type": "caption",
                "timestamp": time.time(),
                "original_msg": query.message.id
            }
            prompt = await query.message.edit_text(
                "📝 <b>Send your new caption</b>\n\n"
                "You can use HTML formatting and include:\n"
                "- {filename} - Original file name\n"
                "- {size} - File size\n"
                "- {duration} - For video/audio\n\n"
                f"Current caption: {await hyoshcoder.get_caption(user_id) or 'None'}\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="caption")]
                ])
            )
            metadata_states[user_id]["prompt_id"] = prompt.id
            return

        elif data == "remove_caption":
            await hyoshcoder.set_caption(user_id, None)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="caption")]
            ])
            response = {
                'caption': "✅ Caption removed successfully",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "premiumx":
            premium_status = await hyoshcoder.check_premium_status(user_id)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("Premium Benefits", callback_data="premium_benefits")],
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': Txt.PREMIUM_TXT.format(
                    status="ACTIVE ✅" if premium_status.get('is_premium', False) else "INACTIVE ❌",
                    expiry=premium_status.get('expiry_date', 'Not active')
                ),
                'reply_markup': btn,
                'photo': img
            }

        elif data == "premium_benefits":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="premiumx")]
            ])
            response = {
                'caption': Txt.PREMIUM_BENEFITS_TXT,
                'reply_markup': btn,
                'photo': img
            }

        elif data == "buy_premium":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("1 Month - 50₹", callback_data="premium_1month")],
                [InlineKeyboardButton("3 Months - 120₹", callback_data="premium_3months")],
                [InlineKeyboardButton("6 Months - 200₹", callback_data="premium_6months")],
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="premiumx")]
            ])
            response = {
                'caption': "💰 <b>Premium Plans</b>\n\n"
                          "Choose your premium plan to unlock exclusive features:",
                'reply_markup': btn,
                'photo': img
            }

        elif data.startswith("premium_"):
            plan = data.split("_")[1]
            prices = {
                "1week": "20₹",
                "1month": "60₹",
                "3months": "150₹"
            }
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Pay Now", url="https://yourpaymentlink.com")],
                [InlineKeyboardButton("Close", callback_data="close"),
                 InlineKeyboardButton("Back", callback_data="buy_premium")]
            ])
            response = {
                'caption': f"💳 <b>Payment for {plan} Premium Plan</b>\n\n"
                          f"Plan: {plan.replace('months', ' months').replace('month', ' month')}\n"
                          f"Price: {prices.get(plan, 'N/A')}\n\n"
                          "Click 'Pay Now' to complete your purchase",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "thumbnail":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("View Thumbnail", callback_data="showThumb")],
                [InlineKeyboardButton("Close", callback_data="close"), 
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': Txt.THUMBNAIL_TXT,
                'reply_markup': btn,
                'photo': thumb if thumb else img
            }

        elif data == "showThumb":
            caption = "Here is your current thumbnail" if thumb else "No thumbnail set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close"), 
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': caption,
                'reply_markup': btn,
                'photo': thumb if thumb else img
            }

        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except:
                pass
            return

        # Send response
# Send response
        if response:
            media = None
            if 'animation' in response:
                media = InputMediaAnimation(media=response['animation'], caption=response['caption'])
            elif 'photo' in response:
                media = InputMediaPhoto(media=response['photo'], caption=response['caption'])
            
            if media:
                if query.message.animation or query.message.photo:
                    await query.message.edit_media(media=media, reply_markup=response['reply_markup'])
                else:
                    await query.message.delete()
                    if 'animation' in response:
                        await client.send_animation(
                            chat_id=query.message.chat.id,
                            animation=response['animation'],
                            caption=response['caption'],
                            reply_markup=response['reply_markup']
                        )
                    else:
                        await client.send_photo(
                            chat_id=query.message.chat.id,
                            photo=response['photo'],
                            caption=response['caption'],
                            reply_markup=response['reply_markup']
                        )
            else:
                await query.message.edit_text(
                    text=response['caption'],
                    reply_markup=response['reply_markup'],
                    disable_web_page_preview=True
                )

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.answer("An error occurred", show_alert=True)

# Start cleanup task
asyncio.create_task(cleanup_metadata_states())
