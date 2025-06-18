from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified, BadRequest
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image
from datetime import datetime
import os
import time
import re
import asyncio
import uuid
import logging
from typing import Optional, Tuple, Dict, List

# Database imports
from database.data import hyoshcoder
from config import settings
from helpers.utils import progress_for_pyrogram, humanbytes, convert, extract_episode, extract_quality, extract_season

logger = logging.getLogger(__name__)

# Global variables to manage operations
renaming_operations = {}
user_semaphores = {}
user_queue_messages = {}
user_batch_trackers = {}  # Track batch operations per user
sequential_operations = {}  # For sequential mode
file_processing_counters = {}  # Track individual file counters per user
cancel_operations = {}  # Track cancel requests
processed_files = set()  # Track processed files to prevent duplicate point deductions

async def safe_edit_message(message: Message, text: str, **kwargs):
    """Safely edit a message with handling for MessageNotModified errors"""
    try:
        current_text = message.text if hasattr(message, 'text') else message.caption
        if current_text != text:
            await message.edit_text(text, **kwargs)
    except MessageNotModified:
        pass
    except Exception as e:
        logger.error(f"Error editing message: {e}")

async def track_rename_operation(user_id: int, original_name: str, new_name: str, points_deducted: int):
    """Track successful rename operations in database"""
    try:
        # Check if this file was already processed
        file_hash = hash((user_id, original_name, new_name))
        if file_hash in processed_files:
            return True
            
        await hyoshcoder.file_stats.insert_one({
            "user_id": user_id,
            "original_name": original_name,
            "new_name": new_name,
            "timestamp": datetime.now(),
            "date": datetime.now().date().isoformat()
        })

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

        await hyoshcoder.transactions.insert_one({
            "user_id": user_id,
            "type": "file_rename",
            "amount": -points_deducted,
            "description": f"Renamed {original_name} to {new_name}",
            "timestamp": datetime.now(),
            "balance_after": (await hyoshcoder.get_points(user_id)) - points_deducted
        })

        # Mark file as processed
        processed_files.add(file_hash)
        return True
    except Exception as e:
        logger.error(f"Error tracking rename operation: {e}")
        return False

def sanitize_filename(filename: str) -> str:
    """Sanitize filenames to remove problematic characters"""
    # First remove any invalid characters
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename)
    # Then ensure the filename is ASCII only to avoid encoding issues
    return sanitized.encode('ascii', 'ignore').decode('ascii').strip()

async def get_user_semaphore(user_id: int) -> asyncio.Semaphore:
    """Get or create semaphore for user"""
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3)
    return user_semaphores[user_id]

async def get_stream_indexes(input_path: str):
    try:
        probe = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error',
            '-select_streams', 'v,a,s',
            '-show_entries', 'stream=index,codec_type',
            '-of', 'json', input_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await probe.communicate()
        data = json.loads(stdout.decode())

        video_indexes = [s['index'] for s in data['streams'] if s['codec_type'] == 'video']
        audio_indexes = [s['index'] for s in data['streams'] if s['codec_type'] == 'audio']
        subtitle_indexes = [s['index'] for s in data['streams'] if s['codec_type'] == 'subtitle']
        return video_indexes, audio_indexes, subtitle_indexes
    except Exception as e:
        return [], [], []

