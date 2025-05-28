import random
import uuid
import asyncio
import time
from pyrogram import Client, filters, enums
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, InputMediaPhoto, Message
from pyrogram.errors import FloodWait
from urllib.parse import quote
from helpers.utils import get_random_photo, get_shortlink
from scripts import Txt
from database.data import hyoshcoder
from config import settings
from collections import defaultdict

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

@Client.on_message(filters.private & filters.text & ~filters.command(['start']))
async def process_metadata_text(client: Client, message: Message):
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
        await asyncio.sleep(300)
        current_time = time.time()
        expired = [uid for uid, state in metadata_states.items() 
                  if current_time - state.get('timestamp', 0) > 300]
        for uid in expired:
            metadata_states.pop(uid, None)

@Client.on_callback_query()
async def cb_handler(client: Client, query: CallbackQuery):
    data = query.data
    user_id = query.from_user.id
    
    try:
        await query.answer()
        
        # Get common resources
        img = await get_random_photo()
        thumb = await hyoshcoder.get_thumbnail(user_id)
        sequential_status = await hyoshcoder.get_sequential_mode(user_id)
        src_info = await hyoshcoder.get_src_info(user_id)
        src_txt = "File name" if src_info == "file_name" else "File caption"
        btn_sec_text = "Sequential ✅" if sequential_status else "Sequential ❌"

        if data == "home":
            btn = InlineKeyboardMarkup([
                [InlineKeyboardButton("MY COMMANDS", callback_data='help')],
                [InlineKeyboardButton("My Stats", callback_data='mystats'),
                 InlineKeyboardButton("Leaderboard", callback_data='leaderboard')],
                [InlineKeyboardButton("Earn Points", callback_data='freepoints'),
                 InlineKeyboardButton("Go Premium", callback_data='premiumx')],
                [InlineKeyboardButton("Updates", url='https://t.me/Raaaaavi'),
                 InlineKeyboardButton("Support", url='https://t.me/Raaaaavi')]
            ])
            caption = Txt.START_TXT.format(query.from_user.mention)

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
            caption = Txt.HELP_TXT.format(client.mention)

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
                "Example: <code>Telegram : @REQUETE_ANIME_30sbot</code>\n"
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
            caption = Txt.FILE_NAME_TXT.format(format_template=format_template)

        elif data.startswith("setmedia_"):
            media_type = data.split("_")[1]
            await hyoshcoder.set_media_preference(user_id, media_type)
            btn = InlineKeyboardMarkup([[InlineKeyboardButton("Back", callback_data='help')]])
            caption = f"**Media preference set to:** {media_type} ✅"

        elif data in ["sequential", "toggle_src"]:
            if data == "sequential":
                await hyoshcoder.toggle_sequential_mode(user_id)
            else:
                await hyoshcoder.toggle_src_info(user_id)
            # Refresh the help menu
            response = await cb_handler(client, query)
            return

        elif data == "close":
            try:
                await query.message.delete()
                if query.message.reply_to_message:
                    await query.message.reply_to_message.delete()
            except:
                pass
            return

        # Edit message with response
        if data in ["showThumb", "thumbnail"] and thumb:
            media = InputMediaPhoto(media=thumb, caption=caption)
            await query.message.edit_media(media=media, reply_markup=btn)
        elif img:
            media = InputMediaPhoto(media=img, caption=caption)
            await query.message.edit_media(media=media, reply_markup=btn)
        else:
            await query.message.edit_text(text=caption, reply_markup=btn)

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        logger.error(f"Callback error: {e}")
        await query.answer("An error occurred", show_alert=True)

# Start cleanup task
asyncio.create_task(cleanup_metadata_states())
