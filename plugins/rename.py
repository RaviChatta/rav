from pyrogram import Client, filters
from pyrogram.errors import FloodWait
from pyrogram.types import InputMediaDocument, Message, InlineKeyboardButton, InlineKeyboardMarkup
from PIL import Image
from datetime import datetime
from hachoir.metadata import extractMetadata
from hachoir.parser import createParser
from helpers.utils import progress_for_pyrogram, humanbytes, convert, extract_episode, extract_quality, extract_season
from database.data import hyoshcoder
from config import settings
import os
import time
import re
import subprocess
import asyncio
import uuid
import shlex
import logging
# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Animation emojis
ANIMATION_EMOJIS = ["🔄", "⚡", "✨", "🌟", "🎬", "📁", "📂", "🔍", "📊", "📈"]

# Global variables to manage operations
renaming_operations = {}
sequential_operations = {}
user_semaphores = {}
user_queue_messages = {}

def sanitize_filename(filename: str) -> str:
    """Sanitize filenames to remove problematic characters"""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename).strip()

async def animate_message(message: Message, text: str, delay: float = 0.3):
    """Animate message with rotating emojis"""
    base_text = text
    for emoji in ANIMATION_EMOJIS:
        try:
            await message.edit_text(f"{emoji} {base_text}")
            await asyncio.sleep(delay)
        except:
            break
    await message.edit_text(f"✅ {base_text}")

async def get_user_semaphore(user_id: int) -> asyncio.Semaphore:
    """Get or create semaphore for user"""
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3)
    return user_semaphores[user_id]

async def add_comprehensive_metadata(input_path: str, output_path: str, metadata_text: str) -> Tuple[bool, Optional[str]]:
    """Enhanced metadata addition with support for all streams"""
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
        ]
    ]

    for cmd in metadata_cmds:
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
        except Exception as e:
            error_msg = str(e)
    
    return False, error_msg

