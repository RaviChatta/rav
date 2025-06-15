from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image
from datetime import datetime
import os
import time
import re
import asyncio
import uuid
import logging
from typing import Optional, Tuple

# Import your existing modules
from helpers.utils import progress_for_pyrogram, humanbytes, convert, extract_episode, extract_quality, extract_season
from database.data import hyoshcoder
from config import settings

logger = logging.getLogger(__name__)

# Global variables to manage operations
renaming_operations = {}
sequential_operations = {}
user_semaphores = {}
user_queue_messages = {}


async def safe_edit_message(message: Message, text: str, **kwargs):
    """Safely edit a message with handling for MessageNotModified errors"""
    try:
        current_text = message.text if hasattr(message, 'text') else message.caption
        if current_text != text:  # Only edit if content has changed
            await message.edit_text(text, **kwargs)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error editing message: {e}")


async def track_rename_operation(user_id: int, original_name: str, new_name: str, points_deducted: int):
    """Track successful rename operations in database"""
    try:
        # Track in file_stats collection
        await hyoshcoder.file_stats.insert_one({
            "user_id": user_id,
            "original_name": original_name,
            "new_name": new_name,
            "timestamp": datetime.now(),
            "date": datetime.now().date().isoformat()
        })

        # Update user's activity stats
        await hyoshcoder.users.update_one(
            {"_id": user_id},
            {
                "$inc": {
                    "activity.total_files_renamed": 1,
                    "activity.daily_usage": 1,
                    "points.total_spent": points_deducted,
                    "points.balance": -points_deducted
                },
                "$set": {
                    "activity.last_usage_date": datetime.now().isoformat(),
                    "activity.last_active": datetime.now().isoformat()
                }
            }
        )

        # Record transaction
        await hyoshcoder.transactions.insert_one({
            "user_id": user_id,
            "type": "file_rename",
            "amount": -points_deducted,
            "description": f"Renamed {original_name} to {new_name}",
            "timestamp": datetime.now(),
            "balance_after": (await hyoshcoder.get_points(user_id)) - points_deducted
        })

        return True
    except Exception as e:
        logger.error(f"Error tracking rename operation: {e}")
        return False


def sanitize_filename(filename: str) -> str:
    """Sanitize filenames to remove problematic characters"""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename).strip()


async def get_user_semaphore(user_id: int) -> asyncio.Semaphore:
    """Get or create semaphore for user"""
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3)
    return user_semaphores[user_id]


async def add_comprehensive_metadata(input_path: str, output_path: str, metadata_text: str) -> Tuple[bool, Optional[str]]:
    """
    Enhanced metadata addition with support for:
    - Multiple video/audio/subtitle streams
    - Fallback strategies
    - Robust error handling
    """
    metadata_cmds = [
        # Full metadata with all streams
        [
            'ffmpeg', '-i', input_path,
            '-map', '0', '-c', 'copy',
            '-metadata', f'title={metadata_text}',
            '-metadata', f'comment={metadata_text}',
            '-metadata', f'description={metadata_text}',
            '-metadata:s:v', f'title={metadata_text}',
            *[arg for i in range(10) for arg in [f'-metadata:s:a:{i}', f'title={metadata_text}']],
            *[arg for i in range(10) for arg in [f'-metadata:s:s:{i}', f'title={metadata_text}']],
            '-movflags', '+faststart',
            '-f', 'matroska',
            '-y', output_path
        ],
        # Simplified version
        [
            'ffmpeg', '-i', input_path,
            '-map', '0', '-c', 'copy',
            '-metadata', f'title={metadata_text}',
            '-metadata:s:v', f'title={metadata_text}',
            '-metadata:s:a', f'title={metadata_text}',
            '-y', output_path
        ],
        # Basic version
        [
            'ffmpeg', '-i', input_path,
            '-c', 'copy',
            '-metadata', f'title={metadata_text}',
            '-y', output_path
        ]
    ]

    for attempt, cmd in enumerate(metadata_cmds, 1):
        try:
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
            
            if process.returncode == 0 and os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                return True, None
            
            error_msg = stderr.decode()
            if attempt == len(metadata_cmds):
                return False, error_msg
            
        except asyncio.TimeoutError:
            if attempt == len(metadata_cmds):
                return False, "FFmpeg timed out after 5 minutes"
        except Exception as e:
            if attempt == len(metadata_cmds):
                return False, str(e)
    
    return False, "All metadata addition attempts failed"


async def send_to_dump_channel(client: Client, user_id: int, file_path: str, caption: str, thumb_path: Optional[str] = None) -> bool:
    """Enhanced dump channel sender with proper media type handling"""
    try:
        dump_channel = await hyoshcoder.get_user_channel(user_id)
        if not dump_channel:
            return False

        try:
            chat = await client.get_chat(dump_channel)
            if chat.type not in ["channel", "supergroup"]:
                return False
        except Exception:
            return False

        ext = os.path.splitext(file_path)[1].lower()
        if ext in ('.mp4', '.mkv', '.avi', '.mov'):
            await client.send_video(
                chat_id=dump_channel,
                video=file_path,
                caption=caption[:1024],
                thumb=thumb_path,
                supports_streaming=True
            )
        elif ext in ('.mp3', '.flac', '.m4a'):
            await client.send_audio(
                chat_id=dump_channel,
                audio=file_path,
                caption=caption[:1024],
                thumb=thumb_path
            )
        else:
            await client.send_document(
                chat_id=dump_channel,
                document=file_path,
                caption=caption[:1024],
                thumb=thumb_path
            )
        return True
    except Exception as e:
        logger.error(f"Dump channel error: {e}", exc_info=True)
        return False


