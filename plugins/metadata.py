import logging
import html
import asyncio
from typing import Optional
from pyrogram import Client, filters, enums
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from database.data import hyoshcoder
from config import settings
from scripts import Txt

logger = logging.getLogger(__name__)

# Constants
METADATA_TIMEOUT = 60  # seconds
METADATA_MAX_LENGTH = 200

class MetadataHandler:
    @staticmethod
    async def get_current_metadata_status(user_id: int) -> dict:
        """Get all current metadata settings for a user"""
        return {
            'enabled': await hyoshcoder.get_metadata(user_id),
            'title': await hyoshcoder.get_title(user_id),
            'author': await hyoshcoder.get_author(user_id),
            'artist': await hyoshcoder.get_artist(user_id),
            'audio': await hyoshcoder.get_audio(user_id),
            'subtitle': await hyoshcoder.get_subtitle(user_id),
            'video': await hyoshcoder.get_video(user_id),
            'custom_code': await hyoshcoder.get_metadata_code(user_id)
        }

    @staticmethod
    async def format_metadata_message(metadata: dict) -> str:
        """Format metadata information into a message"""
        return f"""
📝 <b>Metadata Settings</b>

🔹 <b>Status:</b> {'🟢 Enabled' if metadata['enabled'] else '🔴 Disabled'}
🔹 <b>Title:</b> <code>{html.escape(metadata['title']) if metadata['title'] else 'Not set'}</code>
🔹 <b>Author:</b> <code>{html.escape(metadata['author']) if metadata['author'] else 'Not set'}</code>
🔹 <b>Artist:</b> <code>{html.escape(metadata['artist']) if metadata['artist'] else 'Not set'}</code>
🔹 <b>Audio:</b> <code>{html.escape(metadata['audio']) if metadata['audio'] else 'Not set'}</code>
🔹 <b>Subtitle:</b> <code>{html.escape(metadata['subtitle']) if metadata['subtitle'] else 'Not set'}</code>
🔹 <b>Video:</b> <code>{html.escape(metadata['video']) if metadata['video'] else 'Not set'}</code>
🔹 <b>Custom Code:</b> <code>{html.escape(metadata['custom_code']) if metadata['custom_code'] else 'Not set'}</code>
"""

    @staticmethod
    def get_metadata_keyboard(metadata_enabled: bool) -> InlineKeyboardMarkup:
        """Generate metadata control keyboard"""
        return InlineKeyboardMarkup([
            [
                InlineKeyboardButton(
                    f"🟢 ON" if metadata_enabled else "🔴 OFF",
                    callback_data=f"metadata_{int(not metadata_enabled)}"
                )
            ],
            [
                InlineKeyboardButton("✏️ Edit Title", callback_data="edit_title"),
                InlineKeyboardButton("✏️ Edit Author", callback_data="edit_author")
            ],
            [
                InlineKeyboardButton("✏️ Edit Artist", callback_data="edit_artist"),
                InlineKeyboardButton("✏️ Edit Audio", callback_data="edit_audio")
            ],
            [
                InlineKeyboardButton("✏️ Edit Subtitle", callback_data="edit_subtitle"),
                InlineKeyboardButton("✏️ Edit Video", callback_data="edit_video")
            ],
            [
                InlineKeyboardButton("📝 Custom Code", callback_data="custom_metadata"),
                InlineKeyboardButton("ℹ️ Help", callback_data="meta_help")
            ],
            [InlineKeyboardButton("🔙 Back", callback_data="help")]
        ])

    @staticmethod
    async def handle_metadata_edit(
        client: Client,
        user_id: int,
        message: Message,
        field: str,
        command: str,
        example: str
    ) -> Optional[Message]:
        """Handle metadata field editing"""
        if len(message.command) == 1:
            return await message.reply_text(
                f"**Please provide the {field}\n\nExample: `/{command} {example}`**",
                parse_mode=enums.ParseMode.MARKDOWN
            )
        
        value = message.text.split(" ", 1)[1]
        if len(value) > METADATA_MAX_LENGTH:
            return await message.reply_text(
                f"❌ {field} too long (max {METADATA_MAX_LENGTH} characters)"
            )
        
        # Set the appropriate field based on command
        if command == "settitle":
            await hyoshcoder.set_title(user_id, value)
        elif command == "setauthor":
            await hyoshcoder.set_author(user_id, value)
        elif command == "setartist":
            await hyoshcoder.set_artist(user_id, value)
        elif command == "setaudio":
            await hyoshcoder.set_audio(user_id, value)
        elif command == "setsubtitle":
            await hyoshcoder.set_subtitle(user_id, value)
        elif command == "setvideo":
            await hyoshcoder.set_video(user_id, value)
        
        return await message.reply_text(f"✅ {field} saved successfully")

@Client.on_message(filters.command(["metadata", "settitle", "setauthor", "setartist", 
                                  "setaudio", "setsubtitle", "setvideo"]))
