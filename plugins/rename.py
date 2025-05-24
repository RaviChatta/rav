import os
import time
import re
import asyncio
import uuid
from datetime import datetime
from typing import Dict, List, Optional

from pyrogram import Client, filters
from pyrogram.errors import FloodWait, ChatWriteForbidden
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
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
    if not metadata_code:
        return False
        
    cmd = (
        f'ffmpeg -i "{file_path}" -map 0 -c copy '
        f'-metadata title="{metadata_code}" '
        f'-metadata author="{metadata_code}" '
        f'-metadata comment="{metadata_code}" '
        f'"{output_path}"'
    )
    
    try:
        process = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()
        return process.returncode == 0
    except Exception as e:
        logger.error(f"Metadata application failed: {e}")
        return False

async def process_file_rename(
    client: Client,
    message: Message,
    file_name: str,
    file_id: str,
    queue_message: Message,
    user_id: int
) -> Optional[str]:
    """Handle the complete file renaming process"""
    try:
        # Get user settings
        user_data = await hyoshcoder.read_user(user_id)
        if not user_data:
            await queue_message.edit_text("❌ User data not found")
            return None

        format_template = user_data.get("format_template", "")
        media_preference = user_data.get("media_preference", "")
        sequential_mode = user_data.get("sequential_mode", False)
        src_info = await hyoshcoder.get_src_info(user_id)

        # Extract information from file name or caption
        if src_info == "file_name":
            episode_number = await extract_episode(file_name)
            season = await extract_season(file_name)
            extracted_qualities = await extract_quality(file_name)
        else:
            caption = message.caption if message.caption else ""
            episode_number = await extract_episode(caption)
            season = await extract_season(caption)
            extracted_qualities = await extract_quality(caption)

        # Apply placeholders to template
        if episode_number or season:
            placeholders = {
                "episode": episode_number,
                "Episode": episode_number,
                "EPISODE": episode_number,
                "{episode}": episode_number,
                "season": season,
                "Season": season,
                "SEASON": season,
                "{season}": season
            }

            for placeholder, value in placeholders.items():
                if value and placeholder in format_template:
                    format_template = format_template.replace(placeholder, str(value))

            if extracted_qualities:
                quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
                for placeholder in quality_placeholders:
                    if placeholder in format_template:
                        format_template = format_template.replace(
                            placeholder, 
                            "".join(extracted_qualities)
                        )

        # Generate new file name
        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = f"{format_template}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"metadata_temp/{renamed_file_name}"
        
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        # Download the file
        await queue_message.edit_text(f"📥 Downloading: {file_name}")
        file_uuid = str(uuid.uuid4())[:8]
        temp_path = f"{renamed_file_path}_{file_uuid}"

        try:
            path = await client.download_media(
                message,
                file_name=temp_path,
                progress=progress_for_pyrogram,
                progress_args=("Download progress...", queue_message, time.time()),
            )
            os.rename(path, renamed_file_path)
        except Exception as e:
            await queue_message.edit_text(f"❌ Download failed: {e}")
            return None

        # Apply metadata if enabled
        metadata_enabled = await hyoshcoder.get_metadata(user_id)
        metadata_code = await hyoshcoder.get_metadata_code(user_id) if metadata_enabled else None

        final_path = renamed_file_path
        if metadata_enabled and metadata_code:
            await queue_message.edit_text("🔄 Applying metadata...")
            if await apply_metadata(renamed_file_path, metadata_code, metadata_file_path):
                final_path = metadata_file_path
            else:
                await queue_message.edit_text("⚠️ Metadata application failed, using original file")

        return final_path, renamed_file_name

    except Exception as e:
        logger.error(f"Error in rename processing: {e}")
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
        # Get user settings
        custom_caption = await hyoshcoder.get_caption(user_id)
        custom_thumb = await hyoshcoder.get_thumbnail(user_id)
        sequential_mode = await hyoshcoder.get_sequential_mode(user_id)

        # Prepare file info
        file_size = os.path.getsize(file_path)
        duration = 0

        # Get duration for video files
        if media_type == "video":
            try:
                metadata = extractMetadata(createParser(file_path))
                if metadata and metadata.has("duration"):
                    duration = metadata.get("duration").seconds
            except:
                pass

        # Prepare caption
        caption = (
            custom_caption.format(
                filename=file_name,
                filesize=humanbytes(file_size),
                duration=convert(duration),
            ) if custom_caption else f"**{file_name}**"
        )

        # Handle thumbnail
        thumb_path = None
        if custom_thumb:
            thumb_path = await client.download_media(custom_thumb)
        elif media_type == "video":
            # Try to extract thumbnail from video
            try:
                thumb_path = f"temp/{file_name}_thumb.jpg"
                cmd = f"ffmpeg -i {file_path} -ss 00:00:01 -vframes 1 {thumb_path}"
                process = await asyncio.create_subprocess_shell(cmd)
                await process.wait()
                
                if not os.path.exists(thumb_path):
                    thumb_path = None
            except:
                thumb_path = None

        # Resize thumbnail if exists
        if thumb_path:
            try:
                img = Image.open(thumb_path).convert("RGB")
                img = img.resize((320, 320))
                img.save(thumb_path, "JPEG")
            except:
                thumb_path = None

        # Send file based on type
        if sequential_mode:
            # Handle sequential upload to channel
            log_message = await client.send_document(
                settings.LOG_CHANNEL,
                document=file_path,
                thumb=thumb_path,
                caption=caption,
                progress=progress_for_pyrogram,
                progress_args=("Upload progress...", queue_message, time.time()),
            )

            # Track sequential files
            if user_id not in sequential_operations:
                sequential_operations[user_id] = {"files": [], "expected_count": 0}

            episode = await extract_episode(file_name)
            season = await extract_season(file_name)
            
            sequential_operations[user_id]["files"].append({
                "message_id": log_message.id,
                "file_name": file_name,
                "season": season,
                "episode": episode
            })
            sequential_operations[user_id]["expected_count"] += 1

            # Check if all expected files have been processed
            if len(sequential_operations[user_id]["files"]) == sequential_operations[user_id]["expected_count"]:
                await process_sequential_upload(client, user_id, queue_message)
        else:
            # Direct upload to user
            if media_type == "document":
                await client.send_document(
                    original_message.chat.id,
                    document=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload progress...", queue_message, time.time()),
                )
            elif media_type == "video":
                await client.send_video(
                    original_message.chat.id,
                    video=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload progress...", queue_message, time.time()),
                )
            elif media_type == "audio":
                await client.send_audio(
                    original_message.chat.id,
                    audio=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    duration=duration,
                    progress=progress_for_pyrogram,
                    progress_args=("Upload progress...", queue_message, time.time()),
                )

            await queue_message.delete()

        # Cleanup
        if thumb_path and os.path.exists(thumb_path):
            os.remove(thumb_path)

        return True

    except Exception as e:
        logger.error(f"Error sending renamed file: {e}")
        await queue_message.edit_text(f"❌ Upload failed: {e}")
        return False

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
                x["season"] if x["season"] is not None else 0,
                x["episode"] if x["episode"] is not None else 0
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
            )
        )

    # Check rename template
    format_template = user_data.get("format_template", "")
    if not format_template:
        return await message.reply_text(
            "❌ No rename template set!\n"
            "Please set your rename format using /autorename command"
        )

    # Get file info
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        media_type = "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = getattr(message.video, "file_name", "video.mp4")
        media_type = "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = getattr(message.audio, "file_name", "audio.mp3")
        media_type = "audio"
    else:
        return await message.reply_text("❌ Unsupported file type")

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

        # Send the renamed file
        await send_renamed_file(
            client,
            user_id,
            final_path,
            renamed_file_name,
            message,
            queue_message,
            media_type
        )

        # Track file rename in stats
        await hyoshcoder.track_file_rename(user_id, file_name, renamed_file_name)

    except Exception as e:
        logger.error(f"Error in auto_rename_files: {e}")
        await queue_message.edit_text(f"❌ Error processing file: {e}")
    finally:
        # Cleanup
        if user_id in user_queue_messages and queue_message in user_queue_messages[user_id]:
            user_queue_messages[user_id].remove(queue_message)
        
        if os.path.exists(final_path):
            os.remove(final_path)
        
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
            if str(msg.reply_to_message.message_id) == file_id:
                await msg.edit_text("❌ Processing cancelled by user")
                user_queue_messages[user_id].remove(msg)
                break

    await query.answer("Processing cancelled")
