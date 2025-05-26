import os
import re
import time
import uuid
import logging
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helpers.utils import (
    progress_for_pyrogram,
    humanbytes,
    extract_season,
    extract_episode,
    extract_quality,
    sanitize_filename
)
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)

# Global state management
renaming_operations: Dict[str, datetime] = {}
user_semaphores: Dict[int, asyncio.Semaphore] = {}
user_queue_messages: Dict[int, List[Message]] = {}

async def get_user_semaphore(user_id: int) -> asyncio.Semaphore:
    """Manage concurrent operations per user"""
    return user_semaphores.setdefault(user_id, asyncio.Semaphore(3))

async def process_file_rename(
    client: Client,
    message: Message,
    queue_message: Message,
    user_id: int
) -> Optional[Tuple[str, str]]:
    """Main file processing pipeline"""
    try:
        file, media_type = await _get_file_info(message)
        if not file:
            return None

        original_name = sanitize_filename(file.file_name)
        format_template = await _get_user_template(user_id)
        metadata_enabled = await hyoshcoder.get_metadata(user_id)

        # Download file
        file_path = await _download_file(
            client, message, queue_message, user_id, original_name
        )
        if not file_path:
            return None

        # Generate new filename
        new_name = _generate_filename(original_name, format_template)
        new_path = os.path.join("downloads", new_name)
        os.rename(file_path, new_path)

        # Apply metadata if enabled
        if metadata_enabled:
            metadata_code = await hyoshcoder.get_metadata_code(user_id) or ""
            new_path = await _apply_metadata(new_path, new_name, metadata_code)

        return new_path, new_name

    except Exception as e:
        logger.error(f"Processing error: {e}")
        await queue_message.edit_text(f"❌ Error: {str(e)}")
        return None
    finally:
        await _cleanup_temp_files(file_path)

async def _apply_metadata(input_path: str, output_name: str, metadata_code: str) -> str:
    """Apply metadata using FFmpeg"""
    output_path = f"processed/{uuid.uuid4().hex}_{output_name}"
    cmd = [
        'ffmpeg', '-i', input_path, '-map', '0', '-c', 'copy',
        '-metadata', f'comment={metadata_code}', '-y', output_path
    ]
    
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()
    return output_path if proc.returncode == 0 else input_path

def _generate_filename(original: str, template: str) -> str:
    """Generate filename using pattern matching"""
    replacements = {
        '[season]': extract_season(original) or "01",
        '[episode]': extract_episode(original) or "01",
        '[quality]': extract_quality(original) or "HD",
        '[filename]': os.path.splitext(original)[0]
    }
    for ph, val in replacements.items():
        template = template.replace(ph, val)
    return f"{sanitize_filename(template)}{os.path.splitext(original)[1]}"

async def _download_file(client, message, queue_msg, user_id, filename) -> Optional[str]:
    """Download file with progress tracking"""
    dl_path = f"downloads/{user_id}/{uuid.uuid4().hex}{os.path.splitext(filename)[1]}"
    os.makedirs(os.path.dirname(dl_path), exist_ok=True)
    
    return await client.download_media(
        message,
        file_name=dl_path,
        progress=progress_for_pyrogram,
        progress_args=("📥 Downloading...", queue_msg, time.time())
    )

async def _cleanup_temp_files(*paths):
    """Clean temporary files"""
    for path in paths:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception as e:
            logger.error(f"Cleanup error: {e}")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client: Client, message: Message):
    user_id = message.from_user.id
    user_data = await hyoshcoder.read_user(user_id)
    
    # Validate user and settings
    if not user_data or not await hyoshcoder.get_auto_rename_status(user_id):
        return
    
    # Check processing limits
    file_id = message.document.file_id if message.document else message.video.file_id
    if file_id in renaming_operations:
        return
    
    # Process file
    queue_msg = await message.reply("🔄 Starting processing...")
    async with await get_user_semaphore(user_id):
        result = await process_file_rename(client, message, queue_msg, user_id)
        if result:
            await _send_final_file(client, user_id, *result, message, queue_msg)

async def _send_final_file(client, user_id, file_path, file_name, orig_msg, queue_msg):
    """Send processed file back to user"""
    try:
        caption = await _generate_caption(user_id, file_path, file_name)
        thumb = await _get_thumbnail(user_id)
        
        await client.send_document(
            orig_msg.chat.id,
            file_path,
            file_name=file_name,
            caption=caption,
            thumb=thumb,
            progress=progress_for_pyrogram,
            progress_args=("📤 Uploading...", queue_msg, time.time())
        )
        await queue_msg.delete()
    except Exception as e:
        logger.error(f"Upload failed: {e}")
        await queue_msg.edit_text(f"❌ Upload error: {e}")
    finally:
        await _cleanup_temp_files(file_path)

async def _generate_caption(user_id: int, file_path: str, file_name: str) -> str:
    """Generate dynamic caption"""
    template = await hyoshcoder.get_caption(user_id) or "**{filename}**"
    return template.format(
        filename=file_name,
        filesize=humanbytes(os.path.getsize(file_path)),
        duration=format_duration(await _get_duration(file_path))
    )

async def _get_duration(file_path: str) -> Optional[int]:
    """Get media duration using hachoir"""
    try:
        with createParser(file_path) as parser:
            metadata = extractMetadata(parser)
            return metadata.get('duration').seconds if metadata else None
    except Exception as e:
        logger.error(f"Duration error: {e}")
        return None

async def _get_thumbnail(user_id: int) -> Optional[str]:
    """Get user's thumbnail"""
    thumb_id = await hyoshcoder.get_thumbnail(user_id)
    return thumb_id if thumb_id else None
