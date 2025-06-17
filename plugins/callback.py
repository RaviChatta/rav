import random
import uuid
import asyncio
import time
import logging
import string
import secrets
from html import escape
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
from datetime import datetime
from collections import defaultdict
from pyrogram.errors import QueryIdInvalid, FloodWait, ChatWriteForbidden, BadRequest
from asyncio import create_task, sleep
from os import path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Emoji Constants
EMOJI = {
    'points': "✨",
    'premium': "⭐",
    'referral': "👥",
    'rename': "📝",
    'stats': "📊",
    'admin': "🛠️",
    'success': "✅",
    'error': "❌",
    'clock': "⏳",
    'link': "🔗",
    'money': "💰",
    'file': "📁",
    'video': "🎥"
}

# Button Styles
BTN_STYLE = {
    'small': {'width': 3, 'max_chars': 10},
    'medium': {'width': 2, 'max_chars': 15},
    'large': {'width': 1, 'max_chars': 20}
}

# Global state tracker
metadata_states = defaultdict(dict)
caption_states = defaultdict(dict)

METADATA_ON = [
    [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ ᴇɴᴀʙʟᴇᴅ •', callback_data='metadata_0'),
     InlineKeyboardButton('✅', callback_data='metadata_0')],
    [InlineKeyboardButton('• ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ •', callback_data='set_metadata'),
     InlineKeyboardButton('• ʙᴀᴄᴋ •', callback_data='help')]
]

