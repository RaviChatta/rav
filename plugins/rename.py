import os
import time
import re
import asyncio
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser

from helpers.utils import (
    progress_for_pyrogram,
    humanbytes,
    convert,
    extract_episode,
    extract_quality,
    extract_season,
    get_random_photo
)
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)

# Global variables to manage operations
renaming_operations: Dict[str, datetime] = {}
sequential_operations: Dict[int, Dict] = {}
user_semaphores: Dict[int, asyncio.Semaphore] = {}
user_queue_messages: Dict[int, List[Message]] = {}

async def get_user_semaphore(user_id: int) -> asyncio.Semaphore:
    """Get or create a semaphore for user to control concurrent operations"""
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3)  # Limit to 3 concurrent operations per user
    return user_semaphores[user_id]

async def apply_metadata(file_path: str, metadata_code: str, output_path: str) -> bool:
    """Apply metadata to file using ffmpeg"""
    if not metadata_code or not os.path.exists(file_path):
        return False
        
    try:
        cmd = [
            'ffmpeg',
            '-i', file_path,
            '-map', '0',
            '-c', 'copy',
            '-metadata', f'title={metadata_code}',
            '-metadata', f'author={metadata_code}',
            '-metadata', f'comment={metadata_code}',
            '-y',  # Overwrite output file if exists
            output_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        _, stderr = await process.communicate()
        if process.returncode != 0:
            logger.error(f"Metadata application failed: {stderr.decode()}")
            return False
            
        return os.path.exists(output_path)
    except Exception as e:
        logger.error(f"Metadata application error: {e}")
        return False

async def process_file_rename(client, message, file_name, file_id, queue_message, user_id):
    try:
        # Get user settings
        user_data = await hyoshcoder.read_user(user_id)
        if not user_data:
            await queue_message.edit_text("❌ User data not found")
            return None

        format_template = user_data.get("format_template")
        if not format_template:
            await queue_message.edit_text("❌ No rename template set")
            return None

        # Create downloads directory if not exists
        os.makedirs("downloads", exist_ok=True)

        # Download file with progress
        temp_path = f"downloads/temp_{file_id}"
        await queue_message.edit_text(f"📥 Downloading: {file_name}")
        
        file_path = await client.download_media(
            message,
            file_name=temp_path,
            progress=progress_for_pyrogram,
            progress_args=("Downloading...", queue_message, time.time())
        )

        if not file_path or not os.path.exists(file_path):
            await queue_message.edit_text("❌ Download failed")
            return None

        # Generate new filename
        new_name = generate_new_filename(file_name, format_template)
        new_path = os.path.join("downloads", new_name)
        
        # Rename file
        os.rename(file_path, new_path)
        return new_path, new_name

    except Exception as e:
        logger.error(f"Rename error: {str(e)}")
        await queue_message.edit_text(f"❌ Error: {str(e)}")
        return None
    finally:
        # Cleanup temp files
        if 'temp_path' in locals() and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except:
                pass

def generate_new_filename(original_name, template):
    """Generate new filename based on template"""
    # Extract media info
    season = extract_season(original_name) or "01"
    episode = extract_episode(original_name) or "01"
    quality = extract_quality(original_name) or "HD"
    
    # Apply template
    new_name = template
    new_name = new_name.replace("[season]", season)
    new_name = new_name.replace("[episode]", episode)
    new_name = new_name.replace("[quality]", quality)
    new_name = new_name.replace("[filename]", os.path.splitext(original_name)[0])
    
    # Add extension
    ext = os.path.splitext(original_name)[1]
    return f"{new_name}{ext}"
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)

        # Download the file
        await queue_message.edit_text(f"📥 Downloading: {file_name}")
        temp_path = f"{renamed_file_path}_{str(uuid.uuid4())[:8]}"

        file_path = await client.download_media(
            message,
            file_name=temp_path,
            progress=progress_for_pyrogram,
            progress_args=("Download progress...", queue_message, time.time()),
        )
        
        if not file_path or not os.path.exists(file_path):
            await queue_message.edit_text("❌ Download failed")
            return None
            
        os.rename(file_path, renamed_file_path)
        return renamed_file_path, renamed_file_name

    except Exception as e:
        logger.error(f"Rename processing error: {e}")
        await queue_message.edit_text(f"❌ Processing error: {e}")
        return None


