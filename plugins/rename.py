from pyrogram import Client, filters
from pyrogram.errors import FloodWait, MessageNotModified, BadRequest
from pyrogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image
from datetime import datetime, timedelta
import os
import time
import re
import pytz

import asyncio
import random
import shutil
from pyrogram.types import InputMediaPhoto
import uuid
import logging
from pyrogram.enums import ParseMode, ChatAction
import json
from typing import Optional, Tuple, Dict, List, Set
# Database imports
from database.data import hyoshcoder
from config import settings
from helpers.utils import progress_for_pyrogram, humanbytes, convert, extract_episode, extract_quality, extract_season
from pyrogram.errors import MessageNotModified, BadRequest
import html
from html import escape as html_escape

def escape_markdown(text: str) -> str:
    """Custom Markdown escaper for Telegram"""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return ''.join(f'\\{char}' if char in escape_chars else char for char in text)

def escape_html(text: str) -> str:
    """Escape text for HTML parse mode"""
    return html_escape(text, quote=False)
    
logger = logging.getLogger(__name__)

# Global variables to manage operations
user_file_queues = {}  # Tracks all files in queue per user
user_semaphores = {}   # Semaphores per user for concurrency control
renaming_operations = {}  # Tracks currently processing files
user_batch_trackers = {}  # Track batch operations per user
sequential_operations = {}  # For sequential mode
active_sequences = {}  # For sequence handling
cancel_operations = {}  # Track cancel requests
processed_files = set()  # Track processed files to prevent duplicate point deductions

# Sequence handling variables
active_sequences: Dict[int, List[Dict[str, str]]] = {}
sequence_message_ids: Dict[int, List[int]] = {}