@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    start_time = time.time()

    # Get user data
    user_data = await hyoshcoder.read_user(user_id)
    if not user_data:
        return await message.reply_text("❌ Unable to load your information. Please type /start to register.")

    points_data = user_data.get("points", {})
    user_points = points_data.get("balance", 0)
    format_template = user_data.get("format_template", "")
    media_preference = user_data.get("media_preference", "")
    sequential_mode = user_data.get("sequential_mode", False)
    src_info = await hyoshcoder.get_src_info(user_id)  

    # Get points config
    points_config = await hyoshcoder.get_config("points_config", {})
    rename_cost = points_config.get("rename_cost", 1)

    if user_points < rename_cost:
        return await message.reply_text(
            f"❌ You don't have enough points (Needed: {rename_cost})",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Free points", callback_data="freepoints")]])
        )

    if not format_template:
        return await message.reply_text("Please set your rename format with /autorename")

    # File type handling
    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        media_type = media_preference or "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_name}.mp4" if not message.video.file_name.endswith('.mp4') else message.video.file_name
        media_type = media_preference or "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_name}.mp3" if not message.audio.file_name.endswith('.mp3') else message.audio.file_name
        media_type = media_preference or "audio"
    else:
        return await message.reply_text("Unsupported file type")

    # Check for duplicate processing
    if file_id in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed_time < 10:
            return

    renaming_operations[file_id] = datetime.now()

    # Extract metadata from filename/caption
    if src_info == "file_name":
        episode_number = await extract_episode(file_name)
        season = await extract_season(file_name)
        extracted_qualities = await extract_quality(file_name)
    elif src_info == "caption":
        caption = message.caption if message.caption else ""
        episode_number = await extract_episode(caption)
        season = await extract_season(caption)
        extracted_qualities = await extract_quality(caption)
    else:
        episode_number = await extract_episode(file_name)
        season = await extract_season(file_name)
        extracted_qualities = await extract_quality(file_name)

    # Queue message
    confirmation_message = (
        "**File added to queue ✅**\n"
        f"➲ **Name:** `{file_name}`\n"
        f"➲ **Season:** `{season if season else 'N/A'}`\n"
        f"➲ **Episode:** `{episode_number if episode_number else 'N/A'}`\n"
        f"➲ **Quality:** `{extracted_qualities if extracted_qualities else 'N/A'}`"
    )
    queue_message = await message.reply_text(confirmation_message)

    if user_id not in user_queue_messages:
        user_queue_messages[user_id] = []
    user_queue_messages[user_id].append(queue_message)

    user_semaphore = await get_user_semaphore(user_id)
    await user_semaphore.acquire()

    try:
        # Process queue messages
        if user_id in user_queue_messages and user_queue_messages[user_id]:
            await safe_edit_message(user_queue_messages[user_id][0], f"🔄 **Processing:** `{file_name}`")
            user_queue_messages[user_id].pop(0)
            
        if user_id not in sequential_operations:
            sequential_operations[user_id] = {"files": [], "expected_count": 0}

        sequential_operations[user_id]["expected_count"] += 1

        # Apply format template
        if episode_number or season:
            placeholders = ["episode", "Episode", "EPISODE", "{episode}", "season", "Season", "SEASON", "{season}"]
            for placeholder in placeholders:
                if placeholder.lower() in ["episode", "{episode}"] and episode_number:
                    format_template = format_template.replace(placeholder, str(episode_number), 1)
                elif placeholder.lower() in ["season", "{season}"] and season:
                    format_template = format_template.replace(placeholder, str(season), 1)

            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in format_template:
                    if extracted_qualities == "Unknown":
                        await safe_edit_message(queue_message, "**Using 'Unknown' for quality**")
                        format_template = format_template.replace(quality_placeholder, "Unknown")
                    else:
                        format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))

        # Prepare file paths
        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = sanitize_filename(f"{format_template}{file_extension}")
        renamed_file_path = os.path.join("downloads", renamed_file_name)
        metadata_file_path = os.path.join("Metadata", renamed_file_name)
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        file_uuid = str(uuid.uuid4())[:8]
        temp_file_path = f"{renamed_file_path}_{file_uuid}"

        # Download file
        await safe_edit_message(queue_message, f"📥 **Downloading:** `{file_name}`")
        try:
            path = await client.download_media(
                message,
                file_name=temp_file_path,
                progress=progress_for_pyrogram,
                progress_args=("Downloading...", queue_message, time.time()),
            )
        except Exception as e:
            del renaming_operations[file_id]
            return await safe_edit_message(queue_message, f"❌ Download failed: {e}")

        # Rename file
        try:
            os.rename(path, renamed_file_path)
            path = renamed_file_path
        except Exception as e:
            await safe_edit_message(queue_message, f"❌ Rename failed: {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return

        # Add metadata if enabled
        metadata_added = False
        _bool_metadata = await hyoshcoder.get_metadata(user_id)
        if _bool_metadata:
            metadata = await hyoshcoder.get_metadata_code(user_id)
            if metadata:
                await safe_edit_message(queue_message, "🔄 Adding metadata to all streams...")
                success, error = await add_comprehensive_metadata(
                    renamed_file_path,
                    metadata_file_path,
                    metadata
                )
                
                if success:
                    metadata_added = True
                    path = metadata_file_path
                else:
                    error_msg = error[:500] if error else "Unknown error"
                    await safe_edit_message(queue_message, f"⚠️ Metadata failed: {error_msg}\nUsing original file")
                    path = renamed_file_path

        # Prepare for upload
        await safe_edit_message(queue_message, f"📤 **Uploading:** `{file_name}`")
        thumb_path = None
        custom_caption = await hyoshcoder.get_caption(message.chat.id)
        custom_thumb = await hyoshcoder.get_thumbnail(message.chat.id)

        # Get file info
        if message.document:
            file_size = humanbytes(message.document.file_size)
            duration = convert(0)
        elif message.video:
            file_size = humanbytes(message.video.file_size)
            duration = convert(message.video.duration or 0)
        elif message.audio:
            file_size = humanbytes(message.audio.file_size)
            duration = convert(message.audio.duration or 0)

        caption = (
            custom_caption.format(
                filename=renamed_file_name,
                filesize=file_size,
                duration=duration,
            )
            if custom_caption
            else f"**{renamed_file_name}**"
        )

        # Handle thumbnail
        if custom_thumb:
            thumb_path = await client.download_media(custom_thumb)
        elif media_type == "video" and message.video.thumbs:
            thumb_path = await client.download_media(message.video.thumbs[0].file_id)
        elif media_type == "audio" and message.audio.thumbs:
            thumb_path = await client.download_media(message.audio.thumbs[0].file_id)

        if thumb_path:
            try:
                with Image.open(thumb_path) as img:
                    img = img.convert("RGB")
                    img.thumbnail((320, 320))
                    img.save(thumb_path, "JPEG", quality=85)
            except Exception as e:
                logger.warning(f"Thumbnail error: {e}")
                thumb_path = None

        # Upload flow
        try:
            # Try dump channel first
            dump_success = await send_to_dump_channel(
                client,
                user_id,
                path,
                caption,
                thumb_path
            )
            
            if dump_success:
                await safe_edit_message(queue_message, "✅ Sent to dump channel!")
            else:
                # Normal upload
                if media_type == "document":
                    await client.send_document(
                        message.chat.id,
                        document=path,
                        thumb=thumb_path,
                        caption=caption,
                        progress=progress_for_pyrogram,
                        progress_args=("Uploading...", queue_message, time.time())
                    )
                elif media_type == "video":
                    await client.send_video(
                        message.chat.id,
                        video=path,
                        caption=caption,
                        thumb=thumb_path,
                        duration=message.video.duration if message.video else 0,
                        supports_streaming=True,
                        progress=progress_for_pyrogram,
                        progress_args=("Uploading...", queue_message, time.time())
                    )
                elif media_type == "audio":
                    await client.send_audio(
                        message.chat.id,
                        audio=path,
                        caption=caption,
                        thumb=thumb_path,
                        duration=message.audio.duration if message.audio else 0,
                        progress=progress_for_pyrogram,
                        progress_args=("Uploading...", queue_message, time.time())
                    )

            # Success message
            time_taken = time.time() - start_time
            remaining_points = (await hyoshcoder.get_points(user_id)) - rename_cost
            success_msg = (
                f"✅ **Successfully processed!**\n\n"
                f"➲ **Original:** `{file_name}`\n"
                f"➲ **Renamed:** `{renamed_file_name}`\n"
                f"➲ **Time:** {time_taken:.1f}s\n"
                f"➲ **Metadata:** {'Yes' if metadata_added else 'No'}\n"
                f"➲ **Points Used:** {rename_cost}\n"
                f"➲ **Remaining Points:** {remaining_points}"
            )
            await message.reply_text(success_msg)

        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
            await message.reply_text(f"⚠️ Flood wait: {e.value} seconds")
        except Exception as e:
            await safe_edit_message(queue_message, f"❌ Upload failed: {e}")
            raise
        finally:
            # Cleanup
            try:
                if os.path.exists(renamed_file_path):
                    os.remove(renamed_file_path)
                if os.path.exists(metadata_file_path):
                    os.remove(metadata_file_path)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)
                if os.path.exists(temp_file_path):
                    os.remove(temp_file_path)
            except Exception as e:
                logger.error(f"Cleanup error: {e}")

            if file_id in renaming_operations:
                del renaming_operations[file_id]
            
            try:
                await queue_message.delete()
            except:
                pass

            # Deduct points
            await hyoshcoder.deduct_points(user_id, rename_cost)
    finally:
        user_semaphore.release()
