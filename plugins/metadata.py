import html
import logging
import asyncio
from typing import Dict, Optional
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from database.data import hyoshcoder
from config import settings
from scripts import Txt

logger = logging.getLogger(__name__)
METADATA_TIMEOUT = 60

class MetadataManager:
    def __init__(self):
        self.fields = {
            'title': ('set_title', 'get_title'),
            'author': ('set_author', 'get_author'),
            'artist': ('set_artist', 'get_artist'),
            'audio': ('set_audio', 'get_audio'),
            'subtitle': ('set_subtitle', 'get_subtitle'),
            'video': ('set_video', 'get_video'),
            'custom_code': ('set_metadata_code', 'get_metadata_code')
        }

    async def get_full_metadata(self, user_id: int) -> Dict:
        """Get complete metadata configuration"""
        return {
            'enabled': await hyoshcoder.get_metadata(user_id),
            **{field: await getattr(hyoshcoder, getter)(user_id) or ""
               for field, (_, getter) in self.fields.items()}
        }

    async def handle_metadata_command(self, message: Message):
        """Handle /metadata command with interactive keyboard"""
        user_id = message.from_user.id
        metadata = await self.get_full_metadata(user_id)
        
        keyboard = [
            [self._toggle_button(metadata['enabled'])],
            *[[self._field_button(field) for field in row] 
              for row in [['title', 'author'], ['artist', 'audio'], ['subtitle', 'video']]],
            [InlineKeyboardButton("Custom Code", callback_data="custom_metadata"),
             InlineKeyboardButton("Help", callback_data="meta_help")],
            [InlineKeyboardButton("Close", callback_data="close")]
        ]
        
        await message.reply_text(
            self._format_metadata(metadata),
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode=enums.ParseMode.HTML
        )

    def _toggle_button(self, enabled: bool) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            f"Status: {'ON' if enabled else 'OFF'}",
            callback_data=f"metadata_{int(not enabled)}"
        )

    def _field_button(self, field: str) -> InlineKeyboardButton:
        return InlineKeyboardButton(
            f"Edit {field.title()}",
            callback_data=f"edit_{field}"
        )

    def _format_metadata(self, metadata: Dict) -> str:
        return f"📝 <b>Metadata Settings</b>\n\n" + "\n".join(
            f"🔹 <b>{field.title()}:</b> <code>{html.escape(str(val))}</code>"
            for field, val in metadata.items()
        )

    async def handle_field_edit(self, client: Client, user_id: int, field: str, query: CallbackQuery):
        """Handle metadata field editing process"""
        await query.message.delete()
        current_value = (await self.get_full_metadata(user_id))[field]
        
        msg = await client.send_message(
            user_id,
            f"✏️ Editing {field.replace('_', ' ').title()}\n"
            f"Current: <code>{html.escape(current_value) or 'None'}</code>\n\n"
            f"Send new value (max 200 chars)\n"
            f"Timeout: {METADATA_TIMEOUT}s",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Cancel", callback_data="metadata_cancel")]])
        )
        
        try:
            response = await client.listen.Message(filters.text & filters.user(user_id), timeout=METADATA_TIMEOUT)
            await self._validate_and_save(field, user_id, response.text)
            await client.send_message(user_id, f"✅ {field.title()} updated!")
        except asyncio.TimeoutError:
            await client.send_message(user_id, "⏳ Edit timed out")
        except Exception as e:
            await client.send_message(user_id, f"❌ Error: {str(e)}")
        finally:
            await msg.delete()

    async def _validate_and_save(self, field: str, user_id: int, value: str):
        """Validate and save metadata field"""
        if len(value) > 200:
            raise ValueError("Max 200 characters allowed")
        setter = getattr(hyoshcoder, self.fields[field][0])
        await setter(user_id, value)

@Client.on_message(filters.command(["metadata", "settitle", "setauthor", "setartist",
                                  "setaudio", "setsubtitle", "setvideo", "setcode"]))
async def metadata_command_handler(client: Client, message: Message):
    manager = MetadataManager()
    cmd = message.command[0].lower()
    
    if cmd == "metadata":
        await manager.handle_metadata_command(message)
    else:
        field = cmd[3:]
        if len(message.command) < 2:
            return await message.reply(f"Please provide {field} value")
        
        try:
            await manager._validate_and_save(field, message.from_user.id, ' '.join(message.command[1:]))
            await message.reply(f"✅ {field.title()} updated!")
        except Exception as e:
            await message.reply(f"❌ Error: {str(e)}")

@Client.on_callback_query(filters.regex(r"^metadata_|edit_|custom_metadata|meta_help"))
async def metadata_callback_handler(client: Client, query: CallbackQuery):
    manager = MetadataManager()
    user_id = query.from_user.id
    data = query.data
    
    if data.startswith("metadata_"):
        new_state = data.split("_")[1] == '1'
        await hyoshcoder.set_metadata(user_id, new_state)
        await query.message.edit_reply_markup(
            InlineKeyboardMarkup(manager._get_updated_buttons(await manager.get_full_metadata(user_id)))
        )
    
    elif data.startswith("edit_"):
        await manager.handle_field_edit(client, user_id, data.split("_")[1], query)
    
    elif data == "custom_metadata":
        await handle_custom_code(client, manager, user_id, query)
    
    elif data == "meta_help":
        await query.message.edit_text(Txt.META_HELP_TXT)

async def handle_custom_code(client: Client, manager: MetadataManager, user_id: int, query: CallbackQuery):
    # Implementation similar to handle_field_edit but for custom code
    pass