async def add_comprehensive_metadata(input_path: str, output_path: str, metadata_text: str) -> Tuple[bool, Optional[str]]:
    """Enhanced metadata addition with FFmpeg and dynamic stream detection"""
    video_indexes, audio_indexes, subtitle_indexes = await get_stream_indexes(input_path)

    metadata_cmds = [
        [
            'ffmpeg', '-i', input_path,
            '-map', '0', '-c', 'copy',
            '-metadata', f'title={metadata_text}',
            '-metadata', f'comment={metadata_text}',
            '-metadata', f'description={metadata_text}',
            *[f'-metadata:s:v:{i}' for i in video_indexes for _ in (0,)],
            *[metadata_text for _ in video_indexes],
            *[f'-metadata:s:a:{i}' for i in audio_indexes for _ in (0,)],
            *[metadata_text for _ in audio_indexes],
            *[f'-metadata:s:s:{i}' for i in subtitle_indexes for _ in (0,)],
            *[metadata_text for _ in subtitle_indexes],
            '-f', 'matroska',
            '-y', output_path
        ],
        [
            'ffmpeg', '-i', input_path,
            '-map', '0', '-c', 'copy',
            '-metadata', f'title={metadata_text}',
            *[f'-metadata:s:v:{i}' for i in video_indexes for _ in (0,)],
            *[metadata_text for _ in video_indexes],
            *[f'-metadata:s:a:{i}' for i in audio_indexes for _ in (0,)],
            *[metadata_text for _ in audio_indexes],
            '-y', output_path
        ],
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
    """Enhanced dump channel sender"""
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

async def get_user_rank(user_id: int) -> Tuple[Optional[int], int]:
    """Get user's global rank and total renames"""
    try:
        pipeline = [
            {"$group": {"_id": "$user_id", "total_renames": {"$sum": 1}}},
            {"$sort": {"total_renames": -1}}
        ]
        
        all_users = await hyoshcoder.file_stats.aggregate(pipeline).to_list(None)
        
        for index, user in enumerate(all_users, start=1):
            if user["_id"] == user_id:
                return index, user["total_renames"]
        
        return None, 0
    except Exception as e:
        logger.error(f"Error getting user rank: {e}")
        return None, 0

async def send_completion_message(client: Client, user_id: int, start_time: float, file_count: int, points_used: int):
    """Send the unified completion message for batch operations"""
    try:
        # Check if operation was canceled
        if user_id in cancel_operations and cancel_operations[user_id]:
            del cancel_operations[user_id]
            return await client.send_message(user_id, "❌ Batch processing was canceled!")
        
        user_rank, total_renames = await get_user_rank(user_id)
        user_points = await hyoshcoder.get_points(user_id)
        
        time_taken = time.time() - start_time
        mins, secs = divmod(int(time_taken), 60)
        avg_time = time_taken / file_count if file_count > 0 else 0
        avg_mins, avg_secs = divmod(int(avg_time), 60)
        
        completion_msg = (
            f"❐ Batch Rename Completed\n\n"
            f"⌬ Total Files: « {file_count} »\n"
            f"⌬ Total Points Used: « {points_used} »\n"
            f"⌬ Points Remaining: « {user_points} »\n"
            f"⌬ Total Time Taken: {mins}m {secs}s\n"
            f"⌬ Average Time Per File: {avg_mins}m {avg_secs}s\n"
            f"⌬ Your Total Renames: {total_renames}\n"
            f"⌬ Global Rank: #{user_rank if user_rank else 'N/A'}"
        )
        
        await client.send_message(user_id, completion_msg)
    except Exception as e:
        logger.error(f"Error sending completion message: {e}")
        await client.send_message(user_id, "✅ Batch processing completed successfully!")

async def send_single_success_message(client: Client, message: Message, file_name: str, renamed_file_name: str, 
                                    start_time: float, rename_cost: int, metadata_added: bool):
    """Send success message for single file operations"""
    try:
        # Check if operation was canceled
        if message.from_user.id in cancel_operations and cancel_operations[message.from_user.id]:
            del cancel_operations[message.from_user.id]
            return await message.reply_text("❌ Processing was canceled!")
        
        time_taken = time.time() - start_time
        remaining_points = (await hyoshcoder.get_points(message.from_user.id)) - rename_cost
        success_msg = (
            f"✅ **File Renamed Successfully!**\n\n"
            f"➲ **Original:** `{file_name}`\n"
            f"➲ **Renamed:** `{renamed_file_name}`\n"
            f"➲ **Time Taken:** {time_taken:.1f}s\n"
            f"➲ **Metadata Added:** {'Yes' if metadata_added else 'No'}\n"
            f"➲ **Points Used:** {rename_cost}\n"
            f"➲ **Remaining Points:** {remaining_points}"
        )
        await message.reply_text(success_msg)
    except Exception as e:
        logger.error(f"Error sending success message: {e}")
        await message.reply_text("✅ File processed successfully!")

@Client.on_message(filters.command("cancel"))
async def cancel_processing(client: Client, message: Message):
    """Cancel current processing operations"""
    user_id = message.from_user.id
    cancel_operations[user_id] = True
    
    # Clean up any ongoing operations
    if user_id in user_batch_trackers:
        del user_batch_trackers[user_id]
    if user_id in file_processing_counters:
        del file_processing_counters[user_id]
    if user_id in sequential_operations:
        sequential_operations[user_id]["files"] = []
    
    await message.reply_text("🛑 Cancel request received. Current operations will be stopped after completing current file.")

@Client.on_message((filters.document | filters.video | filters.audio) & (filters.group | filters.private))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    start_time = time.time()

    # Check for cancel request
    if user_id in cancel_operations and cancel_operations[user_id]:
        return

    # Initialize user's counter if not exists
    if user_id not in file_processing_counters:
        file_processing_counters[user_id] = 0
    
    # Get unique file number for this user
    # Increment file counter
    file_processing_counters[user_id] = file_processing_counters.get(user_id, 0) + 1
    current_file_number = file_processing_counters[user_id]
    
    # Initialize batch tracker only if media_group_id exists
    if getattr(message, 'media_group_id', None):
        if user_id not in user_batch_trackers:
            user_batch_trackers[user_id] = {
                "start_time": start_time,
                "count": 0,
                "points_used": 0,
                "is_batch": True
            }
        
        batch_data = user_batch_trackers[user_id]
        batch_data["count"] += 1
    else:
        # Not a batch - handle single file
        current_file_number = 1  # Optional fallback for single uploads


    # Get user data
    try:
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
        file_size = 0
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
            media_type = media_preference or "document"
            file_size = message.document.file_size
        elif message.video:
            file_id = message.video.file_id
            file_name = f"{message.video.file_name}.mp4" if not message.video.file_name.endswith('.mp4') else message.video.file_name
            media_type = media_preference or "video"
            file_size = message.video.file_size
        elif message.audio:
            file_id = message.audio.file_id
            file_name = f"{message.audio.file_name}.mp3" if not message.audio.file_name.endswith('.mp3') else message.audio.file_name
            media_type = media_preference or "audio"
            file_size = message.audio.file_size
        else:
            return await message.reply_text("Unsupported file type")

        # Check file size (2GB limit)
        if file_size > 2 * 1024 * 1024 * 1024:  # 2GB in bytes
            return await message.reply_text("ᴛʜᴇ ғɪʟᴇ ᴇxᴄᴇᴇᴅs 2GB. ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ sᴍᴀʟʟᴇʀ ғɪʟᴇ ᴏʀ ᴍᴇᴅɪᴀ.")

        # Check for duplicate processing
        if file_id in renaming_operations:
            elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
            if elapsed_time < 10:
                return

        renaming_operations[file_id] = datetime.now()

        # Queue message with detailed info
        confirmation_message = (
            "**File added to queue ✅**\n"
            f"➲ **Name:** `{file_name}`\n"
            f"➲ **Queue Position:** #{current_file_number}\n"
            f"➲ **Points to Deduct:** {rename_cost}"
        )
        queue_message = await message.reply_text(confirmation_message)

        user_semaphore = await get_user_semaphore(user_id)
        await user_semaphore.acquire()

        try:
            # Check for cancel request again after acquiring semaphore
            if user_id in cancel_operations and cancel_operations[user_id]:
                await queue_message.edit_text("❌ Processing canceled by user")
                return

            # Process queue messages
            if user_id in user_queue_messages and user_queue_messages[user_id]:
                await safe_edit_message(user_queue_messages[user_id][0], f"🔄 Processing queue #{current_file_number}")
                user_queue_messages[user_id].pop(0)

            # Sequential mode handling
            if sequential_mode:
                if user_id not in sequential_operations:
                    sequential_operations[user_id] = {"files": [], "expected_count": 0}

                sequential_operations[user_id]["expected_count"] += 1
                while len(sequential_operations[user_id]["files"]) > 0:
                    await asyncio.sleep(1)
                    if user_id in cancel_operations and cancel_operations[user_id]:
                        await queue_message.edit_text("❌ Processing canceled by user")
                        return

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

            # Prepare file paths with ASCII-only filenames
            _, file_extension = os.path.splitext(file_name)
            renamed_file_name = sanitize_filename(f"{format_template}{file_extension}")
            renamed_file_path = os.path.join("downloads", renamed_file_name)
            metadata_file_path = os.path.join("Metadata", renamed_file_name)
            os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
            os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

            file_uuid = str(uuid.uuid4())[:8]
            temp_file_path = f"{renamed_file_path}_{file_uuid}"

            # Download file with retry logic
            max_download_retries = 3
            for attempt in range(max_download_retries):
                try:
                    if user_id in cancel_operations and cancel_operations[user_id]:
                        await queue_message.edit_text("❌ Processing canceled by user")
                        return

                    await safe_edit_message(queue_message, f"📥 Downloading queue #{current_file_number} (Attempt {attempt + 1})")
                    path = await client.download_media(
                        message,
                        file_name=temp_file_path,
                        progress=progress_for_pyrogram,
                        progress_args=(f"Downloading #{current_file_number}", queue_message, time.time()),
                    )
                    break
                except Exception as e:
                    if attempt == max_download_retries - 1:
                        del renaming_operations[file_id]
                        return await safe_edit_message(queue_message, f"❌ Download failed: {e}")
                    await asyncio.sleep(2 ** attempt)

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
                    await safe_edit_message(queue_message, f"🔄 𝙧𝙚𝙣𝙖𝙢𝙞𝙣𝙜 𝙖𝙣𝙙 𝘼𝙙𝙙𝙞𝙣𝙜 𝙢𝙚𝙩𝙖𝙙𝙖𝙩𝙖 𝙩𝙤 #{current_file_number}")
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
            await safe_edit_message(queue_message, f"📤 Uploading queue #{current_file_number}")
            thumb_path = None
            custom_caption = await hyoshcoder.get_caption(message.chat.id)
            custom_thumb = await hyoshcoder.get_thumbnail(message.chat.id)

            # Get file info
            file_size_human = humanbytes(file_size)
            if message.document:
                duration = convert(0)
            elif message.video:
                duration = convert(message.video.duration or 0)
            elif message.audio:
                duration = convert(message.audio.duration or 0)

            caption = (
                custom_caption.format(
                    filename=renamed_file_name,
                    filesize=file_size_human,
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

            # Upload flow with retry logic
            max_upload_retries = 5
            for attempt in range(max_upload_retries):
                try:
                    if user_id in cancel_operations and cancel_operations[user_id]:
                        await queue_message.edit_text("❌ Processing canceled by user")
                        return

                    # Try dump channel first
                    dump_success = await send_to_dump_channel(
                        client,
                        user_id,
                        path,
                        caption,
                        thumb_path
                    )
                    
                    if dump_success:
                        await safe_edit_message(queue_message, f"✅ Sent #{current_file_number} to dump channel!")
                    else:
                        # Normal upload
                        if media_type == "document":
                            await client.send_document(
                                message.chat.id,
                                document=path,
                                thumb=thumb_path,
                                caption=caption,
                                progress=progress_for_pyrogram,
                                progress_args=(f"Uploading #{current_file_number}", queue_message, time.time())
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
                                progress_args=(f"Uploading #{current_file_number}", queue_message, time.time())
                            )
                        elif media_type == "audio":
                            await client.send_audio(
                                message.chat.id,
                                audio=path,
                                caption=caption,
                                thumb=thumb_path,
                                duration=message.audio.duration if message.audio else 0,
                                progress=progress_for_pyrogram,
                                progress_args=(f"Uploading #{current_file_number}", queue_message, time.time())
                            )

                    # Track the operation (only if not already processed)
                    batch_data["points_used"] += rename_cost
                    await track_rename_operation(
                        user_id=user_id,
                        original_name=file_name,
                        new_name=renamed_file_name,
                        points_deducted=rename_cost
                    )

                    # Delete queue message
                    await queue_message.delete()

                 # Check if this is part of a batch or single file
                if hasattr(message, 'media_group_id') and message.media_group_id:
                    # ✅ Track batch progress
                    file_processing_counters[user_id] = file_processing_counters.get(user_id, 0) + 1
                else:
                    # Single file - send single success message
                    await send_single_success_message(
                        client, message, file_name, renamed_file_name,
                        start_time, rename_cost, metadata_added
                    )
                
                    # Clean up if not in batch mode
                    if user_id in user_batch_trackers and not batch_data.get("is_batch"):
                        del user_batch_trackers[user_id]


                except BadRequest as e:
                    if "FILE_PART_INVALID" in str(e):
                        if attempt == max_upload_retries - 1:
                            raise
                        await asyncio.sleep(5 * (attempt + 1))
                        continue
                    raise
                except FloodWait as e:
                    await asyncio.sleep(e.value + 5)
                    await message.reply_text(f"⚠️ Flood wait: {e.value} seconds")
                    break
                except Exception as e:
                    if attempt == max_upload_retries - 1:
                        raise
                    await asyncio.sleep(5 * (attempt + 1))
                    continue

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

            # Decrement counter when done
            if user_id in file_processing_counters:
                file_processing_counters[user_id] -= 1
                if file_processing_counters[user_id] <= 0:
                    del file_processing_counters[user_id]

            # Deduct points (already handled in track_rename_operation)
            user_semaphore.release()

    except Exception as e:
        logger.error(f"Error in auto_rename_files: {e}")
        await message.reply_text("❌ An error occurred while processing your file. Please try again.")

@Client.on_message(filters.media_group & (filters.group | filters.private))
async def handle_media_group_completion(client: Client, message: Message):
    """Handle completion message for batch uploads"""
    try:
        user_id = message.from_user.id

        # If batch not tracked, skip
        if user_id not in user_batch_trackers:
            return

        batch_data = user_batch_trackers[user_id]
        if not batch_data.get("is_batch"):
            return

        expected_files = batch_data["count"]

        # Wait and poll until all files processed
        for _ in range(15):  # Max 15 x 2s = 30 seconds wait
            await asyncio.sleep(2)

            completed = file_processing_counters.get(user_id, 0)

            if completed >= expected_files:
                # All done!
                await send_completion_message(
                    client,
                    user_id,
                    batch_data["start_time"],
                    expected_files,
                    batch_data["points_used"]
                )

                # Cleanup
                file_processing_counters.pop(user_id, None)
                user_batch_trackers.pop(user_id, None)
                sequential_operations.pop(user_id, None)

                return  # All done

        # Timeout fallback
        await client.send_message(user_id, "✅ Batch finished but couldn't verify file count.")
        
        # Safe cleanup fallback
        file_processing_counters.pop(user_id, None)
        user_batch_trackers.pop(user_id, None)

    except Exception as e:
        logger.error(f"Error in handle_media_group_completion: {e}")
        try:
            await client.send_message(user_id, "✅ Batch finished but error showing stats.")
        except:
            pass


@Client.on_message(filters.command(["leaderboard", "top"]))
async def show_leaderboard(client: Client, message: Message):
    """Beautiful leaderboard with auto-deletion"""
    try:
        loading_msg = await message.reply_text("🔄 Loading leaderboard...")
        
        # Try to get leaderboard data with retry logic
        max_retries = 3
        leaderboard = []
        
        for attempt in range(max_retries):
            try:
                pipeline = [
                    {"$group": {"_id": "$user_id", "total_renames": {"$sum": 1}}},
                    {"$sort": {"total_renames": -1}},
                    {"$limit": 10}
                ]
                
                top_users = await hyoshcoder.file_stats.aggregate(pipeline).to_list(length=10)
                
                for user in top_users:
                    try:
                        # Get user details with proper error handling
                        user_data = await client.get_users(user["_id"])
                        username = user_data.username if user_data.username else user_data.first_name
                        leaderboard.append({
                            "user_id": user["_id"],
                            "username": username,
                            "renames": user["total_renames"]
                        })
                    except Exception as e:
                        logger.error(f"Error getting user data for {user['_id']}: {e}")
                        leaderboard.append({
                            "user_id": user["_id"],
                            "username": "Anonymous",
                            "renames": user["total_renames"]
                        })
                        continue
                
                break  # Success, exit retry loop
            except Exception as e:
                if attempt == max_retries - 1:
                    raise
                await asyncio.sleep(2 ** attempt)
                continue
        
        await loading_msg.delete()
        
        if not leaderboard:
            return await message.reply_text("No rename data available yet!")
        
        text = "✨ **Top 10 File Renamers** ✨\n\n"
        medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
        
        for i, user in enumerate(leaderboard, start=1):
            text += (
                f"{medals[i-1]} **#{i}:** "
                f"[@{user['username']}](tg://user?id={user['user_id']}) - "
                f"`{user['renames']} files`\n"
            )
        
        try:
            user_rank, user_renames = await get_user_rank(message.from_user.id)
            if user_rank:
                if user_rank > 10:
                    text += (
                        f"\n📊 **Your Rank:** #{user_rank}\n"
                        f"📝 **Your Renames:** {user_renames}\n"
                        f"➖ You need {leaderboard[-1]['renames'] - user_renames + 1} more to reach top 10!"
                    )
                else:
                    text += f"\n🎉 **You're in top 10!** Keep going!"
        except Exception as e:
            logger.error(f"Error getting user rank: {e}")
            text += "\n⚠️ Couldn't load your personal stats"

        # Send the full leaderboard to the chat where command was used
        msg = await message.reply_text(text, disable_web_page_preview=True)
        
        # Auto-delete after 1 minute
        await asyncio.sleep(60)
        try:
            await msg.delete()
        except:
            pass
        
    except Exception as e:
        logger.error(f"Error generating leaderboard: {e}")
        try:
            await loading_msg.delete()
        except:
            pass
        await message.reply_text("❌ Failed to load leaderboard. Please try again later.")