async def send_renamed_file(
    client: Client,
    user_id: int,
    file_path: str,
    file_name: str,
    original_message: Message,
    queue_message: Message,
    media_type: str = "document"
) -> bool:
    """Send the renamed file back to the user"""
    try:
        if not os.path.exists(file_path):
            await queue_message.edit_text("❌ File not found for upload")
            return False

        # Get user settings
        custom_caption = await hyoshcoder.get_caption(user_id)
        custom_thumb = await hyoshcoder.get_thumbnail(user_id)

        # Prepare caption
        file_size = os.path.getsize(file_path)
        caption = (
            custom_caption.format(
                filename=file_name,
                filesize=humanbytes(file_size),
                duration="N/A"
            ) if custom_caption else f"**{file_name}**"
        )

        # Handle thumbnail
        thumb_path = None
        if custom_thumb:
            try:
                thumb_path = await client.download_media(custom_thumb)
            except Exception as e:
                logger.error(f"Thumbnail download error: {e}")

        # Send file based on type
        if media_type == "document":
            await client.send_document(
                original_message.chat.id,
                document=file_path,
                thumb=thumb_path,
                caption=caption,
                file_name=file_name
            )
        elif media_type == "video":
            await client.send_video(
                original_message.chat.id,
                video=file_path,
                thumb=thumb_path,
                caption=caption,
                file_name=file_name
            )
        elif media_type == "audio":
            await client.send_audio(
                original_message.chat.id,
                audio=file_path,
                thumb=thumb_path,
                caption=caption,
                file_name=file_name
            )

        await queue_message.delete()
        return True

    except Exception as e:
        logger.error(f"File upload error: {e}")
        await queue_message.edit_text(f"❌ Upload failed: {e}")
        return False
    finally:
        # Cleanup
        if thumb_path and os.path.exists(thumb_path):
            try:
                os.remove(thumb_path)
            except:
                pass
        return True

