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
from pyrogram.errors import QueryIdInvalid, FloodWait, ChatWriteForbidden

logger = logging.getLogger(__name__)
ADMIN_USER_ID = settings.ADMIN

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
caption_states = defaultdict(dict)

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
async def process_text_states(client, message: Message):
    user_id = message.from_user.id
    
    # Handle metadata state
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
    
    # Handle caption state
    elif user_id in caption_states and not message.text.startswith('/'):
        try:
            if message.text.lower() == "/cancel":
                await message.reply("🚫 Caption update cancelled", 
                                reply_markup=InlineKeyboardMarkup(
                                    [[InlineKeyboardButton("Back to Caption", callback_data="caption")]]
                                ))
            else:
                await hyoshcoder.set_caption(user_id, message.text)
                current_caption = await hyoshcoder.get_caption(user_id)
                
                btn = InlineKeyboardMarkup([
                    [InlineKeyboardButton("Set Caption", callback_data="set_caption")],
                    [InlineKeyboardButton("Remove Caption", callback_data="remove_caption")],
                    [InlineKeyboardButton("Close", callback_data="close"),
                     InlineKeyboardButton("Back", callback_data="help")]
                ])
                
                await message.reply(
                    f"✅ <b>Caption Updated Successfully!</b>\n\n"
                    f"📝 <b>Current Caption:</b>\n{current_caption}",
                    reply_markup=btn
                )
                
            caption_states.pop(user_id, None)
            
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            caption_states.pop(user_id, None)
    else:
        message.continue_propagation()

async def cleanup_states():
    while True:
        await asyncio.sleep(300)
        current_time = time.time()
        
        # Clean metadata states
        expired_meta = [uid for uid, state in metadata_states.items() 
                       if current_time - state.get('timestamp', 0) > 300]
        for uid in expired_meta:
            metadata_states.pop(uid, None)
            
        # Clean caption states
        expired_caption = [uid for uid, state in caption_states.items()
                          if current_time - state.get('timestamp', 0) > 300]
        for uid in expired_caption:
            caption_states.pop(uid, None)

