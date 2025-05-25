# rename.py (expanded with more features)
import os
import logging
import asyncio
from datetime import datetime
from typing import Dict, Optional, Union
from pyrogram import Client, filters
from pyrogram.types import Message
from database.data import hyoshcoder
from helpers.utils import progress_for_pyrogram, humanbytes
from config import settings
from scripts import Txt

logger = logging.getLogger(__name__)

class RenameHandler:
    def __init__(self):
        self.active_operations: Dict[int, bool] = {}
        self.emoji = {
            'file': "📁", 'video': "🎥", 'audio': "🎵",
            'success': "✅", 'error': "❌", 'progress': "⏳"
        }

    async def _cleanup_temp_files(self, *paths):
        """Clean up temporary files"""
        for path in paths:
            try:
                if path and os.path.exists(path):
                    os.remove(path)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

    async def process_rename(
        self, 
        client: Client, 
        message: Message, 
        new_name: str,
        deduct_points: bool = True
    ) -> Union[bool, str]:
        """Core rename operation with enhanced features"""
        user_id = message.from_user.id
        if user_id in self.active_operations:
            return "❗ You already have an active operation"
            
        self.active_operations[user_id] = True
        
        try:
            # File type detection
            if message.document:
                file = message.document
                file_type = "document"
            elif message.video:
                file = message.video
                file_type = "video"
            elif message.audio:
                file = message.audio
                file_type = "audio"
            else:
                return False

            original_name = getattr(file, "file_name", "unknown")
            file_size = file.file_size

            # Points handling
            if deduct_points:
                points_config = await hyoshcoder.get_config("points_config") or {}
                points_per_rename = points_config.get("per_rename", 2)
                premium_status = await hyoshcoder.check_premium_status(user_id)
                
                if not premium_status.get("is_premium", False):
                    current_points = await hyoshcoder.get_points(user_id)
                    if current_points < points_per_rename:
                        return f"❌ Insufficient points! Need {points_per_rename} points"
                    
                    await hyoshcoder.deduct_points(user_id, points_per_rename, "file_rename")

            # File operations
            temp_dir = f"downloads/{user_id}"
            os.makedirs(temp_dir, exist_ok=True)
            temp_path = f"{temp_dir}/{file.file_id}"

            processing_msg = await message.reply_text(
                f"{self.emoji['progress']} <b>Processing file...</b>\n"
                f"Original: <code>{original_name}</code>\n"
                f"New: <code>{new_name}</code>",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{message.id}")]
                ])
            )

            # Download with progress
            file_path = await client.download_media(
                message,
                file_name=temp_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", processing_msg, datetime.now().timestamp())
            )

            if not file_path:
                await processing_msg.edit_text("❌ Download failed")
                return False

            # Rename file
            new_path = os.path.join(temp_dir, new_name)
            os.rename(file_path, new_path)

            # Upload with progress
            await processing_msg.edit_text(f"{self.emoji['progress']} <b>Uploading renamed file...</b>")
            
            upload_method = {
                "document": client.send_document,
                "video": client.send_video,
                "audio": client.send_audio
            }[file_type]

            await upload_method(
                chat_id=user_id,
                file=new_path,
                file_name=new_name,
                progress=progress_for_pyrogram,
                progress_args=("Uploading...", processing_msg, datetime.now().timestamp())
            )

            # Track in database
            await hyoshcoder.track_file_rename(
                user_id=user_id,
                original_name=original_name,
                new_name=new_name,
                file_type=file_type,
                file_size=file_size
            )

            await processing_msg.delete()
            return True

        except Exception as e:
            logger.error(f"File processing error: {e}")
            return f"❌ Error: {str(e)}"
        finally:
            self.active_operations.pop(user_id, None)
            await self._cleanup_temp_files(file_path, new_path)

    async def handle_auto_rename(self, client: Client, message: Message):
        """Handle automatic renaming based on template"""
        user_id = message.from_user.id
        template = await hyoshcoder.get_format_template(user_id)
        
        if not template:
            return await message.reply(
                "No auto-rename template set!\n"
                "Use /autorename to set a template",
                quote=True
            )
            
        file = message.document or message.video or message.audio
        if not file:
            return

        original_name = getattr(file, "file_name", "unknown")
        ext = os.path.splitext(original_name)[1]
        
        # Enhanced template processing
        new_name = template
        if "[filename]" in template:
            base_name = os.path.splitext(original_name)[0]
            new_name = new_name.replace("[filename]", base_name)
        if "[ext]" in template:
            new_name = new_name.replace("[ext]", ext[1:] if ext else "")
        
        if not new_name.endswith(ext):
            new_name += ext

        result = await self.process_rename(client, message, new_name)
        if isinstance(result, str):
            await message.reply(result, quote=True)

    async def handle_manual_rename(self, client: Client, message: Message):
        """Handle manual rename command"""
        if len(message.text.split()) < 2:
            return await message.reply(
                "Please provide the new filename\n"
                "Example: <code>/rename New File Name.mp4</code>",
                quote=True
            )
            
        new_name = message.text.split(" ", 1)[1]
        result = await self.process_rename(client, message, new_name)
        if isinstance(result, str):
            await message.reply(result, quote=True)

rename_handler = RenameHandler()

@Client.on_message(filters.document | filters.video | filters.audio)
async def auto_rename(client: Client, message: Message):
    if await hyoshcoder.get_auto_rename_status(message.from_user.id):
        await rename_handler.handle_auto_rename(client, message)

@Client.on_message(filters.command("rename") & (filters.document | filters.video | filters.audio))
async def manual_rename(client: Client, message: Message):
    await rename_handler.handle_manual_rename(client, message)