async def process_sequential_upload(client: Client, user_id: int, queue_message: Message):
    """Handle sequential upload of multiple files to user's channel"""
    try:
        if user_id not in sequential_operations:
            return

        files_info = sequential_operations[user_id]["files"]
        expected_count = sequential_operations[user_id]["expected_count"]

        if len(files_info) != expected_count:
            return

        # Sort files by season and episode
        sorted_files = sorted(
            files_info,
            key=lambda x: (
                int(x["season"]) if x["season"] and x["season"].isdigit() else 0,
                int(x["episode"]) if x["episode"] and x["episode"].isdigit() else 0
            )
        )

        # Get user's dump channel
        user_channel = await hyoshcoder.get_user_channel(user_id)
        if not user_channel:
            user_channel = user_id  # Fallback to user's PM if no channel set

        success_count = 0
        errors = []

        # Try to send to user's channel
        try:
            for file_info in sorted_files:
                try:
                    await asyncio.sleep(3)  # Rate limiting
                    await client.copy_message(
                        user_channel,
                        settings.LOG_CHANNEL,
                        file_info["message_id"]
                    )
                    success_count += 1
                except Exception as e:
                    errors.append(f"{file_info['file_name']}: {str(e)}")
        except Exception as e:
            await queue_message.reply_text(
                f"❌ Failed to send to channel {user_channel}: {e}\n"
                "Sending files to your PM instead..."
            )
            
            # Fallback to user's PM
            for file_info in sorted_files:
                try:
                    await asyncio.sleep(3)
                    await client.copy_message(
                        user_id,
                        settings.LOG_CHANNEL,
                        file_info["message_id"]
                    )
                    success_count += 1
                except Exception as e:
                    errors.append(f"{file_info['file_name']}: {str(e)}")

        # Send summary message
        result_message = (
            f"✅ Successfully sent {success_count}/{expected_count} files\n"
            f"📌 Destination: {'your PM' if user_channel == user_id else f'channel {user_channel}'}"
        )
        
        if errors:
            result_message += "\n\n❌ Errors:\n" + "\n".join(errors[:5])  # Show first 5 errors
            if len(errors) > 5:
                result_message += f"\n...and {len(errors)-5} more"

        await queue_message.reply_text(result_message)

    except Exception as e:
        logger.error(f"Error in sequential upload: {e}")
        await queue_message.reply_text(f"❌ Sequential upload failed: {e}")
    finally:
        if user_id in sequential_operations:
            del sequential_operations[user_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check user registration
    user_data = await hyoshcoder.read_user(user_id)
    if not user_data:
        return await message.reply_text("❌ Please start the bot first with /start")

    # Check auto-rename status
    auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
    if not auto_rename_status:
        return  # Skip processing if auto-rename is disabled

    # Check points balance
    points_config = await hyoshcoder.get_config("points_config") or {}
    points_per_rename = points_config.get("per_rename", 1)
    current_points = await hyoshcoder.get_points(user_id)
    
    premium_status = await hyoshcoder.check_premium_status(user_id)
    if not premium_status.get("is_premium", False) and current_points < points_per_rename:
        return await message.reply_text(
            f"❌ Insufficient points! Each rename costs {points_per_rename} points\n"
            f"Your balance: {current_points} points",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎁 Get Free Points", callback_data="freepoints")]
            ])
        )

    # Get file info with proper type handling
    file_id = None
    file_name = "file"
    media_type = "document"
    
    if message.document:
        file = message.document
        file_id = file.file_id
        file_name = file.file_name or "document"
        media_type = "document"
    elif message.video:
        file = message.video
        file_id = file.file_id
        file_name = getattr(file, "file_name", None) or "video.mp4"
        media_type = "video"
    elif message.audio:
        file = message.audio
        file_id = file.file_id
        file_name = getattr(file, "file_name", None) or "audio.mp3"
        media_type = "audio"
    else:
        return await message.reply_text("❌ Unsupported file type")

    # Check rename template
    format_template = user_data.get("format_template", "")
    if not format_template:
        return await message.reply_text(
            "❌ No rename template set!\n"
            "Please set your rename format using /autorename command"
        )

    # Check for duplicate processing
    if file_id in renaming_operations:
        elapsed = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed < 10:  # 10 second cooldown for same file
            return
    renaming_operations[file_id] = datetime.now()

    # Create queue message
    queue_message = await message.reply_text(
        "🔄 Your file has been added to processing queue...",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{file_id}")]
        ])
    )

    # Track queue messages
    if user_id not in user_queue_messages:
        user_queue_messages[user_id] = []
    user_queue_messages[user_id].append(queue_message)

    # Acquire semaphore for this user
    user_semaphore = await get_user_semaphore(user_id)
    await user_semaphore.acquire()

    try:
        # Process the file
        result = await process_file_rename(client, message, file_name, file_id, queue_message, user_id)
        if not result:
            return

        final_path, renamed_file_name = result

        # Deduct points if not premium
        if not premium_status.get("is_premium", False):
            await hyoshcoder.deduct_points(user_id, points_per_rename, "file_rename")

        # Send the renamed file with proper media type handling
        success = await send_renamed_file(
            client,
            user_id,
            final_path,
            renamed_file_name,
            message,
            queue_message,
            media_type
        )

        # Track file rename in stats if successful
        if success:
            await hyoshcoder.track_file_rename(user_id, file_name, renamed_file_name)

    except Exception as e:
        logger.error(f"Error in auto_rename_files: {e}")
        await queue_message.edit_text(f"❌ Error processing file: {e}")
    finally:
        # Cleanup
        if user_id in user_queue_messages and queue_message in user_queue_messages[user_id]:
            user_queue_messages[user_id].remove(queue_message)
        
        try:
            if 'final_path' in locals() and os.path.exists(final_path):
                os.remove(final_path)
        except:
            pass
        
        if file_id in renaming_operations:
            del renaming_operations[file_id]
        
        user_semaphore.release()

@Client.on_callback_query(filters.regex(r"^cancel_"))
async def cancel_rename(client: Client, query: CallbackQuery):
    """Handle rename cancellation"""
    file_id = query.data.split("_", 1)[1]
    user_id = query.from_user.id

    if file_id in renaming_operations:
        del renaming_operations[file_id]
    
    if user_id in user_queue_messages:
        for msg in user_queue_messages[user_id]:
            try:
                if str(msg.reply_to_message.message_id) == file_id:
                    await msg.edit_text("❌ Processing cancelled by user")
                    user_queue_messages[user_id].remove(msg)
                    break
            except:
                continue

    await query.answer("Processing cancelled")