async def send_to_dump_channel(client: Client, user_id: int, file_path: str, caption: str, thumb_path: Optional[str] = None) -> bool:
    """Enhanced dump channel sender with animations"""
    try:
        dump_channel = await hyoshcoder.get_user_channel(user_id)
        if not dump_channel:
            return False

        # Convert channel ID to integer if it's string
        try:
            if isinstance(dump_channel, str):
                dump_channel = int(dump_channel)
        except ValueError:
            logger.error(f"Invalid dump channel format: {dump_channel}")
            return False

        # Check channel accessibility with animation
        status_msg = await client.send_message(user_id, "🔍 Checking dump channel...")
        await animate_message(status_msg, "Checking dump channel access")

        try:
            chat = await client.get_chat(dump_channel)
            if chat.type not in ["channel", "supergroup"]:
                await status_msg.edit_text("❌ Dump channel is not valid")
                return False
        except Exception as e:
            await status_msg.edit_text(f"❌ Can't access dump channel: {e}")
            return False

        # Determine file type with animation
        await status_msg.edit_text("🔍 Detecting file type...")
        ext = os.path.splitext(file_path)[1].lower()
        
        # Send with appropriate method and animations
        await status_msg.edit_text("🚀 Sending to dump channel...")
        try:
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
            await status_msg.edit_text("✅ Successfully sent to dump channel!")
            await asyncio.sleep(2)
            await status_msg.delete()
            return True
        except Exception as e:
            await status_msg.edit_text(f"❌ Failed to send to dump channel: {e}")
            await asyncio.sleep(3)
            await status_msg.delete()
            return False
    except Exception as e:
        logger.error(f"Unexpected error in dump channel: {e}", exc_info=True)
        return False

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client: Client, message: Message):
    user_id = message.from_user.id
    start_time = time.time()

    # Get user data with animation
    status_msg = await message.reply_text("🔍 Checking your account...")
    await animate_message(status_msg, "Checking your account")

    user_data = await hyoshcoder.read_user(user_id)
    if not user_data:
        await status_msg.edit_text("❌ Account not found. Please /start")
        return

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
        await status_msg.edit_text(
            f"❌ You need {rename_cost} points (have {user_points})",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Get Points", callback_data="freepoints")]])
        )
        return

    if not format_template:
        await status_msg.edit_text("ℹ️ Please set rename format with /autorename")
        return

    # File type handling with animation
    await animate_message(status_msg, "Checking file type")
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
        await status_msg.edit_text("❌ Unsupported file type")
        return

    # Check for duplicate processing
    if file_id in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed_time < 10:
            await status_msg.edit_text("⚠️ This file is already being processed")
            return

    renaming_operations[file_id] = datetime.now()

    # Extract metadata with animation
    await animate_message(status_msg, "Extracting file info")
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
    await animate_message(status_msg, "Applying your format")
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
                format_template = format_template.replace(quality_placeholder, extracted_qualities or "Unknown")

    # Prepare file paths
    _, file_extension = os.path.splitext(file_name)
    renamed_file_name = sanitize_filename(f"{format_template}{file_extension}")
    renamed_file_path = os.path.join("downloads", renamed_file_name)
    metadata_file_path = os.path.join("Metadata", renamed_file_name)
    os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
    os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

    # Download with progress animation
    await animate_message(status_msg, "Downloading your file")
    temp_file_path = f"{renamed_file_path}_{uuid.uuid4().hex[:8]}"
    try:
        path = await client.download_media(
            message,
            file_name=temp_file_path,
            progress=progress_for_pyrogram,
            progress_args=("⬇️ Downloading...", status_msg, time.time()),
        )
    except Exception as e:
        del renaming_operations[file_id]
        await status_msg.edit_text(f"❌ Download failed: {e}")
        return

    # Rename file
    try:
        os.rename(path, renamed_file_path)
        path = renamed_file_path
    except Exception as e:
        await status_msg.edit_text(f"❌ Rename failed: {e}")
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
        return

    # Add metadata with animation
    metadata_added = False
    _bool_metadata = await hyoshcoder.get_metadata(user_id)
    if _bool_metadata:
        metadata = await hyoshcoder.get_metadata_code(user_id)
        if metadata:
            await animate_message(status_msg, "Adding metadata")
            success, error = await add_comprehensive_metadata(
                renamed_file_path,
                metadata_file_path,
                metadata
            )
            
            if success:
                metadata_added = True
                path = metadata_file_path
            else:
                await status_msg.edit_text(f"⚠️ Metadata failed: {error[:200]}...")
                path = renamed_file_path

    # Prepare for upload
    await animate_message(status_msg, "Preparing upload")
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

    caption = custom_caption.format(
        filename=renamed_file_name,
        filesize=file_size,
        duration=duration,
    ) if custom_caption else f"**{renamed_file_name}**"

    # Handle thumbnail with animation
    if custom_thumb or (media_type == "video" and message.video.thumbs) or (media_type == "audio" and message.audio.thumbs):
        await animate_message(status_msg, "Processing thumbnail")
        try:
            thumb_path = await client.download_media(
                custom_thumb or 
                (message.video.thumbs[0].file_id if media_type == "video" else None) or
                (message.audio.thumbs[0].file_id if media_type == "audio" else None)
            )
            with Image.open(thumb_path) as img:
                img = img.convert("RGB")
                img.thumbnail((320, 320))
                img.save(thumb_path, "JPEG", quality=85)
        except Exception as e:
            logger.warning(f"Thumbnail error: {e}")
            thumb_path = None

    # Upload flow with animations
    try:
        # Try dump channel first if set
        dump_channel = await hyoshcoder.get_user_channel(user_id)
        dump_success = False
        if dump_channel:
            await animate_message(status_msg, "Sending to dump channel")
            dump_success = await send_to_dump_channel(
                client,
                user_id,
                path,
                caption,
                thumb_path
            )
            
        # Normal upload if dump failed or not set
        if not dump_success:
            await animate_message(status_msg, "Uploading to chat")
            if media_type == "document":
                await client.send_document(
                    message.chat.id,
                    document=path,
                    thumb=thumb_path,
                    caption=caption,
                    progress=progress_for_pyrogram,
                    progress_args=("⬆️ Uploading...", status_msg, time.time())
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
                    progress_args=("⬆️ Uploading...", status_msg, time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    message.chat.id,
                    audio=path,
                    caption=caption,
                    thumb=thumb_path,
                    duration=message.audio.duration if message.audio else 0,
                    progress=progress_for_pyrogram,
                    progress_args=("⬆️ Uploading...", status_msg, time.time())
                )

        # Calculate remaining points
        remaining_points = (await hyoshcoder.get_points(user_id)) - rename_cost
        
        # Final success message with animation
        time_taken = time.time() - start_time
        success_msg = (
            f"🎉 **Successfully Processed!**\n\n"
            f"▸ **Original:** `{file_name}`\n"
            f"▸ **Renamed:** `{renamed_file_name}`\n"
            f"▸ **Time:** {time_taken:.1f} seconds\n"
            f"▸ **Size:** {file_size}\n"
            f"▸ **Metadata:** {'✅' if metadata_added else '❌'}\n"
            f"▸ **Dump Channel:** {'✅' if dump_success else '❌'}\n"
            f"▸ **Points Used:** {rename_cost}\n"
            f"▸ **Remaining Points:** {remaining_points}\n\n"
            f"⚡ Thank you for using our service!"
        )
        
        # Animate the success message
        success_message = await message.reply_text("🔄 Preparing your results...")
        await animate_message(success_message, "Preparing your results")
        await success_message.edit_text(success_msg)

    except FloodWait as e:
        await status_msg.edit_text(f"⏳ Please wait {e.value} seconds due to flood limits")
        await asyncio.sleep(e.value)
    except Exception as e:
        await status_msg.edit_text(f"❌ Upload failed: {e}")
        logger.error(f"Upload error: {e}", exc_info=True)
    finally:
        # Cleanup files
        cleanup_files = [
            renamed_file_path,
            metadata_file_path,
            thumb_path,
            temp_file_path
        ]
        for file_path in cleanup_files:
            try:
                if file_path and os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                logger.warning(f"Couldn't delete {file_path}: {e}")

        # Release operation lock
        if file_id in renaming_operations:
            del renaming_operations[file_id]
        
        # Delete status message
        try:
            await status_msg.delete()
        except:
            pass

        # Deduct points
        try:
            await hyoshcoder.deduct_points(user_id, rename_cost)
        except Exception as e:
            logger.error(f"Points deduction error: {e}")