def get_leaderboard_keyboard(selected_period="weekly", selected_type="points"):
    periods = {
        "daily": "⏰ Daily",
        "weekly": "📆 Weekly",
        "monthly": "🗓 Monthly",
        "alltime": "🏅 All-Time"
    }

    types = {
        "points": "⭐ Points",
        "renames": "📁 Files",
        "referrals": "🎁 Referrals"
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
                [InlineKeyboardButton(f"{EMOJI['points']} Earn Points", callback_data='freepoints')],
                [InlineKeyboardButton("❌ Close", callback_data='close')]
            ])

            response = {
                'caption': Txt.START_TXT.format(query.from_user.mention),
                'reply_markup': btn,
                'animation': anim
            }

        elif data == "help":
            btn = InlineKeyboardMarkup([
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
            try:
                period = await hyoshcoder.get_leaderboard_period(user_id)
                lb_type = await hyoshcoder.get_leaderboard_type(user_id)
        
                emoji_map = {
                    "points": "⭐",
                    "renames": "📁",
                    "referrals": "🎁"
                }
                title_map = {
                    "points": "Points",
                    "renames": "Files Renamed",
                    "referrals": "Referrals"
                }
        
                emoji = emoji_map.get(lb_type, "⭐")
                title = title_map.get(lb_type, "Points")
        
                if lb_type == "referrals":
                    leaders = await hyoshcoder.get_referrals_leaderboard(period, limit=20)
                elif lb_type == "renames":
                    leaders = await hyoshcoder.get_renames_leaderboard(period, limit=20)
                else:
                    leaders_raw = await hyoshcoder.get_leaderboard(period, limit=20)
                    leaders = [{
                        'username': user.get('username', f"User {user['_id']}"),
                        'value': user.get('points', 0),
                        'is_premium': user.get('is_premium', False)
                    } for user in leaders_raw]
        
                if not leaders:
                    response = {
                        'caption': "📭 No leaderboard data available yet",
                        'reply_markup': InlineKeyboardMarkup([
                            [InlineKeyboardButton("🔙 Back", callback_data="help")]
                        ]),
                        'photo': img
                    }
                else:
                    period_name = {
                        "daily": "Daily",
                        "weekly": "Weekly",
                        "monthly": "Monthly",
                        "alltime": "All-Time"
                    }.get(period, period.capitalize())
        
                    text = f"🏆 **{period_name} Leaderboard - {emoji} {title}**\n\n"
                    for i, user in enumerate(leaders, 1):
                        premium_tag = " 💎" if user.get("is_premium") else ""
                        text += f"**{i}.** {user['username']} — `{user['value']}` {emoji}{premium_tag}\n"
        
                    response = {
                        'caption': text,
                        'reply_markup': get_leaderboard_keyboard(period, lb_type),
                        'photo': img
                    }
        
            except Exception as e:
                logger.error(f"Error in leaderboard handler: {e}")
                response = {
                    'caption': "⚠️ Error loading leaderboard data",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("🔙 Back", callback_data="help")]
                    ]),
                    'photo': img
                }


        # In callback.py - Update the freepoints section
        elif data == "freepoints":
            me = await client.get_me()
            me_username = me.username
            unique_code = str(uuid.uuid4())[:8]
            telegram_link = f"https://t.me/{me_username}?start=adds_{unique_code}"
            invite_link = f"https://t.me/{me_username}?start=refer_{user_id}"
            
            try:
                if settings.SHORTED_LINK and settings.SHORTED_LINK_API:
                    shortlink = await get_shortlink(settings.SHORTED_LINK, settings.SHORTED_LINK_API, telegram_link)
                else:
                    shortlink = telegram_link
            except Exception as e:
                logger.error(f"Shortlink error: {e}")
                shortlink = telegram_link
        
            point_map = [5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]
            points = random.choice(point_map)
            
            # Save the points offer
            await hyoshcoder.set_expend_points(user_id, points, unique_code)
            
            share_msg = (
                "I just discovered this amazing bot! 🚀\n"
                f"Join me using this link: {invite_link}\n"
                "Automatically rename files with this bot!\n"
                "FEATURES:\n"
                "- Auto-rename files\n"
                "- Add custom metadata\n"
                "- Choose your filename\n"
                "- Choose your album name\n"
                "- Choose your artist name\n"
                "- Choose your genre\n"
                "- Choose your movie year\n"
                "- Add custom thumbnails\n"
                "- Link a channel to send your videos\n"
                "And much more!\n"
                "You can earn points by signing up and using the bot!"
            )
            
            share_msg_encoded = f"https://t.me/share/url?url={quote(invite_link)}&text={quote(share_msg)}"
            
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔗 Share Bot", url=share_msg_encoded)],
                [InlineKeyboardButton("💰 Watch Ad", url=shortlink)],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            caption = (
                "**Free Points**\n\n"
                "You can earn points by:\n"
                f"1. Sharing the bot - Earn 10 points per referral\n"
                f"2. Watching ads - Earn {points} points now!\n\n"
                "Premium users get 2x points!"
            )
            
            # Edit the existing message instead of sending new one
            try:
                if query.message.animation:
                    await query.message.edit_media(
                        media=InputMediaAnimation(
                            media=await get_random_animation(),
                            caption=caption
                        ),
                        reply_markup=btn
                    )
                elif query.message.photo:
                    await query.message.edit_media(
                        media=InputMediaPhoto(
                            media=await get_random_photo(),
                            caption=caption
                        ),
                        reply_markup=btn
                    )
                else:
                    await query.message.edit_text(
                        text=caption,
                        reply_markup=btn,
                        disable_web_page_preview=True
                    )
            except Exception as e:
                logger.error(f"Error editing freepoints message: {e}")
                # Fallback to sending new message if edit fails
                await client.send_message(
                    chat_id=query.message.chat.id,
                    text=caption,
                    reply_markup=btn,
                    disable_web_page_preview=True
                )
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
            caption_states[user_id] = {
                "waiting": True,
                "timestamp": time.time(),
                "original_msg": query.message.id
            }
            prompt = await query.message.edit_text(
                "📝 <b>Send new caption text</b>\n\n"
                "Example: <code>📕Name ➠ : {filename}\n🔗 Size ➠ : {filesize}\n⏰ Duration ➠ : {duration}</code>\n\n"
                f"Current: {await hyoshcoder.get_caption(user_id) or 'None'}\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Cancel", callback_data="caption")]]
                )
            )
            caption_states[user_id]["prompt_id"] = prompt.id
            return

        elif data == "remove_caption":
            await hyoshcoder.set_caption(user_id, None)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Close", callback_data="close"), 
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': "✅ Caption removed successfully!",
                'reply_markup': btn,
                'photo': img
            }

        elif data == "setmedia":
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
                          "You can set a channel where renamed files will be automatically forwarded.",
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

        elif data == "premiumx":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("Premium Features", callback_data="premium_features")],
                [InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': "🌟 <b>Premium Membership</b>\n\n"
                          "Get access to exclusive features:\n"
                          "• 2x Points Multiplier\n"
                          "• Priority Processing\n"
                          "• No Ads\n"
                          "• Extended File Size Limits\n\n"
                          "Click below to learn more!",
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
                elif 'animation' in response:
                    await query.message.edit_media(
                        media=InputMediaAnimation(
                            media=response['animation'],
                            caption=response['caption']
                        ),
                        reply_markup=response['reply_markup']
                    )
                else:
                    await query.message.edit_text(
                        text=response.get('caption', response.get('text', '')),
                        reply_markup=response['reply_markup'],
                        disable_web_page_preview=True,
                        parse_mode=enums.ParseMode.HTML
                    )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                await cb_handler(client, query)
            except ChatWriteForbidden:
                logger.warning(f"Can't write in chat with {user_id}")
            except Exception as e:
                logger.error(f"Error updating message: {e}")

        # Answer the callback query at the end
        try:
            await query.answer()
        except QueryIdInvalid:
            logger.warning("Query ID was invalid or expired")
        except Exception as e:
            logger.error(f"Error answering callback: {e}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        await cb_handler(client, query)
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