def sanitize_metadata(metadata_text: str) -> str:
    """Sanitize metadata text to be FFmpeg-safe"""
    if not metadata_text:
        return ""
    # Replace problematic characters with underscore
    sanitized = re.sub(r'[\\/:*?"<>|\x00-\x1f]', '_', metadata_text)
    # Limit to 500 characters (FFmpeg has limits on metadata length)
    return sanitized[:500]

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
        user_semaphores[user_id] = asyncio.Semaphore(2)
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
    """Robust metadata addition with FFmpeg version fallbacks and detailed error handling"""
    try:
        # Sanitize metadata text
        safe_metadata = sanitize_metadata(metadata_text)
        if not safe_metadata:
            return False, "Empty metadata after sanitization"

        # First check if FFmpeg is available
        try:
            version_check = await asyncio.create_subprocess_exec(
                'ffmpeg', '-version',
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await version_check.wait()
            if version_check.returncode != 0:
                return False, "FFmpeg is not properly installed"
        except FileNotFoundError:
            return False, "FFmpeg not found on system"

        # Define strategies with version-specific approaches
        strategies = [
            # Strategy 1: Modern FFmpeg approach (v4.0+)
            [
                'ffmpeg',
                '-i', input_path,
                '-map', '0',
                '-c', 'copy',
                '-movflags', 'use_metadata_tags',
                '-metadata', f'title={safe_metadata}',
                '-metadata', f'comment={safe_metadata}',
                '-metadata', f'description={safe_metadata}',
                '-metadata:s:v:0', f'title=Video - {safe_metadata}',
                '-metadata:s:a:0', f'title=Audio - {safe_metadata}',
                '-metadata:s:s:0', f'title=Subs - {safe_metadata}',
                # Additional metadata from old version
                '-metadata', f'artist={safe_metadata}',
                '-metadata', f'author={safe_metadata}',
                '-metadata', f'encoded_by={safe_metadata}',
                '-metadata', f'custom_tag={safe_metadata}',
                '-y', 
                output_path
            ],
            # Strategy 2: Legacy compatible approach
            [
                'ffmpeg',
                '-i', input_path,
                '-map', '0',
                '-c:v', 'copy',
                '-c:a', 'copy',
                '-c:s', 'copy',
                '-metadata', f'title={safe_metadata}',
                '-y', output_path
            ],
            # Strategy 3: Minimal metadata only
            [
                'ffmpeg',
                '-i', input_path,
                '-c', 'copy',
                '-metadata', f'title={safe_metadata}',
                '-y', output_path
            ]
        ]

        # Try each strategy with enhanced error detection
        last_error = ""
        for strategy_num, cmd in enumerate(strategies, 1):
            try:
                # Log the attempt
                logging.info(f"Attempting Strategy {strategy_num}: {' '.join(cmd)}")
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                # Use a shorter timeout for faster fallthrough
                stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
                
                # Check results
                if process.returncode == 0:
                    if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                        return True, None
                    last_error = f"Strategy {strategy_num}: Empty output file"
                else:
                    error_msg = stderr.decode('utf-8', errors='replace') if stderr else "No error output"
                    last_error = f"Strategy {strategy_num} failed: {error_msg[:500]}"
                    logging.warning(last_error)

            except asyncio.TimeoutError:
                last_error = f"Strategy {strategy_num} timed out"
                logging.warning(last_error)
                continue
            except Exception as e:
                last_error = f"Strategy {strategy_num} error: {str(e)}"
                logging.warning(last_error)
                continue

        # Final fallback - try atomicparsley for MP4 files if available
        if output_path.lower().endswith('.mp4'):
            try:
                result = await asyncio.create_subprocess_exec(
                    'AtomicParsley',
                    input_path,
                    '--title', safe_metadata,
                    '--comment', safe_metadata,
                    '--description', safe_metadata,
                    '-o', output_path,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await result.wait()
                if result.returncode == 0:
                    return True, None
            except Exception as e:
                logging.info(f"AtomicParsley fallback failed: {str(e)}")

        return False, f"All strategies failed. Last error: {last_error}"

    except Exception as e:
        logging.error(f"Metadata addition crashed: {str(e)}", exc_info=True)
        return False, f"Critical error: {str(e)}"

async def send_to_dump_channel(
    client: Client,
    user_id: int,
    file_path: str,
    caption: str = "",
    thumb_path: Optional[str] = None,
    **kwargs
) -> bool:
    """
    Enhanced send to dump channel with better error handling and logging
    
    Args:
        client: Pyrogram Client
        user_id: User ID to lookup dump channel
        file_path: Path to media file
        caption: Caption text (max 1024 chars)
        thumb_path: Path to thumbnail image
        
    Returns:
        bool: True if successful, False otherwise
    """
    if not os.path.exists(file_path):
        logger.error(f"File not found: {file_path}")
        return False

    try:
        # Get dump channel from database
        dump_channel = await hyoshcoder.get_user_channel(user_id)
        if not dump_channel:
            logger.debug(f"No dump channel set for user {user_id}")
            return False

        # Verify channel exists and bot has permissions
        try:
            # Convert to integer and validate
            channel_id = int(dump_channel)
            if channel_id >= 0:
                logger.warning(f"Invalid channel ID format (must be negative): {dump_channel}")
                return False
                
            chat = await client.get_chat(channel_id)
            if chat.type not in ("channel", "supergroup"):
                logger.warning(f"Invalid chat type {chat.type} for {channel_id}")
                return False
                
            # Check bot permissions
            member = await client.get_chat_member(channel_id, client.me.id)
            if not member or not member.privileges or not member.privileges.can_post_messages:
                logger.warning(f"Bot lacks posting permissions in channel {channel_id}")
                return False
                
        except (ValueError, PeerIdInvalid) as e:
            logger.error(f"Invalid channel ID or can't access channel {dump_channel}: {e}")
            return False
        except Exception as e:
            logger.error(f"Can't access dump channel {dump_channel}: {e}")
            return False

        # Rest of the function remains the same...
        send_params = {
            "chat_id": channel_id,
            "caption": caption[:1024],
            "thumb": thumb_path if thumb_path and os.path.exists(thumb_path) else None,
            **kwargs
        }

        # Determine media type and send appropriately
        ext = os.path.splitext(file_path)[1].lower()
        
        try:
            if ext in ('.mp4', '.mkv', '.avi', '.mov', '.webm'):
                await client.send_video(
                    video=file_path,
                    supports_streaming=True,
                    **send_params
                )
            elif ext in ('.mp3', '.flac', '.m4a', '.wav', '.ogg'):
                await client.send_audio(
                    audio=file_path,
                    **send_params
                )
            elif ext in ('.jpg', '.jpeg', '.png', '.webp'):
                await client.send_photo(
                    photo=file_path,
                    **{k: v for k, v in send_params.items() if k != "thumb"}
                )
            else:
                await client.send_document(
                    document=file_path,
                    **send_params
                )
            
            logger.info(f"Successfully sent {file_path} to dump channel {channel_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send to dump channel: {e}")
            return False

    except Exception as e:
        logger.error(f"Unexpected error in send_to_dump_channel: {e}")
        return False

async def get_user_rank(user_id: int, time_range: str = "all") -> Tuple[Optional[int], int]:
    """Get user's global rank and total renames with time range support"""
    try:
        now = datetime.now()
        date_filter = {}
        
        if time_range == "day":
            date_filter = {"$gte": datetime(now.year, now.month, now.day)}
        elif time_range == "week":
            start_of_week = now - timedelta(days=now.weekday())
            date_filter = {"$gte": datetime(start_of_week.year, start_of_week.month, start_of_week.day)}
        elif time_range == "month":
            date_filter = {"$gte": datetime(now.year, now.month, 1)}
        
        pipeline = [
            {"$match": {"timestamp": date_filter}} if date_filter else {"$match": {}},
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
            f"⌬ Total Files Processed: {file_count}\n"
            f"⌬ Total Points Used: {points_used}\n"
            f"⌬ Points Remaining: {user_points}\n"
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
        
        elapsed_seconds = time.time() - start_time
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        
        if minutes > 0:
            time_taken_str = f"{minutes}m {seconds}s"
        else:
            time_taken_str = f"{seconds}s"

        remaining_points = (await hyoshcoder.get_points(message.from_user.id)) - rename_cost
        success_msg = (
            f"✅ 𝗙𝗶𝗹𝗲 𝗥𝗲𝗻𝗮𝗺𝗲𝗱 𝗦𝘂𝗰𝗰𝗲𝘀𝘀𝗳𝘂𝗹𝗹𝘆!\n\n"
            f"➲ 𝗢𝗿𝗶𝗴𝗶𝗻𝗮𝗹: `{file_name}`\n"
            f"➲ 𝗥𝗲𝗻𝗮𝗺𝗲𝗱: `{renamed_file_name}`\n"
            f"➲ 𝗧𝗶𝗺𝗲 𝗧𝗮𝗸𝗲𝗻: {time_taken_str}\n"
            f"➲ 𝗠𝗲𝘁𝗮𝗱𝗮𝘁𝗮 𝗔𝗱𝗱𝗲𝗱: {'𝗬𝗲𝘀' if metadata_added else '𝗡𝗼'}\n"
            f"➲ 𝗣𝗼𝗶𝗻𝘁𝘀 𝗨𝘀𝗲𝗱: {rename_cost}\n"
            f"➲ 𝗥𝗲𝗺𝗮𝗶𝗻𝗶𝗻𝗴 𝗣𝗼𝗶𝗻𝘁𝘀: {remaining_points}"
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

# SEQUENCE HANDLERS
@Client.on_message(filters.command(["ssequence", "startsequence"]))
async def start_sequence(client: Client, message: Message):
    """Start a file sequence collection"""
    user_id = message.from_user.id
    
    if settings.ADMIN_MODE and user_id not in settings.ADMINS:
        return await message.reply_text("**Admin mode is active - Only admins can use sequences!**")
        
    if user_id in active_sequences:
        return await message.reply_text("**A sequence is already active! Use /esequence to end it.**")
    
    active_sequences[user_id] = []
    sequence_message_ids[user_id] = []
    
    msg = await message.reply_text("**Sequence has been started! Send your files...**")
    sequence_message_ids[user_id].append(msg.id)
    
@Client.on_message(filters.command(["esequence", "endsequence"]))
async def end_sequence(client: Client, message: Message):
    """End a file sequence and send sorted files"""
    user_id = message.from_user.id
    
    if settings.ADMIN_MODE and user_id not in settings.ADMINS:
        return await message.reply_text("**Admin mode is active - Only admins can use sequences!**")
    
    if user_id not in active_sequences:
        return await message.reply_text("**No active sequence found!**\n**Use /ssequence to start one.**")

    # Start timer
    start_time = time.time()
    
    file_list = active_sequences.pop(user_id, [])
    delete_messages = sequence_message_ids.pop(user_id, [])

    if not file_list:
        return await message.reply_text("**No files received in this sequence!**")

    try:
        # Processing message with static text instead of animation
        processing_msg = await message.reply_text(
            "🔃 **Sorting and organizing your files...**\n"
            "Please wait while I process your sequence..."
        )

        # Extract metadata and sort files
        file_metadata = []
        missing_files = []
        for file in file_list:
            try:
                season = await extract_season(file["file_name"])
                episode = await extract_episode(file["file_name"])
                quality = await extract_quality(file["file_name"])
                file_metadata.append({
                    "file": file,
                    "season": season or "0",
                    "episode": episode or "0", 
                    "quality": quality or "unknown"
                })
            except Exception as e:
                missing_files.append(file["file_name"])
                logger.error(f"Error processing file {file['file_name']}: {e}")

        # Sort files
        sorted_files = sorted(
            file_metadata,
            key=lambda f: (f["season"], f["episode"], f["quality"])
        )
        
        # Calculate time taken
        time_taken = time.time() - start_time
        mins, secs = divmod(int(time_taken), 60)
        time_str = f"{mins}m {secs}s" if mins > 0 else f"{secs}s"

        # Delete processing message
        await processing_msg.delete()

        # Send files with delay to avoid flooding
        for file_data in sorted_files:
            if user_id in cancel_operations and cancel_operations[user_id]:
                await message.reply_text("❌ Sequence processing was canceled!")
                return

            try:
                file = file_data["file"]
                file_name = file['file_name'].replace('*', '×').replace('_', ' ').replace('`', "'")
                
                # Send file to user with simple caption
                await client.send_document(
                    message.chat.id,
                    file["file_id"],
                    caption=f'"{file_name}"'
                )
                
                # Send to dump channel if configured
                try:
                    dump_channel = await hyoshcoder.get_user_channel(user_id)
                    if dump_channel:
                        user = message.from_user
                        full_name = user.first_name
                        if user.last_name:
                            full_name += f" {user.last_name}"
                        username = f"@{user.username}" if user.username else "N/A"
                        
                        user_data = await hyoshcoder.read_user(user_id)
                        is_premium = user_data.get("is_premium", False) if user_data else False
                        premium_status = '🗸' if is_premium else '✘'

                        await client.send_document(
                            chat_id=dump_channel,
                            document=file["file_id"],
                            caption=(
                                f"<b>User Details</b>\n"
                                f"ID: <code>{user_id}</code>\n"
                                f"Name: {full_name}\n"
                                f"Username: {username}\n"
                                f"Premium: {premium_status}\n"
                                f"File: <code>{html.escape(file['file_name'])}</code>"
                            ),
                            parse_mode=ParseMode.HTML
                        )
                except Exception as e:
                    logger.error(f"Failed to send to dump channel: {e}")

                # Small delay between files (0.5-1.5 seconds)
                await asyncio.sleep(random.uniform(0.5, 1.5))
                
            except FloodWait as e:
                await asyncio.sleep(e.value + 1)
            except Exception as e:
                logger.error(f"Error sending file {file['file_name']}: {e}")
                missing_files.append(file['file_name'])

        # Prepare success message
        success_message = (
            f"🎉 **SEQUENCE COMPLETED** 🎉\n\n"
            f"▫️ **Total Files Sent:** `{len(sorted_files)}`\n"
            f"▫️ **Time Taken:** `{time_str}`\n"
        )

        # Add missing files info if any
        if missing_files:
            success_message += (
                f"\n❌ **Missing Files:** `{len(missing_files)}`\n"
                f"`{', '.join(missing_files[:3])}`"
            )
            if len(missing_files) > 3:
                success_message += f" +{len(missing_files)-3} more"

        # Send final success message after all files are sent
        await message.reply_text(success_message)

        # Clean up messages
        if delete_messages:
            try:
                await client.delete_messages(message.chat.id, delete_messages)
            except Exception as e:
                logger.error(f"Error deleting messages: {e}")

    except Exception as e:
        logger.error(f"Sequence processing failed: {e}")
        error_message = (
            "❌ **Failed to process sequence!**\n"
            "Please try again with fewer files or check your filenames."
        )
        # Avoid showing technical errors to users
        await message.reply_text(error_message)

@Client.on_message((filters.document | filters.video | filters.audio) & (filters.group | filters.private))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    start_time = time.time()
    
    # Initialize global variables if not exists
    global user_file_queues, user_semaphores, renaming_operations, file_processing_counters
    
    if 'file_processing_counters' not in globals():
        file_processing_counters = {}
    
    # Check if this is part of a sequence
    if user_id in active_sequences:
        if message.document:
            file_id = message.document.file_id
            file_name = message.document.file_name
        elif message.video:
            file_id = message.video.file_id
            file_name = f"{message.video.file_name}.mp4" if not message.video.file_name.endswith('.mp4') else message.video.file_name
        elif message.audio:
            file_id = message.audio.file_id
            file_name = f"{message.audio.file_name}.mp3" if not message.audio.file_name.endswith('.mp3') else message.audio.file_name

        file_info = {"file_id": file_id, "file_name": file_name if file_name else "Unknown"}
        active_sequences[user_id].append(file_info)
        await message.reply_text("File received in sequence...\nEnd sequence by using /esequence")
        return

    # Check for cancel request
    if user_id in cancel_operations and cancel_operations[user_id]:
        return

    # Initialize user's queue and counters if not exists
    if user_id not in user_file_queues:
        user_file_queues[user_id] = {
            'queue': [],
            'counter': 0,
            'is_processing': False,
            'batch_data': None
        }
    
    # Initialize batch tracker if media_group_id exists
    if getattr(message, 'media_group_id', None):
        if not user_file_queues[user_id]['batch_data']:
            user_file_queues[user_id]['batch_data'] = {
                "start_time": start_time,
                "count": 0,
                "points_used": 0,
                "is_batch": True
            }
        
        user_file_queues[user_id]['batch_data']["count"] += 1

    # Get file info
    file_info = {}
    if message.document:
        file_info = {
            'type': 'document',
            'file_id': message.document.file_id,
            'file_name': message.document.file_name,
            'size': message.document.file_size,
            'message': message,
            'media_type': 'document'
        }
    elif message.video:
        file_info = {
            'type': 'video',
            'file_id': message.video.file_id,
            'file_name': message.video.file_name or "",
            'size': message.video.file_size,
            'message': message,
            'media_type': 'video',
            'duration': message.video.duration if message.video else 0
        }
    elif message.audio:
        file_info = {
            'type': 'audio',
            'file_id': message.audio.file_id,
            'file_name': message.audio.file_name or "",
            'size': message.audio.file_size,
            'message': message,
            'media_type': 'audio',
            'duration': message.audio.duration if message.audio else 0
        }
    else:
        return await message.reply_text("Unsupported file type")

    # Add to queue and get position
    user_file_queues[user_id]['counter'] += 1
    queue_position = user_file_queues[user_id]['counter']
    file_info['queue_position'] = queue_position
    file_info['start_time'] = start_time
    user_file_queues[user_id]['queue'].append(file_info)

    # Send simplified queue confirmation
    try:
        await message.reply_text(f"📁 #{queue_position} - {file_info['file_name'] or 'Unknown'}")
    except Exception as e:
        logger.error(f"Error sending queue message: {e}")

    # Start processing if not already running
    if not user_file_queues[user_id]['is_processing']:
        user_file_queues[user_id]['is_processing'] = True
        asyncio.create_task(process_user_queue(client, user_id))

async def process_user_queue(client: Client, user_id: int):
    """Process all files in the user's queue with semaphore control"""
    # Initialize semaphore for this user if not exists
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(2)  # Allow 2 concurrent processes
    
    while user_file_queues.get(user_id, {}).get('queue'):
        async with user_semaphores[user_id]:
            file_info = user_file_queues[user_id]['queue'].pop(0)
            try:
                # Get user data for each file
                user_data = await hyoshcoder.read_user(user_id)
                if not user_data:
                    await file_info['message'].reply_text("❌ Unable to load your information. Please type /start to register.")
                    continue

                # Check sequential mode from database
                sequential_mode = user_data.get("sequential_mode", False)
                
                # Handle sequential mode
                if sequential_mode:
                    if user_id not in sequential_operations:
                        sequential_operations[user_id] = {"files": [], "expected_count": 0}

                    sequential_operations[user_id]["expected_count"] += 1
                    while len(sequential_operations[user_id]["files"]) > 0:
                        await asyncio.sleep(1)
                        if user_id in cancel_operations and cancel_operations[user_id]:
                            await file_info['message'].reply_text("❌ Processing canceled by user")
                            break

                await process_single_file(client, file_info, user_data)
                
                # Handle batch completion if this was the last file in a batch
                if (user_file_queues[user_id]['batch_data'] and 
                    len(user_file_queues[user_id]['queue']) == 0):
                    batch_data = user_file_queues[user_id]['batch_data']
                    await send_completion_message(
                        client,
                        user_id,
                        batch_data["start_time"],
                        batch_data["count"],
                        batch_data["points_used"]
                    )
                    user_file_queues[user_id]['batch_data'] = None
                
            except Exception as e:
                logger.error(f"Error processing file for {user_id}: {e}")
                try:
                    await file_info['message'].reply_text(f"❌ Error processing file: {str(e)[:500]}")
                except:
                    pass
    
    # Cleanup when done
    if user_id in user_file_queues:
        user_file_queues[user_id]['is_processing'] = False
        if len(user_file_queues[user_id]['queue']) == 0:
            del user_file_queues[user_id]

async def process_single_file(client: Client, file_info: dict, user_data: dict):
    """Process a single file with all the renaming logic"""
    message = file_info['message']
    user_id = message.from_user.id
    queue_position = file_info['queue_position']
    start_time = file_info['start_time']
    
    points_data = user_data.get("points", {})
    user_points = points_data.get("balance", 0)
    format_template = user_data.get("format_template", "")
    media_preference = user_data.get("media_preference", file_info['media_type'])
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

    # Check file size (2GB limit)
    if file_info['size'] > 2 * 1024 * 1024 * 1024:
        return await message.reply_text("ᴛʜᴇ ғɪʟᴇ ᴇxᴄᴇᴇᴅs 2GB. ᴘʟᴇᴀsᴇ sᴇɴᴅ ᴀ sᴍᴀʟʟᴇʀ ғɪʟᴇ ᴏʀ ᴍᴇᴅɪᴀ.")

    # Check for duplicate processing
    if file_info['file_id'] in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_info['file_id']]).seconds
        if elapsed_time < 10:
            return await message.reply_text("⚠️ Please wait for your current file operation to complete.")

    renaming_operations[file_info['file_id']] = datetime.now()

    # Extract metadata from filename/caption
    if src_info == "file_name":
        episode_number = await extract_episode(file_info['file_name'])
        season = await extract_season(file_info['file_name'])
        extracted_qualities = await extract_quality(file_info['file_name'])
    elif src_info == "caption":
        caption = message.caption if message.caption else ""
        episode_number = await extract_episode(caption)
        season = await extract_season(caption)
        extracted_qualities = await extract_quality(caption)
    else:
        episode_number = await extract_episode(file_info['file_name'])
        season = await extract_season(file_info['file_name'])
        extracted_qualities = await extract_quality(file_info['file_name'])

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
                    await message.reply_text("**Using 'Unknown' for quality**")
                    format_template = format_template.replace(quality_placeholder, "Unknown")
                else:
                    format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))

    # Prepare file paths
    _, file_extension = os.path.splitext(file_info['file_name'])
    renamed_file_name = sanitize_filename(f"{format_template}{file_extension}")
    renamed_file_path = os.path.join("downloads", renamed_file_name)
    metadata_file_path = os.path.join("Metadata", renamed_file_name)
    os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

    file_uuid = str(uuid.uuid4())[:8]
    temp_file_path = f"{renamed_file_path}_{file_uuid}"

    # Download file with retry logic
    max_download_retries = 1
    queue_message = None
    for attempt in range(max_download_retries):
        try:
            if user_id in cancel_operations and cancel_operations[user_id]:
                return await message.reply_text("❌ Processing canceled by user")

            queue_message = await message.reply_text(f"📥 Downloading #{queue_position}...")
            path = await client.download_media(
                message,
                file_name=temp_file_path,
                progress=progress_for_pyrogram,
                progress_args=(f"Downloading #{queue_position}", queue_message, time.time()),
            )
            break
        except Exception as e:
            if attempt == max_download_retries - 1:
                del renaming_operations[file_info['file_id']]
                return await message.reply_text(f"❌ Download failed: {e}")
            await asyncio.sleep(2 ** attempt)

    # Rename file
    try:
        os.rename(path, renamed_file_path)
        path = renamed_file_path
    except Exception as e:
        await message.reply_text(f"❌ Rename failed: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return

    # Add metadata if enabled
    metadata_added = False
    _bool_metadata = await hyoshcoder.get_metadata(user_id)
    if _bool_metadata:
        metadata = await hyoshcoder.get_metadata_code(user_id)
        if metadata:
            try:
                await queue_message.edit_text(f"🔄 Adding metadata to file #{queue_position}...")
            except:
                queue_message = await message.reply_text(f"🔄 Adding metadata to file #{queue_position}...")

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
                await message.reply_text(f"⚠️ Metadata failed: {error_msg}\nUsing original file")
                path = renamed_file_path

    # Prepare for upload
    try:
        await queue_message.edit_text(f"📤 Uploading #{queue_position}...")
    except:
        queue_message = await message.reply_text(f"📤 Uploading #{queue_position}...")

    thumb_path = None
    custom_caption = await hyoshcoder.get_caption(message.chat.id)
    custom_thumb = await hyoshcoder.get_thumbnail(message.chat.id)
    
    # Get file info
    file_size_human = humanbytes(file_info['size'])
    duration = convert(file_info.get('duration', 0))
    
    # Create caption
    if custom_caption:
        formatted_text = custom_caption.format(
            filename=html.escape(renamed_file_name),
            filesize=file_size_human,
            duration=duration
        )
        caption = f"""<b><blockquote>{formatted_text}</blockquote></b>"""
    else:
        caption = f"""<b><blockquote>{html.escape(renamed_file_name)}</blockquote></b>"""
    
    # Handle thumbnail
    if custom_thumb:
        thumb_path = await client.download_media(custom_thumb)
    elif file_info['media_type'] == "video" and hasattr(message.video, 'thumbs') and message.video.thumbs:
        thumb_path = await client.download_media(message.video.thumbs[0].file_id)
    elif file_info['media_type'] == "audio" and hasattr(message.audio, 'thumbs') and message.audio.thumbs:
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
    max_upload_retries = 3
    for attempt in range(max_upload_retries):
        try:
            if user_id in cancel_operations and cancel_operations[user_id]:
                await message.reply_text("❌ Processing canceled by user")
                return
    
            # Prepare common upload parameters
            common_params = {
                'caption': caption,
                'parse_mode': ParseMode.HTML,
                'thumb': thumb_path if thumb_path and os.path.exists(thumb_path) else None,
                'progress': progress_for_pyrogram,
                'progress_args': (f"Uploading #{queue_position}", queue_message, time.time())
            }
    
            # Try dump channel first if configured
            dump_success = False
            dump_channel = await hyoshcoder.get_user_channel(user_id)
            
            if dump_channel:
                try:
                    channel_id = int(dump_channel)
                    if channel_id < 0:  # Negative ID indicates a channel
                        chat = await client.get_chat(channel_id)
                        if chat.type in ("channel", "supergroup"):
                            member = await client.get_chat_member(channel_id, client.me.id)
                            if member and member.privileges and member.privileges.can_post_messages:
                                # Prepare dump channel caption
                                user = message.from_user
                                full_name = user.first_name
                                if user.last_name:
                                    full_name += f" {user.last_name}"
                                username = f"@{user.username}" if user.username else "N/A"
                                
                                user_data = await hyoshcoder.read_user(user_id)
                                is_premium = user_data.get("is_premium", False) if user_data else False
                                premium_status = '✅' if is_premium else '❌'
                                
                                dump_caption = (
                                    f"<b>File Details</b>\n"
                                    f"Name: <code>{html.escape(renamed_file_name)}</code>\n"
                                    f"Size: {humanbytes(file_info['size'])}\n"
                                )
                                
                                # Send to dump channel based on file type
                                if file_info['media_type'] == "document":
                                    await client.send_document(
                                        chat_id=channel_id,
                                        document=path,
                                        caption=dump_caption,
                                        thumb=common_params['thumb'],
                                        parse_mode=ParseMode.HTML
                                    )
                                    dump_success = True
                                elif file_info['media_type'] == "video":
                                    await client.send_video(
                                        chat_id=channel_id,
                                        video=path,
                                        caption=dump_caption,
                                        thumb=common_params['thumb'],
                                        duration=file_info.get('duration', 0),
                                        supports_streaming=True,
                                        parse_mode=ParseMode.HTML
                                    )
                                    dump_success = True
                                elif file_info['media_type'] == "audio":
                                    await client.send_audio(
                                        chat_id=channel_id,
                                        audio=path,
                                        caption=dump_caption,
                                        thumb=common_params['thumb'],
                                        duration=file_info.get('duration', 0),
                                        parse_mode=ParseMode.HTML
                                    )
                                    dump_success = True
                                    
                                if dump_success:
                                    try:
                                        await queue_message.edit_text(f"✅ File #{queue_position} sent to dump channel!")
                                    except:
                                        pass
                except Exception as e:
                    logger.error(f"Error sending to dump channel: {e}")
                    dump_success = False
    
            # If dump channel not set or failed, send to original chat
            if not dump_success:
                if file_info['media_type'] == "document":
                    await client.send_document(
                        chat_id=message.chat.id,
                        document=path,
                        **common_params
                    )
                elif file_info['media_type'] == "video":
                    await client.send_video(
                        chat_id=message.chat.id,
                        video=path,
                        duration=file_info.get('duration', 0),
                        supports_streaming=True,
                        **common_params
                    )
                elif file_info['media_type'] == "audio":
                    await client.send_audio(
                        chat_id=message.chat.id,
                        audio=path,
                        duration=file_info.get('duration', 0),
                        **common_params
                    )
    
            # Track successful operation
            await track_rename_operation(
                user_id=user_id,
                original_name=file_info['file_name'],
                new_name=renamed_file_name,
                points_deducted=rename_cost
            )
    
            # Update batch tracking if applicable
            if user_file_queues.get(user_id, {}).get('batch_data'):
                user_file_queues[user_id]['batch_data']["points_used"] += rename_cost
    
            # Send success message for single files
            if not user_file_queues.get(user_id, {}).get('batch_data'):
                await send_single_success_message(
                    client, message, file_info['file_name'], renamed_file_name,
                    start_time, rename_cost, metadata_added
                )
    
            break  # Success - exit retry loop
    
        except FloodWait as e:
            await asyncio.sleep(e.value + 5)
            await message.reply_text(f"⚠️ Flood wait: {e.value} seconds")
            continue
        except BadRequest as e:
            if "FILE_PART_INVALID" in str(e) and attempt < max_upload_retries - 1:
                await asyncio.sleep(5 * (attempt + 1))
                continue
            await message.reply_text(f"❌ Upload failed: {str(e)[:200]}")
            raise
        except Exception as e:
            logger.error(f"Upload attempt {attempt + 1} failed: {e}")
            if attempt == max_upload_retries - 1:
                await message.reply_text("❌ Failed after multiple retries")
                raise
            await asyncio.sleep(5 * (attempt + 1))
            continue

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
        if queue_message:
            try:
                await queue_message.delete()
            except:
                pass
    except Exception as e:
        logger.error(f"Cleanup error: {e}")

    if file_info['file_id'] in renaming_operations:
        del renaming_operations[file_info['file_id']]

@Client.on_message(filters.media_group & (filters.group | filters.private))
async def handle_media_group_completion(client: Client, message: Message):
    """Handle completion message for batch uploads"""
    try:
        user_id = message.from_user.id

        # If batch not tracked, skip
        if user_id not in user_file_queues or not user_file_queues[user_id].get('batch_data'):
            return

        batch_data = user_file_queues[user_id]['batch_data']
        if not batch_data.get("is_batch"):
            return

        # Send completion message
        await send_completion_message(
            client,
            user_id,
            batch_data["start_time"],
            batch_data["count"],
            batch_data["points_used"]
        )

        # Cleanup
        user_file_queues[user_id]['batch_data'] = None
        if user_id in sequential_operations:
            sequential_operations.pop(user_id)

    except Exception as e:
        logger.error(f"Error in handle_media_group_completion: {e}")
        try:
            await client.send_message(user_id, "✅ Batch finished but error showing stats.")
        except:
            pass

@Client.on_message(filters.command("cancel"))
async def cancel_processing(client: Client, message: Message):
    """Cancel current processing operations"""
    user_id = message.from_user.id
    cancel_operations[user_id] = True
    
    # Clean up any ongoing operations
    if user_id in user_file_queues:
        user_file_queues[user_id]['queue'] = []
        if 'batch_data' in user_file_queues[user_id]:
            user_file_queues[user_id]['batch_data'] = None
    
    if user_id in sequential_operations:
        sequential_operations[user_id]["files"] = []
    
    await message.reply_text("🛑 Cancel request received. Current operations will be stopped after completing current file.")

# LEADERBOARD HANDLERS
@Client.on_message(filters.command(["leaderboard", "top"]))
async def show_leaderboard(client: Client, message: Message):
    """Beautiful leaderboard with auto-deletion"""
    try:
        loading_msg = await message.reply_text("🔄 𝗟𝗼𝗮𝗱𝗶𝗻𝗴 𝗹𝗲𝗮𝗱𝗲𝗿𝗯𝗼𝗮𝗿𝗱...")
        
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
# SCREENSHOT GENERATOR (MAX 4K)

async def generate_screenshots(video_path: str, output_dir: str, count: int = 10) -> List[str]:
    """Generate screenshots at the video's native resolution using ffmpeg."""
    try:
        os.makedirs(output_dir, exist_ok=True)

        # Get duration
        probe_duration = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error',
            '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1',
            video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, _ = await probe_duration.communicate()
        duration = float(stdout.decode().strip())

        # Get resolution
        probe_resolution = await asyncio.create_subprocess_exec(
            'ffprobe', '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'stream=width,height',
            '-of', 'csv=p=0:s=x',
            video_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        res_out, _ = await probe_resolution.communicate()
        resolution = res_out.decode().strip()
        logger.info(f"Detected video resolution: {resolution}")

        # Even timestamps
        start = duration * 0.05
        end = duration * 0.95
        interval = (end - start) / count
        timestamps = [start + i * interval for i in range(count)]

        screenshots = []

        for i, timestamp in enumerate(timestamps):
            output_path = os.path.join(output_dir, f"screenshot_{i+1}.jpg")
            cmd = [
                'ffmpeg',
                '-ss', str(timestamp),
                '-i', video_path,
                '-vframes', '1',
                '-q:v', '2',  # High quality
                '-y',
                output_path
            ]
            process = await asyncio.create_subprocess_exec(*cmd,
                                                           stdout=asyncio.subprocess.DEVNULL,
                                                           stderr=asyncio.subprocess.DEVNULL)
            await process.wait()

            if os.path.exists(output_path):
                screenshots.append(output_path)

        return screenshots

    except Exception as e:
        logger.error(f"Error generating screenshots: {e}")
        return []

@Client.on_message(filters.command("ss"))
async def generate_screenshots_command(client: Client, message: Message):
    """Generate and send clean, full-res screenshots from a video."""
    temp_dir = None
    try:
        if not message.reply_to_message or not (
            message.reply_to_message.video or message.reply_to_message.document
        ):
            return await message.reply_text("📎 Please reply to a video file to generate screenshots.")

        user_id = message.from_user.id
        media = message.reply_to_message.video or message.reply_to_message.document

        # Check user points
        points_config = await hyoshcoder.get_config("points_config", {})
        screenshot_cost = points_config.get("screenshot_cost", 5)
        user_points = await hyoshcoder.get_points(user_id)

        if user_points < screenshot_cost:
            return await message.reply_text(
                f"❌ You need {screenshot_cost} points to generate screenshots!",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("💎 Free Points", callback_data="freepoints")]
                ])
            )

        processing_msg = await message.reply_text("🔄 Downloading and processing video...")

        # Prepare temp directory
        temp_dir = f"temp_screenshots_{user_id}_{int(time.time())}"
        os.makedirs(temp_dir, exist_ok=True)
        video_path = os.path.join(temp_dir, "video.mp4")

        # Download the video
        await client.download_media(media, file_name=video_path)

        await processing_msg.edit_text("🖼 Generating screenshots at original video resolution...")

        # Generate screenshots
        screenshot_paths = await generate_screenshots(video_path, temp_dir)

        if not screenshot_paths:
            await processing_msg.edit_text("❌ Failed to generate screenshots.")
            return

        # Send photo album without captions
        media_group = [
            InputMediaPhoto(media=path) for path in screenshot_paths[:10]
        ]

        await client.send_media_group(
            chat_id=message.chat.id,
            media=media_group
        )

        # Deduct points
        await hyoshcoder.users.update_one(
            {"_id": user_id},
            {"$inc": {"points.balance": -screenshot_cost}}
        )

        await processing_msg.edit_text(
            f"✅ {len(screenshot_paths)} full-resolution screenshots sent! (-{screenshot_cost} points)"
        )

    except Exception as e:
        logger.error(f"Error in screenshot command: {e}")
        await message.reply_text("❌ An error occurred while processing your request.")
    finally:
        try:
            if temp_dir and os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as cleanup_error:
            logger.warning(f"Cleanup failed: {cleanup_error}")
