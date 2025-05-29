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
from typing import Optional, Dict, List, Union, Tuple, AsyncGenerator, Any
import asyncio
import uuid
import shlex

# Global variables to manage operations
renaming_operations = {}
sequential_operations = {}
user_semaphores = {}
user_queue_messages = {}

def sanitize_filename(filename):
    """Sanitize filenames to remove problematic characters"""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", filename).strip()

async def get_user_semaphore(user_id):
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3)
    return user_semaphores[user_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id

    user_data = await hyoshcoder.read_user(user_id)
    if not user_data:
        return await message.reply_text("❌ Unable to load your information. Please type /start to register.")

    user_points = user_data.get("points", 0)
    format_template = user_data.get("format_template", "")
    media_preference = user_data.get("media_preference", "")
    sequential_mode = user_data.get("sequential_mode", False)
    src_info = await hyoshcoder.get_src_info(user_id)  

    if user_points < 1:
        return await message.reply_text("❌ You don't have enough balance to rename a file. Please recharge your points.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Free points", callback_data="free_points")]]))

    if not format_template:
        return await message.reply_text("Please first define an auto-rename format using /autorename")

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

    if file_id in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed_time < 10:
            return

    renaming_operations[file_id] = datetime.now()

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
        if user_id in user_queue_messages and user_queue_messages[user_id]:
            await user_queue_messages[user_id][0].edit_text(f"🔄 **Processing file:**\n➲ **Filename:** `{file_name}`")
            user_queue_messages[user_id].pop(0)
            
        if user_id not in sequential_operations:
            sequential_operations[user_id] = {"files": [], "expected_count": 0}

        sequential_operations[user_id]["expected_count"] += 1

        if episode_number or season:
            placeholders = [
                "episode", "Episode", "EPISODE", "{episode}",
                "season", "Season", "SEASON", "{season}"
            ]
            for placeholder in placeholders:
                if placeholder.lower() in ["episode", "{episode}"] and episode_number:
                    format_template = format_template.replace(placeholder, str(episode_number), 1)
                elif placeholder.lower() in ["season", "{season}"] and season:
                    format_template = format_template.replace(placeholder, str(season), 1)

            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in format_template:
                    if extracted_qualities == "Unknown":
                        await queue_message.edit_text("**Could not correctly extract the quality. Renaming with 'Unknown'...**")
                        del renaming_operations[file_id]
                        return

                    format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))

        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = sanitize_filename(f"{format_template}{file_extension}")
        renamed_file_path = os.path.join("downloads", renamed_file_name)
        metadata_file_path = os.path.join("Metadata", renamed_file_name)
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        file_uuid = str(uuid.uuid4())[:8]
        renamed_file_path_with_uuid = f"{renamed_file_path}_{file_uuid}"

        await queue_message.edit_text(f"📥 **Downloading:** `{file_name}`")

        max_retries = 3
        for attempt in range(max_retries):
            try:
                path = await client.download_media(
                    message,
                    file_name=renamed_file_path_with_uuid,
                    progress=progress_for_pyrogram,
                    progress_args=("Download in progress...", queue_message, time.time()),
                )
                break
            except Exception as e:
                if attempt == max_retries - 1:
                    del renaming_operations[file_id]
                    return await queue_message.edit_text(f"**Download error:** {e}")
                await asyncio.sleep(5 * (attempt + 1))

        await queue_message.edit_text(f"🔄 **Renaming and adding metadata:** `{file_name}`")

        try:
            os.rename(path, renamed_file_path)
            path = renamed_file_path

            metadata_added = False
            _bool_metadata = await hyoshcoder.get_metadata(user_id)
            if _bool_metadata:
                metadata = await hyoshcoder.get_metadata_code(user_id)
                if metadata:
                    cmd = [
                        'ffmpeg',
                        '-i', renamed_file_path,
                        '-map', '0',
                        '-c:s', 'copy',
                        '-c:a', 'copy', 
                        '-c:v', 'copy',
                        '-metadata', f'title={metadata}',
                        '-metadata', f'author={metadata}',
                        '-metadata:s:s', f'title={metadata}',
                        '-metadata:s:a', f'title={metadata}',
                        '-metadata:s:v', f'title={metadata}',
                        '-y',
                        metadata_file_path
                    ]

                    try:
                        process = await asyncio.create_subprocess_exec(
                            *cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE
                        )
                        
                        try:
                            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)
                        except asyncio.TimeoutError:
                            process.kill()
                            await process.communicate()
                            raise Exception("FFmpeg timed out after 2 minutes")
                        
                        if process.returncode != 0:
                            error_msg = stderr.decode().strip()
                            raise Exception(f"FFmpeg failed with error: {error_msg}")
                        
                        metadata_added = True
                        path = metadata_file_path
                    except Exception as e:
                        await queue_message.edit_text(f"❌ Metadata error: {str(e)}")
                        metadata_added = False
            if not metadata_added:
                await queue_message.edit_text("Adding metadata failed. Uploading renamed file.")
                path = renamed_file_path

            await queue_message.edit_text(f"📤 **Uploading:** `{file_name}`")
            await asyncio.sleep(5)  
            thumb_path = None
            custom_caption = await hyoshcoder.get_caption(message.chat.id)
            custom_thumb = await hyoshcoder.get_thumbnail(message.chat.id)

            if message.document:
                file_size = humanbytes(message.document.file_size)
                duration = convert(0)
            elif message.video:
                file_size = humanbytes(message.video.file_size)
                duration = convert(message.video.duration or 0)
            else:
                await queue_message.edit_text("Message doesn't contain supported document or video.")
                return

            caption = (
                custom_caption.format(
                    filename=renamed_file_name,
                    filesize=file_size,
                    duration=duration,
                )
                if custom_caption
                else f"**{renamed_file_name}**"
            )

            if custom_thumb:
                thumb_path = await client.download_media(custom_thumb)
            elif media_type == "video" and message.video.thumbs:
                thumb_path = await client.download_media(message.video.thumbs[0].file_id)

            if thumb_path:
                try:
                    img = Image.open(thumb_path).convert("RGB")
                    img = img.resize((320, 320))
                    img.save(thumb_path, "JPEG")
                except Exception as e:
                    print(f"Thumbnail processing error: {e}")

            # Removed chunk_size parameter as it's not supported in Pyrogram
            try:
                if sequential_mode:
                    log_message = await client.send_document(
                        settings.LOG_CHANNEL,
                        document=path,
                        thumb=thumb_path,
                        caption=caption,
                        progress=progress_for_pyrogram,
                        progress_args=("Upload in progress...", queue_message, time.time())
                    )
                    sequential_operations[user_id]["files"].append({
                        "message_id": log_message.id,
                        "file_name": renamed_file_name,
                        "season": season,
                        "episode": episode_number
                    })

                    if len(sequential_operations[user_id]["files"]) == sequential_operations[user_id]["expected_count"]:
                        sorted_files = sorted(
                            sequential_operations[user_id]["files"],
                            key=lambda x: (x["season"], x["episode"])
                        )

                        user_channel = await hyoshcoder.get_user_channel(user_id)
                        if not user_channel:
                            user_channel = user_id  

                        try:
                            await client.get_chat(user_channel)
                            for file_info in sorted_files:
                                await asyncio.sleep(3)
                                await client.copy_message(
                                    user_channel,
                                    settings.LOG_CHANNEL,
                                    file_info["message_id"]
                                )
                            await queue_message.reply_text(
                                f"✅ **All files have been sent to channel:** `{user_channel}`\n"
                                "If some files weren't completely sent, this is due to Telegram request flooding. "
                                "Please send these files to me individually."
                            )
                        except Exception as e:
                            await queue_message.reply_text(
                                f"❌ **Error: Channel {user_channel} is not accessible. {e}\n"
                            )
                            for file_info in sorted_files:
                                await asyncio.sleep(3)
                                await client.copy_message(
                                    user_id,
                                    settings.LOG_CHANNEL,
                                    file_info["message_id"]
                                )
                            await queue_message.reply_text("✅ **All files have been sent to your user ID.**")

                        del sequential_operations[user_id]
                else:
                    if media_type == "document":
                        await client.send_document(
                            message.chat.id,
                            document=path,
                            thumb=thumb_path,
                            caption=caption,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload in progress...", queue_message, time.time())
                        )
                    elif media_type == "video":
                        await client.send_video(
                            message.chat.id,
                            video=path,
                            caption=caption,
                            thumb=thumb_path,
                            duration=message.video.duration if message.video else 0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload in progress...", queue_message, time.time())
                        )
                    elif media_type == "audio":
                        await client.send_audio(
                            message.chat.id,
                            audio=path,
                            caption=caption,
                            thumb=thumb_path,
                            duration=message.audio.duration if message.audio else 0,
                            progress=progress_for_pyrogram,
                            progress_args=("Upload in progress...", queue_message, time.time())
                        )
            except FloodWait as e:
                await asyncio.sleep(e.value + 5)
                # You might want to add retry logic here
                raise
            except Exception as e:
                raise e

        except Exception as e:
            await queue_message.edit_text(f"❌ **Error:** {str(e)}")
            raise
        finally:
            try:
                if os.path.exists(renamed_file_path):
                    os.remove(renamed_file_path)
                if os.path.exists(metadata_file_path):
                    os.remove(metadata_file_path)
                if thumb_path and os.path.exists(thumb_path):
                    os.remove(thumb_path)
            except Exception as cleanup_error:
                print(f"Cleanup error: {cleanup_error}")

            await hyoshcoder.deduct_points(user_id, 1)
            if file_id in renaming_operations:
                del renaming_operations[file_id]
            
            try:
                await queue_message.delete()
            except:
                pass
    finally:
        user_semaphore.release()