METADATA_OFF = [
    [InlineKeyboardButton('• ᴍᴇᴛᴀᴅᴀᴛᴀ ᴅɪꜱᴀʙʟᴇᴅ •', callback_data='metadata_1'),
     InlineKeyboardButton('❌', callback_data='metadata_1')],
    [InlineKeyboardButton('• ꜱᴇᴛ ᴄᴜꜱᴛᴏᴍ ᴍᴇᴛᴀᴅᴀᴛᴀ •', callback_data='set_metadata'),
     InlineKeyboardButton('• ʙᴀᴄᴋ •', callback_data='help')]
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

async def safe_edit_media(message, media_type, media_file, caption, reply_markup):
    """Safely edit media messages with proper error handling"""
    try:
        if media_type == 'photo':
            media = InputMediaPhoto(media=media_file or await get_random_photo(), caption=caption)
        elif media_type == 'animation':
            media = InputMediaAnimation(media=media_file or await get_random_animation(), caption=caption)
        else:
            raise ValueError("Invalid media type")
        
        await message.edit_media(
            media=media,
            reply_markup=reply_markup
        )
        return True
    except Exception as e:
        logger.error(f"Error editing media: {e}")
        try:
            await message.edit_text(
                text=caption,
                reply_markup=reply_markup,
                disable_web_page_preview=True
            )
            return True
        except Exception as e:
            logger.error(f"Error editing text: {e}")
            return False

async def auto_delete_message(chat_id: int, message_id: int, delay: int = 30):
    """Automatically delete a message after a specified delay."""
    try:
        await asyncio.sleep(delay)
        await client.delete_messages(chat_id, message_id)
        logger.info(f"Successfully auto-deleted message {message_id} in chat {chat_id}")
    except FloodWait as e:
        logger.warning(f"FloodWait in auto_delete_message: waiting {e.value} seconds")
        await asyncio.sleep(e.value)
        await auto_delete_message(chat_id, message_id, delay)
    except Exception as e:
        logger.error(f"Error auto-deleting message {message_id} in chat {chat_id}: {e}")

async def is_valid_channel(client, chat_id):
    """Check if a channel is valid and accessible"""
    try:
        if chat_id is None:
            return False
        await client.get_chat(chat_id)
        return True
    except Exception:
        return False

async def cleanup_states():
    """Clean up expired states periodically"""
    while True:
        await asyncio.sleep(300)  # Clean every 5 minutes
        current_time = time.time()
        
        # Clean expired metadata states
        expired_meta = [uid for uid, state in metadata_states.items() 
                       if current_time - state.get('timestamp', 0) > 300]
        for uid in expired_meta:
            metadata_states.pop(uid, None)
            
        # Clean expired caption states
        expired_caption = [uid for uid, state in caption_states.items()
                          if current_time - state.get('timestamp', 0) > 300]
        for uid in expired_caption:
            caption_states.pop(uid, None)

# Start the cleanup task
create_task(cleanup_states())

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
                    f"✅ <b>Success!</b>\nMetadata set to:\n<code>{escape(message.text)}</code>",
                    reply_markup=InlineKeyboardMarkup(METADATA_ON if bool_meta else METADATA_OFF)
                )
                
            metadata_states.pop(user_id, None)
            return
            
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            metadata_states.pop(user_id, None)
            return
    
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
                    [InlineKeyboardButton("• ꜱᴇᴛ ᴄᴀᴘᴛɪᴏɴ •", callback_data="set_caption")],
                    [InlineKeyboardButton("• ʀᴇᴍᴏᴠᴇ ᴄᴀᴘᴛɪᴏɴ •", callback_data="remove_caption")],
                    [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"),
                     InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
                ])
                
                await message.reply(
                    f"✅ <b>Caption Updated Successfully!</b>\n\n"
                    f"📝 <b>Current Caption:</b>\n<code>{escape(current_caption) if current_caption else 'None'}</code>",
                    reply_markup=btn
                )
                
            caption_states.pop(user_id, None)
            return
            
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")
            caption_states.pop(user_id, None)
            return
            
    message.continue_propagation()

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        # Get common resources with error handling
        try:
            img = await get_random_photo()
            anim = await get_random_animation()
            thumb = await hyoshcoder.get_thumbnail(user_id) or img
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
            src_txt = "File name" if src_info == "file_name" else "File caption"
            btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"
        except Exception as e:
            logger.error(f"Error getting resources: {e}")
            await query.answer("❌ Error loading resources. Please try again.", show_alert=True)
            return

        response = None

        if data == "home":
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• ᴍʏ ᴄᴏᴍᴍᴀɴᴅꜱ •", callback_data='help'),
                    InlineKeyboardButton(f"{EMOJI['stats']} • ᴍʏ ꜱᴛᴀᴛꜱ •", callback_data='mystats')
                ],
                [
                    InlineKeyboardButton(f"{EMOJI['points']} • ᴇᴀʀɴ ᴘᴏɪɴᴛꜱ •", callback_data='freepoints'),
                    InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data='close')
                ]
            ])

            response = {
                'caption': Txt.START_TXT.format(query.from_user.mention),
                'reply_markup': btn,
                'animation': anim
            }

        elif data == "help":
            btn_seq_text = "ˢᵉᑫ✅" if sequential_status else "ˢᵉᑫ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
    
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ᴬᵁᵀᴼ", callback_data='file_names'),
                    InlineKeyboardButton("ᵀᴴᵁᴹᴮ", callback_data='thumbnail'),
                    InlineKeyboardButton("ᶜᴬᴾᵀᴵᴼᴺ", callback_data='caption')
                ],
                [
                    InlineKeyboardButton("ᴹᴱᵀᴬ", callback_data='meta'),
                    InlineKeyboardButton("ᴹᴱᴰᴵᴬ", callback_data='setmedia'),
                    InlineKeyboardButton("ᴰᵁᴹᴾ", callback_data='setdump')
                ],
                [
                    InlineKeyboardButton(btn_seq_text, callback_data='sequential'),
                    InlineKeyboardButton("ᴾᴿᴱᴹ", callback_data='premiumx'),
                    InlineKeyboardButton(f"ˢᴿᶜ: {src_txt}", callback_data='toggle_src')
                ],
                [
                    InlineKeyboardButton("ᴴᴼᴹᴱ", callback_data='home')
                ]
            ])

            response = {
                "caption": Txt.HELP_TXT.format(client.mention),
                "reply_markup": btn,
                "photo": img
            }

        elif data == "sequential":
            current_status = await hyoshcoder.get_sequential_mode(user_id)
            new_status = not current_status
            await hyoshcoder.set_sequential_mode(user_id, new_status)
            
            btn_seq_text = "ˢᵉᑫ✅" if new_status else "ˢᵉᑫ❌"
            src_txt = "File name" if await hyoshcoder.get_src_info(user_id) == "file_name" else "File caption"
            
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ᴬᵁᵀᴼ", callback_data='file_names'),
                    InlineKeyboardButton("ᵀᴴᵁᴹᴮ", callback_data='thumbnail'),
                    InlineKeyboardButton("ᶜᴬᴾᵀᴵᴼᴺ", callback_data='caption')
                ],
                [
                    InlineKeyboardButton("ᴹᴱᵀᴬ", callback_data='meta'),
                    InlineKeyboardButton("ᴹᴱᴰᴵᴬ", callback_data='setmedia'),
                    InlineKeyboardButton("ᴰᵁᴹᴾ", callback_data='setdump')
                ],
                [
                    InlineKeyboardButton(btn_seq_text, callback_data='sequential'),
                    InlineKeyboardButton("ᴾᴿᴱᴹ", callback_data='premiumx'),
                    InlineKeyboardButton(f"ˢᴿᶜ: {src_txt}", callback_data='toggle_src')
                ],
                [
                    InlineKeyboardButton("ᴴᴼᴹᴱ", callback_data='home')
                ]
            ])
            
            await query.message.edit_reply_markup(reply_markup=btn)
            await query.answer(f"Sequential mode {'enabled' if new_status else 'disabled'}")

        elif data == "toggle_src":
            current_src = await hyoshcoder.get_src_info(user_id)
            new_src = "file_caption" if current_src == "file_name" else "file_name"
            await hyoshcoder.set_src_info(user_id, new_src)
            
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            btn_seq_text = "ˢᵉᑫ✅" if sequential_status else "ˢᵉᑫ❌"
            src_txt = "File name" if new_src == "file_name" else "File caption"
            
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("ᴬᵁᵀᴼ", callback_data='file_names'),
                    InlineKeyboardButton("ᵀᴴᵁᴹᴮ", callback_data='thumbnail'),
                    InlineKeyboardButton("ᶜᴬᴾᵀᴵᴼᴺ", callback_data='caption')
                ],
                [
                    InlineKeyboardButton("ᴹᴱᵀᴬ", callback_data='meta'),
                    InlineKeyboardButton("ᴹᴱᴰᴵᴬ", callback_data='setmedia'),
                    InlineKeyboardButton("ᴰᵁᴹᴾ", callback_data='setdump')
                ],
                [
                    InlineKeyboardButton(btn_seq_text, callback_data='sequential'),
                    InlineKeyboardButton("ᴾᴿᴱᴹ", callback_data='premiumx'),
                    InlineKeyboardButton(f"ˢᴿᶜ: {src_txt}", callback_data='toggle_src')
                ],
                [
                    InlineKeyboardButton("ᴴᴼᴹᴱ", callback_data='home')
                ]
            ])
            
            await query.message.edit_reply_markup(reply_markup=btn)
            await query.answer(f"Source changed to {src_txt}")

        elif data == "mystats":
            try:
                stats = await hyoshcoder.get_user_file_stats(user_id) or {
                    'total_renamed': 0,
                    'today': 0,
                    'this_week': 0,
                    'this_month': 0
                }
                
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
                    [InlineKeyboardButton(" • ʙᴀᴄᴋ •", callback_data="help")]
                ])
                
                response = {
                    'caption': text,
                    'reply_markup': btn,
                    'photo': img
                }
            
            except Exception as e:
                logger.error(f"Error in mystats handler: {e}")
                response = {
                    'caption': "⚠️ Error loading statistics. Please try again later.",
                    'reply_markup': InlineKeyboardMarkup([
                        [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
                    ]),
                    'photo': img
                }

        elif data in ["meta", "metadata_0", "metadata_1"]:
            if data.startswith("metadata_"):
                new_status = data == "metadata_1"
                await hyoshcoder.set_metadata(user_id, new_status)
            
            bool_meta = await hyoshcoder.get_metadata(user_id)
            meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
            
            response = {
                'caption': f"<b>Current Metadata:</b>\n\n➜ <code>{escape(meta_code)}</code>",
                'reply_markup': InlineKeyboardMarkup(METADATA_ON if bool_meta else METADATA_OFF),
                'photo': img
            }

        elif data == "set_metadata":
            metadata_states[user_id] = {
                "waiting": True,
                "timestamp": time.time(),
                "original_msg": query.message.id
            }
            prompt = await query.message.edit_text(
                "📝 <b>Send new metadata text</b>\n\n"
                "Example: <code>@CulturedTeluguweeb</code>\n"
                f"Current: <code>{escape(await hyoshcoder.get_metadata_code(user_id) or 'None')}</code>\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("• ᴄᴀɴᴄᴇʟ •", callback_data="meta")]]
                )
            )
            
            )
            metadata_states[user_id]["prompt_id"] = prompt.id
            return

        elif data == "freepoints":
            try:
                user = await hyoshcoder.users.find_one({"_id": user_id})
                referral_code = user.get("referral_code") if user else secrets.token_hex(4)
                
                if not user or not referral_code:
                    referral_code = secrets.token_hex(4)
                    await hyoshcoder.users.update_one(
                        {"_id": user_id},
                        {"$set": {"referral_code": referral_code}},
                        upsert=True
                    )
                
                refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
                
                caption = (
                    "**🎯 Your Referral Link**\n\n"
                    f"Share this link to earn {settings.REFER_POINT_REWARD} points per referral:\n"
                    f"`{refer_link}`\n\n"
                    "💡 Use `/freepoints` for earning points via ads\n"
                    "💡 Use `/genpoints` to generate earning links\n\n"
                )
                
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
                ])
                
                response = {
                    'text': caption,
                    'reply_markup': buttons,
                    'disable_web_page_preview': True
                }
            
            except Exception as e:
                logger.error(f"Callback freepoints error: {e}")
                await query.answer("❌ Error loading referral info", show_alert=True)
                return

        elif data == "file_names":
            format_template = await hyoshcoder.get_format_template(user_id) or "Not set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"), 
                 InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            response = {
                'caption': Txt.FILE_NAME_TXT.format(format_template=format_template),
                'reply_markup': btn,
                'photo': img
            }

        elif data == "caption":
            current_caption = await hyoshcoder.get_caption(user_id) or "Not set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ꜱᴇᴛ ᴄᴀᴘᴛɪᴏɴ •", callback_data="set_caption")],
                [InlineKeyboardButton("• ʀᴇᴍᴏᴠᴇ ᴄᴀᴘᴛɪᴏɴ •", callback_data="remove_caption")],
                [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"),
                 InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            
            await safe_edit_media(
                query.message,
                'photo',
                img,
                f"📝 <b>Current Caption:</b>\n<code>{escape(current_caption)}</code>",
                btn
            )
            return

        elif data == "set_caption":
            caption_states[user_id] = {
                "waiting": True,
                "timestamp": time.time(),
                "original_msg": query.message.id
            }
            prompt = await query.message.edit_text(
                "📝 <b>Send new caption text</b>\n\n"
                "Example: <code>📕Name ➠ : {filename}\n🔗 Size ➠ : {filesize}\n⏰ Duration ➠ : {duration}</code>\n\n"
                f"Current: <code>{escape(await hyoshcoder.get_caption(user_id) or 'None')}</code>\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("• ᴄᴀɴᴄᴇʟ •", callback_data="caption")]]
                )
            )
            caption_states[user_id]["prompt_id"] = prompt.id
            return
        
        elif data == "remove_caption":
            await hyoshcoder.set_caption(user_id, None)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"), 
                 InlineKeyboardButton("Back", callback_data="help")]
            ])
            response = {
                'caption': "✅ Caption removed successfully!",
                'reply_markup': btn,
                'photo': img
            }
            await safe_edit_media(
                query.message,
                'photo',
                img,
                response['caption'],
                response['reply_markup']
            )
            return
        
        elif data == "setmedia":
            current_media = await hyoshcoder.get_media_preference(user_id)
            current_media_text = current_media.capitalize() if current_media else "Not set"
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• ᴠɪᴅᴇᴏ •", callback_data='setmedia_video'),
                    InlineKeyboardButton("• ᴅᴏᴄᴜᴍᴇɴᴛ •", callback_data='setmedia_document')
                ],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data='help')]
            ])
            
            await safe_edit_media(
                query.message,
                'photo',
                img,
                f"🎥 <b>Current Media Preference:</b> {current_media_text}",
                btn
            )
            return
        
        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            if media_type not in ['video', 'document']:
                await query.answer("Invalid media type selected", show_alert=True)
                return
        
            await hyoshcoder.set_media_preference(user_id, media_type)
            await query.answer(f"Media preference set to {media_type}", show_alert=True)
            
            current_media_text = media_type.capitalize()
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("• ᴠɪᴅᴇᴏ •", callback_data='setmedia_video'),
                    InlineKeyboardButton("• ᴅᴏᴄᴜᴍᴇɴᴛ •", callback_data='setmedia_document')
                ],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data='help')]
            ])
            
            await safe_edit_media(
                query.message,
                'photo',
                img,
                f"🎥 <b>Current Media Preference:</b> {current_media_text}",
                btn
            )
            return
                
        elif data == "setdump":
            current_dump = await hyoshcoder.get_user_channel(user_id)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Set Dump Channel", callback_data="setdump_instructions")],
                [InlineKeyboardButton("🗑️ Remove Dump Channel", callback_data="remove_dump")],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            
            await safe_edit_media(
                query.message,
                'photo',
                img,
                f"📤 <b>Current Dump Channel</b>: <code>{current_dump or 'Not set'}</code>",
                btn
            )
            return
        
        elif data == "setdump_instructions":
            await query.answer("ℹ️ Use /set_dump <channel_id> to configure dump channel.", show_alert=True)
            return
        
        elif data == "remove_dump":
            await hyoshcoder.set_user_channel(user_id, None)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            response = {
                'caption': "✅ Dump channel removed successfully.",
                'reply_markup': btn,
                'photo': img
            }
            await safe_edit_media(
                query.message,
                'photo',
                img,
                response['caption'],
                response['reply_markup']
            )
            return
        
        elif data == "premiumx":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ʙᴜʏ ᴘʀᴇᴍɪᴜᴍ •", callback_data="buy_premium")],
                [InlineKeyboardButton("• ᴘʀᴇᴍɪᴜᴍ ꜰᴇᴀᴛᴜʀᴇꜱ •", callback_data="premium_features")],
                [InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            response = {
                'caption': (
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
                ),
                'reply_markup': btn,
                'photo': img
            }
        
        elif data == "thumbnail":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴠɪᴇᴡ ᴛʜᴜᴍʙɴᴀɪʟ •", callback_data="showThumb")],
                [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"), 
                 InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            response = {
                'caption': Txt.THUMBNAIL_TXT,
                'reply_markup': btn,
                'photo': thumb
            }
        
        elif data == "showThumb":
            caption = "Here is your current thumbnail" if thumb else "No thumbnail set"
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("• ᴄʟᴏꜱᴇ •", callback_data="close"), 
                 InlineKeyboardButton("• ʙᴀᴄᴋ •", callback_data="help")]
            ])
            response = {
                'caption': caption,
                'reply_markup': btn,
                'photo': thumb
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
                    if not await safe_edit_media(
                        query.message,
                        'photo',
                        response['photo'],
                        response['caption'],
                        response['reply_markup']
                    ):
                        await query.message.edit_text(
                            text=response['caption'],
                            reply_markup=response['reply_markup'],
                            disable_web_page_preview=True
                        )
                elif 'animation' in response:
                    await safe_edit_media(
                        query.message,
                        'animation',
                        response['animation'],
                        response['caption'],
                        response['reply_markup']
                    )
                elif 'text' in response:
                    await query.message.edit_text(
                        text=response['text'],
                        reply_markup=response['reply_markup'],
                        disable_web_page_preview=response.get('disable_web_page_preview', True)
                    )
                else:
                    await query.message.edit_text(
                        text=response.get('caption', ''),
                        reply_markup=response['reply_markup'],
                        disable_web_page_preview=True
                    )
            except FloodWait as e:
                await asyncio.sleep(e.value)
                return await cb_handler(client, query)
            except BadRequest as e:
                logger.error(f"BadRequest: {e}")
            except Exception as e:
                logger.error(f"Error sending response: {e}")
        
        # Answer the callback query
        try:
            await query.answer()
        except QueryIdInvalid:
            logger.warning("Query ID was invalid or expired")
        except Exception as e:
            logger.error(f"Error answering callback: {e}")

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await cb_handler(client, query)
    except Exception as e:
        logger.error(f"Callback handler error: {e}", exc_info=True)
        try:
            await query.answer("❌ An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass
