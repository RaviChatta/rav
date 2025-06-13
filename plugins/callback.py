import random
import uuid
import asyncio
import time
import logging
import string
import secrets
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
from pyrogram.errors import QueryIdInvalid, FloodWait, ChatWriteForbidden
from asyncio import create_task, sleep

logger = logging.getLogger(__name__)
ADMIN_USER_ID = settings.ADMIN

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
    [InlineKeyboardButton('Metadata Enabled', callback_data='metadata_0'),
     InlineKeyboardButton('✅', callback_data='metadata_0')],
    [InlineKeyboardButton('Set Custom Metadata', callback_data='set_metadata'),
     InlineKeyboardButton('Back', callback_data='help')]
]

METADATA_OFF = [
    [InlineKeyboardButton('Metadata Disabled', callback_data='metadata_1'),
     InlineKeyboardButton('❌', callback_data='metadata_1')],
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
                [InlineKeyboardButton(f"{EMOJI['stats']} My Stats", callback_data='mystats')],
                [InlineKeyboardButton(f"{EMOJI['points']} Earn Points", callback_data='freepoints')],
                [InlineKeyboardButton("❌ Close", callback_data='close')]
            ])

            response = {
                'caption': Txt.START_TXT.format(query.from_user.mention),
                'reply_markup': btn,
                'animation': anim
            }

        elif data == "help":
       
            # Get user-specific settings
            sequential_status = await hyoshcoder.get_sequential_mode(user_id)
            src_info = await hyoshcoder.get_src_info(user_id)
    
            btn_seq_text = "ˢᵉᑫ✅" if sequential_status else "ˢᵉᑫ❌"
            src_txt = "File name" if src_info == "file_name" else "File caption"
    
            # Build dynamic keyboard
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
            # Toggle sequential mode
            current_status = await hyoshcoder.get_sequential_mode(user_id)
            new_status = not current_status
            await hyoshcoder.set_sequential_mode(user_id, new_status)
            
            # Update the button text in the help menu
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
            # Toggle between file name and file caption as source
            current_src = await hyoshcoder.get_src_info(user_id)
            new_src = "file_caption" if current_src == "file_name" else "file_name"
            await hyoshcoder.set_src_info(user_id, new_src)
            
            # Update the button text in the help menu
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
                # Get user stats with proper date handling
                stats = await hyoshcoder.get_user_file_stats(user_id)
                points = await hyoshcoder.get_points(user_id)
                premium_status = await hyoshcoder.check_premium_status(user_id)
                user_data = await hyoshcoder.read_user(user_id)
                referral_stats = user_data.get('referral', {})
                
                # Ensure we have default values if stats are None
                if stats is None:
                    stats = {
                        'total_renamed': 0,
                        'today': 0,
                        'this_week': 0,
                        'this_month': 0
                    }
                else:
                    # Convert any integer timestamps to proper datetime objects
                    if isinstance(stats.get('last_updated'), int):
                        stats['last_updated'] = datetime.fromtimestamp(stats['last_updated'])
                
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
                    
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
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
                        [InlineKeyboardButton("🔙 Back", callback_data="help")]
                    ]),
                    'photo': img
                }

        elif data in ["meta", "metadata_0", "metadata_1"]:
            if data.startswith("metadata_"):
                # Toggle the metadata status
                new_status = data == "metadata_1"
                await hyoshcoder.set_metadata(user_id, new_status)
            
            bool_meta = await hyoshcoder.get_metadata(user_id)
            meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
            
            response = {
                'caption': f"<b>Current Metadata:</b>\n\n➜ {meta_code}",
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
                f"Current: {await hyoshcoder.get_metadata_code(user_id) or 'None'}\n\n"
                "Reply with text or /cancel",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("❌ Cancel", callback_data="meta")]]
                )
            )
            metadata_states[user_id]["prompt_id"] = prompt.id
            return

        elif data == "freepoints":
            try:
                user = await hyoshcoder.users.find_one({"_id": user_id})
        
                # Generate referral code if not present
                if not user or not user.get("referral_code"):
                    referral_code = secrets.token_hex(4)
                    await hyoshcoder.users.update_one(
                        {"_id": user_id},
                        {"$set": {"referral_code": referral_code}},
                        upsert=True
                    )
                else:
                    referral_code = user["referral_code"]
        
                refer_link = f"https://t.me/{settings.BOT_USERNAME}?start=ref_{referral_code}"
        
                # Generate new point ID and deep link
                point_id = "".join(random.choices(string.ascii_uppercase + string.digits, k=settings.TOKEN_ID_LENGTH))
                deep_link = f"https://t.me/{settings.BOT_USERNAME}?start={point_id}"
        
                # Pick random shortener
                shortener = settings.get_random_shortener()
                short_url = await get_shortlink(
                    url=shortener["domain"],
                    api=shortener["api"],
                    link=deep_link
                )
        
                # Fallback to deep link if shortening failed
                if not isinstance(short_url, str) or not short_url.startswith(("http://", "https://")):
                    short_url = deep_link
        
                # Save points link to DB
                await hyoshcoder.create_point_link(user_id, point_id, settings.SHORTENER_POINT_REWARD)
        
                # Caption
                caption = (
                    "**🎁 Free Points Menu**\n\n"
                    "Earn points by:\n"
                    f"1. **Referring users** – `{refer_link}`\n"
                    f"   ➤ {settings.REFER_POINT_REWARD} points per referral\n"
                    f"2. **Watching sponsored links** –\n"
                    f"   ➤ {settings.SHORTENER_POINT_REWARD} points\n\n"
                    f"🎯 Your points link:\n`{short_url}`\n\n"
                    "⏱ Points are added automatically!\n\n"
                    f"⌛ This message will be deleted in {settings.AUTO_DELETE_TIME} seconds."
                )
        
                # Buttons
                buttons = InlineKeyboardMarkup([
                    [InlineKeyboardButton("🔙 Back", callback_data="help")]
                ])
        
                # Send message with auto-delete
                try:
                    img = await get_random_photo()
                    if img:
                        sent_msg = await query.message.edit_media(
                            media=InputMediaPhoto(media=img, caption=caption),
                            reply_markup=buttons
                        )
                    else:
                        sent_msg = await query.message.edit_text(
                            text=caption,
                            reply_markup=buttons,
                            disable_web_page_preview=True
                        )
                    
                    # Schedule auto-deletion
                    asyncio.create_task(auto_delete_message(
                        chat_id=query.message.chat.id,
                        message_id=sent_msg.id,
                        delay=settings.AUTO_DELETE_TIME
                    ))
        
                except Exception as e:
                    logger.error(f"Error sending free points message: {e}")
                    sent_msg = await query.message.edit_text(
                        text=caption,
                        reply_markup=buttons,
                        disable_web_page_preview=True
                    )
                    asyncio.create_task(auto_delete_message(
                        chat_id=query.message.chat.id,
                        message_id=sent_msg.id,
                        delay=settings.AUTO_DELETE_TIME
                    ))
        
            except Exception as e:
                logger.error(f"Callback freepoints error: {e}", exc_info=True)
                try:
                    await query.answer("❌ Error loading free points. Try again.", show_alert=True)
                except Exception:
                    pass

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
            
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(media=img, caption=f"📝 <b>Current Caption:</b>\n{current_caption}"),
                    reply_markup=btn
                )
            except Exception as e:
                logger.error(f"Error updating caption menu: {e}")
                await query.message.edit_text(
                    text=f"📝 <b>Current Caption:</b>\n{current_caption}",
                    reply_markup=btn
                )

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
            await query.message.edit_media(
                media=InputMediaPhoto(response['photo']),
                caption=response['caption'],
                reply_markup=response['reply_markup']
            )
        
        elif data == "setmedia":
            current_media = await hyoshcoder.get_media_preference(user_id)
            current_media_text = current_media.capitalize() if current_media else "Not set"
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎥 Video", callback_data='setmedia_video'),
                    InlineKeyboardButton("📁 Document", callback_data='setmedia_document')
                ],
                [InlineKeyboardButton("🔙 Back", callback_data='help")]
            ])
            
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(
                        media=img,
                        caption=f"🎥 <b>Current Media Preference:</b> {current_media_text}"
                    ),
                    reply_markup=btn
                )
            except Exception as e:
                logger.error(f"Error updating media settings menu: {e}")
                await query.message.edit_text(
                    text=f"🎥 <b>Current Media Preference:</b> {current_media_text}",
                    reply_markup=btn
                )
        
        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            if media_type not in ['video', 'document']:
                await query.answer("Invalid media type selected", show_alert=True)
                return
        
            await hyoshcoder.set_media_preference(user_id, media_type)
            await query.answer(f"Media preference set to {media_type}", show_alert=True)
            
            # Return to media menu
            current_media = media_type
            current_media_text = current_media.capitalize()
            btn = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🎥 Video", callback_data='setmedia_video'),
                    InlineKeyboardButton("📁 Document", callback_data='setmedia_document')
                ],
                [InlineKeyboardButton("🔙 Back", callback_data='help")]
            ])
            
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(
                        media=img,
                        caption=f"🎥 <b>Current Media Preference:</b> {current_media_text}"
                    ),
                    reply_markup=btn
                )
            except Exception as e:
                logger.error(f"Error updating media settings after change: {e}")
                await query.message.edit_text(
                    text=f"🎥 <b>Current Media Preference:</b> {current_media_text}",
                    reply_markup=btn
                )
                
        elif data == "setdump":
            current_dump = await hyoshcoder.get_user_channel(user_id)
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("📥 Set Dump Channel", callback_data="setdump_instructions")],
                [InlineKeyboardButton("🗑️ Remove Dump Channel", callback_data="remove_dump")],
                [InlineKeyboardButton("🔙 Back", callback_data="help")]
            ])
            
            try:
                await query.message.edit_media(
                    media=InputMediaPhoto(
                        media=img,
                        caption=f"📤 <b>Current Dump Channel</b>: <code>{current_dump or 'Not set'}</code>"
                    ),
                    reply_markup=btn
                )
            except Exception as e:
                logger.error(f"Error updating dump channel menu: {e}")
                await query.message.edit_text(
                    text=f"📤 <b>Current Dump Channel</b>: <code>{current_dump or 'Not set'}</code>",
                    reply_markup=btn
                )
        
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
            await query.message.edit_media(
                media=InputMediaPhoto(response['photo']),
                caption=response['caption'],
                reply_markup=response['reply_markup']
            )
        
        elif data == "premiumx":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("Buy Premium", callback_data="buy_premium")],
                [InlineKeyboardButton("Premium Features", callback_data="premium_features")],
                [InlineKeyboardButton("Back", callback_data="help")]
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
        
        # Answer the callback query
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
        try:
            await query.answer("❌ An error occurred. Please try again.", show_alert=True)
        except Exception:
            pass