async def metadata_command_handler(client: Client, message: Message):
    user_id = message.from_user.id
    command = message.command[0].lower()
    
    try:
        if command == "metadata":
            metadata = await MetadataHandler.get_current_metadata_status(user_id)
            text = await MetadataHandler.format_metadata_message(metadata)
            reply_markup = MetadataHandler.get_metadata_keyboard(metadata['enabled'])
            
            await message.reply_text(
                text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        elif command == "settitle":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message, 
                "title", "settitle", "My Awesome Title"
            )
        
        elif command == "setauthor":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message,
                "author", "setauthor", "@MyChannel"
            )
        
        elif command == "setartist":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message,
                "artist", "setartist", "@ArtistName"
            )
        
        elif command == "setaudio":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message,
                "audio title", "setaudio", "Audio Track Name"
            )
        
        elif command == "setsubtitle":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message,
                "subtitle", "setsubtitle", "Subtitle Track"
            )
        
        elif command == "setvideo":
            await MetadataHandler.handle_metadata_edit(
                client, user_id, message,
                "video title", "setvideo", "Encoded by @MyChannel"
            )
    
    except Exception as e:
        logger.error(f"Metadata command error: {e}")
        await message.reply_text(
            "❌ An error occurred while processing your request",
            parse_mode=enums.ParseMode.HTML
        )

@Client.on_callback_query(filters.regex(r"^metadata_|edit_|custom_metadata|meta_help"))
async def metadata_callback_handler(client: Client, query: CallbackQuery):
    user_id = query.from_user.id
    data = query.data
    
    try:
        if data.startswith("metadata_"):
            # Toggle metadata status
            is_enabled = data.split("_")[1] == '1'
            await hyoshcoder.set_metadata(user_id, bool_meta=is_enabled)
            
            # Get updated metadata and refresh message
            metadata = await MetadataHandler.get_current_metadata_status(user_id)
            text = await MetadataHandler.format_metadata_message(metadata)
            reply_markup = MetadataHandler.get_metadata_keyboard(is_enabled)
            
            await query.message.edit_text(
                text,
                reply_markup=reply_markup,
                parse_mode=enums.ParseMode.HTML,
                disable_web_page_preview=True
            )
        
        elif data.startswith("edit_"):
            # Handle field editing
            field = data.split("_")[1]
            field_name = field.capitalize()
            
            await query.message.delete()
            
            # Ask user for new value
            request_msg = await client.send_message(
                chat_id=user_id,
                text=(
                    f"✏️ <b>Editing {field_name}</b>\n\n"
                    f"Current value: <code>{html.escape((await MetadataHandler.get_current_metadata_status(user_id))[field]) or 'Not set'}</code>\n\n"
                    f"📝 <b>Send new {field_name} value</b> (max {METADATA_MAX_LENGTH} characters)\n"
                    f"⏳ <i>Timeout: {METADATA_TIMEOUT} seconds</i>\n\n"
                    f"<b>Example:</b>\n<code>My {field_name} Value</code>"
                ),
                parse_mode=enums.ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data="metadata_cancel")]
                ])
            )
            
            try:
                response_msg = await client.listen.Message(
                    filters.text & filters.user(user_id),
                    timeout=METADATA_TIMEOUT
                )
                
                if len(response_msg.text) > METADATA_MAX_LENGTH:
                    raise ValueError(f"Maximum {METADATA_MAX_LENGTH} characters allowed")
                
                # Set the appropriate field
                if field == "title":
                    await hyoshcoder.set_title(user_id, response_msg.text)
                elif field == "author":
                    await hyoshcoder.set_author(user_id, response_msg.text)
                elif field == "artist":
                    await hyoshcoder.set_artist(user_id, response_msg.text)
                elif field == "audio":
                    await hyoshcoder.set_audio(user_id, response_msg.text)
                elif field == "subtitle":
                    await hyoshcoder.set_subtitle(user_id, response_msg.text)
                elif field == "video":
                    await hyoshcoder.set_video(user_id, response_msg.text)
                
                # Send confirmation
                await client.send_message(
                    chat_id=user_id,
                    text=f"✅ <b>{field_name} Updated!</b>\n\n<code>{html.escape(response_msg.text)}</code>",
                    parse_mode=enums.ParseMode.HTML
                )
                
                # Clean up
                await asyncio.sleep(3)
                await request_msg.delete()
                if response_msg:
                    await response_msg.delete()
                
            except asyncio.TimeoutError:
                await client.send_message(
                    chat_id=user_id,
                    text="⏳ <b>Timed out</b>\nEdit cancelled.",
                    parse_mode=enums.ParseMode.HTML
                )
            except Exception as e:
                await client.send_message(
                    chat_id=user_id,
                    text=f"❌ <b>Error:</b>\n{html.escape(str(e))}",
                    parse_mode=enums.ParseMode.HTML
                )
        
        elif data == "custom_metadata":
            # Handle custom metadata code editing
            await query.message.delete()
            current_meta = await hyoshcoder.get_metadata_code(user_id) or ""
            
            request_msg = await client.send_message(
                chat_id=user_id,
                text=(
                    "✏️ <b>Edit Custom Metadata Code</b>\n\n"
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
                        "✅ <b>Metadata Code Updated!</b>\n\n"
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
        
        elif data == "meta_help":
            # Show metadata help information
            await query.message.edit_text(
                text=Txt.META_TXT,
                disable_web_page_preview=True,
                reply_markup=InlineKeyboardMarkup([
                    [
                        InlineKeyboardButton("🔙 Back", callback_data="metadata_1"),
                        InlineKeyboardButton("❌ Close", callback_data="close")
                    ]
                ])
            )
    
    except Exception as e:
        logger.error(f"Metadata callback error: {e}")
        try:
            await query.answer("❌ An error occurred", show_alert=True)
        except:
            pass
