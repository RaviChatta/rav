from database.data import hyoshcoder
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified, MessageDeleteForbidden
import asyncio
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Track metadata editing state
metadata_states: Dict[int, Dict] = {}

# Button layouts with improved structure
METADATA_BUTTONS = {
    True: [
        [InlineKeyboardButton('✅ Metadata Enabled', callback_data='disable_metadata')],
        [InlineKeyboardButton('✏️ Set Custom Metadata', callback_data='set_metadata')],
        [InlineKeyboardButton('🔙 Back', callback_data='help')]
    ],
    False: [
        [InlineKeyboardButton('❌ Metadata Disabled', callback_data='enable_metadata')],
        [InlineKeyboardButton('✏️ Set Custom Metadata', callback_data='set_metadata')],
        [InlineKeyboardButton('🔙 Back', callback_data='help')]
    ]
}

async def safe_edit_message(
    target: Message,
    text: str,
    reply_markup: Optional[InlineKeyboardMarkup] = None,
    **kwargs
) -> bool:
    """Safely edit a message with comprehensive error handling"""
    try:
        await target.edit_text(text, reply_markup=reply_markup, **kwargs)
        return True
    except MessageNotModified:
        logger.debug("Message not modified")
        return True
    except FloodWait as e:
        logger.warning(f"Flood wait: {e.value}s")
        await asyncio.sleep(e.value)
        return await safe_edit_message(target, text, reply_markup, **kwargs)
    except Exception as e:
        logger.error(f"Failed to edit message: {e}")
        return False

async def safe_delete_message(message: Message) -> bool:
    """Safely delete a message with error handling"""
    try:
        await message.delete()
        return True
    except MessageDeleteForbidden:
        logger.warning("No permission to delete message")
    except Exception as e:
        logger.error(f"Failed to delete message: {e}")
    return False

@Client.on_message(filters.command("metadata"))
async def metadata_command(client: Client, message: Message):
    """Handle /metadata command"""
    user_id = message.from_user.id
    try:
        bool_meta = await hyoshcoder.get_metadata(user_id)
        meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
        
        text = (
            "📝 <b>Metadata Settings</b>\n\n"
            f"• Status: {'Enabled ✅' if bool_meta else 'Disabled ❌'}\n"
            f"• Current Code: <code>{meta_code}</code>"
        )
        
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(METADATA_BUTTONS[bool_meta])
        )
    except Exception as e:
        logger.error(f"Metadata command error: {e}")
        await message.reply_text("❌ Failed to load metadata settings")

@Client.on_callback_query(filters.regex(r'^(enable|disable)_metadata$'))
async def toggle_metadata_callback(client: Client, query: CallbackQuery):
    """Handle metadata toggle callback"""
    user_id = query.from_user.id
    try:
        enable = query.data.startswith('enable')
        await hyoshcoder.set_metadata(user_id, enable)
        
        meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
        text = (
            "📝 <b>Metadata Settings</b>\n\n"
            f"• Status: {'Enabled ✅' if enable else 'Disabled ❌'}\n"
            f"• Current Code: <code>{meta_code}</code>"
        )
        
        await safe_edit_message(
            query.message,
            text,
            reply_markup=InlineKeyboardMarkup(METADATA_BUTTONS[enable])
        )
        await query.answer(f"Metadata {'enabled' if enable else 'disabled'}")
    except Exception as e:
        logger.error(f"Toggle metadata error: {e}")
        await query.answer("❌ Failed to update metadata", show_alert=True)

@Client.on_callback_query(filters.regex(r'^set_metadata$'))
async def set_metadata_callback(client: Client, query: CallbackQuery):
    """Handle set metadata callback"""
    user_id = query.from_user.id
    try:
        # Store state
        metadata_states[user_id] = {
            'message_id': query.message.id,
            'timestamp': time.time()
        }
        
        prompt_text = (
            "✏️ <b>Set Custom Metadata</b>\n\n"
            "Please send your new metadata text (or /cancel to abort):\n\n"
            f"Current: <code>{await hyoshcoder.get_metadata_code(user_id) or 'None'}</code>\n"
            "You have 2 minutes to respond."
        )
        
        if not await safe_edit_message(
            query.message,
            prompt_text,
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_metadata")]]
            )
        ):
            await query.answer("❌ Failed to update message", show_alert=True)
    except Exception as e:
        logger.error(f"Set metadata callback error: {e}")
        await query.answer("❌ Error processing request", show_alert=True)

@Client.on_message(filters.private & filters.text & ~filters.command(['start']))
async def handle_metadata_text(client: Client, message: Message):
    """Handle metadata text input"""
    user_id = message.from_user.id
    if user_id not in metadata_states:
        return
    
    try:
        if message.text.lower() == '/cancel':
            await message.reply("🚫 Metadata update cancelled")
            metadata_states.pop(user_id, None)
            return
            
        await hyoshcoder.set_metadata_code(user_id, message.text)
        bool_meta = await hyoshcoder.get_metadata(user_id)
        
        text = (
            "✅ <b>Metadata Updated</b>\n\n"
            f"New metadata: <code>{message.text}</code>\n\n"
            f"Status: {'Enabled ✅' if bool_meta else 'Disabled ❌'}"
        )
        
        await message.reply_text(
            text,
            reply_markup=InlineKeyboardMarkup(METADATA_BUTTONS[bool_meta])
        )
        
        # Cleanup
        metadata_states.pop(user_id, None)
        await safe_delete_message(message)
        
    except Exception as e:
        logger.error(f"Metadata text handler error: {e}")
        await message.reply_text("❌ Failed to update metadata")

@Client.on_callback_query(filters.regex(r'^cancel_metadata$'))
async def cancel_metadata_callback(client: Client, query: CallbackQuery):
    """Handle metadata cancellation"""
    user_id = query.from_user.id
    try:
        metadata_states.pop(user_id, None)
        bool_meta = await hyoshcoder.get_metadata(user_id)
        meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
        
        text = (
            "📝 <b>Metadata Settings</b>\n\n"
            f"• Status: {'Enabled ✅' if bool_meta else 'Disabled ❌'}\n"
            f"• Current Code: <code>{meta_code}</code>"
        )
        
        await safe_edit_message(
            query.message,
            text,
            reply_markup=InlineKeyboardMarkup(METADATA_BUTTONS[bool_meta])
        )
        await query.answer("Metadata update cancelled")
    except Exception as e:
        logger.error(f"Cancel metadata error: {e}")
        await query.answer("❌ Failed to cancel operation", show_alert=True)

async def cleanup_metadata_states():
    """Cleanup expired metadata states"""
    while True:
        await asyncio.sleep(300)  # Run every 5 minutes
        try:
            current_time = time.time()
            expired = [
                uid for uid, state in metadata_states.items()
                if current_time - state.get('timestamp', 0) > 120  # 2 minute timeout
            ]
            for uid in expired:
                metadata_states.pop(uid, None)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

# Start cleanup task when bot starts
async def startup():
    asyncio.create_task(cleanup_metadata_states())
