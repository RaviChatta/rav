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

renaming_operations = {}
secantial_operations = {}
user_semaphores = {}

async def get_user_semaphore(user_id):
    if user_id not in user_semaphores:
        user_semaphores[user_id] = asyncio.Semaphore(3) 
    return user_semaphores[user_id]

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def auto_rename_files(client, message):
    user_id = message.from_user.id
    user_points = await hyoshcoder.get_points(user_id)
    format_template = await hyoshcoder.get_format_template(user_id)
    media_preference = await hyoshcoder.get_media_preference(user_id)
    sequential_mode = await hyoshcoder.get_sequential_mode(user_id)

    if user_points < 1:
        return await message.reply_text("❌ Vous n'avez pas assez de points pour renommer un fichier. Rechargez vos points.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Free points", callback_data="free_points")]]))

    if not format_template:
        return await message.reply_text(
            "ᴠᴇᴜɪʟʟᴇᴢ ᴅ'ᴀʙᴏʀᴅ ᴅᴇ́ғɪɴɪʀ ᴜɴ ғᴏʀᴍᴀᴛ ᴅᴇ ʀᴇɴᴏᴍᴍᴀɢᴇ ᴀᴜᴛᴏᴍᴀᴛɪǫᴜᴇ ᴇɴ ᴜᴛɪʟɪsᴀɴᴛ /autorename"
        )

    if message.document:
        file_id = message.document.file_id
        file_name = message.document.file_name
        media_type = media_preference or "document"
    elif message.video:
        file_id = message.video.file_id
        file_name = f"{message.video.file_name}.mp4"
        media_type = media_preference or "video"
    elif message.audio:
        file_id = message.audio.file_id
        file_name = f"{message.audio.file_name}.mp3"
        media_type = media_preference or "audio"
    else:
        return await message.reply_text("Unsupported File Type")

    if file_id in renaming_operations:
        elapsed_time = (datetime.now() - renaming_operations[file_id]).seconds
        if elapsed_time < 10:
            return

    renaming_operations[file_id] = datetime.now()

    user_semaphore = await get_user_semaphore(user_id)
    await user_semaphore.acquire()

    try:
        if user_id not in secantial_operations:
            secantial_operations[user_id] = {"files": [], "expected_count": 0}

        secantial_operations[user_id]["expected_count"] += 1

        episode_number = await extract_episode(file_name)
        saison = await extract_season(file_name)
        if episode_number or saison:
            placeholders = [
                "episode", "Episode", "EPISODE", "{episode}",
                "saison", "Saison", "SAISON", "{saison}"
            ]
            for placeholder in placeholders:
                if placeholder.lower() in ["episode", "{episode}"] and episode_number:
                    format_template = format_template.replace(placeholder, str(episode_number), 1)
                elif placeholder.lower() in ["saison", "{saison}"] and saison:
                    format_template = format_template.replace(placeholder, str(saison), 1)

            quality_placeholders = ["quality", "Quality", "QUALITY", "{quality}"]
            for quality_placeholder in quality_placeholders:
                if quality_placeholder in format_template:
                    extracted_qualities = await extract_quality(file_name)
                    if extracted_qualities == "Unknown":
                        await message.reply_text("**ᴊᴇ ɴ'ᴀɪ ᴘᴀs ᴘᴜ ᴇxᴛʀᴀɪʀᴇ ʟᴀ ǫᴜᴀʟɪᴛᴇ́ ᴄᴏʀʀᴇᴄᴛᴇᴍᴇɴᴛ. ʀᴇɴᴏᴍᴍᴀɢᴇ ᴇɴ 'Unknown'...**")
                        del renaming_operations[file_id]
                        return

                    format_template = format_template.replace(quality_placeholder, "".join(extracted_qualities))

        _, file_extension = os.path.splitext(file_name)
        renamed_file_name = f"{format_template}{file_extension}"
        renamed_file_path = f"downloads/{renamed_file_name}"
        metadata_file_path = f"Metadata/{renamed_file_name}"
        os.makedirs(os.path.dirname(renamed_file_path), exist_ok=True)
        os.makedirs(os.path.dirname(metadata_file_path), exist_ok=True)

        file_uuid = str(uuid.uuid4())[:8]
        renamed_file_path_with_uuid = f"{renamed_file_path}_{file_uuid}"

        download_msg = await message.reply_text("**__ᴛᴇʟᴇ́ᴄʜᴀʀɢᴇᴍᴇɴᴛ...__**")

        try:
            path = await client.download_media(
                message,
                file_name=renamed_file_path_with_uuid,
                progress=progress_for_pyrogram,
                progress_args=("ᴛᴇʟᴇ́ᴄʜᴀʀɢᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", download_msg, time.time()),
            )
        except Exception as e:
            del renaming_operations[file_id]
            return await download_msg.edit(f"**ᴇʀʀᴇᴜʀ ᴅᴇ ᴛᴇʟᴇ́ᴄʜᴀʀɢᴇᴍᴇɴᴛ:** {e}")

        await download_msg.edit("**__ʀᴇɴᴏᴍᴍᴀɢᴇ ᴇᴛ ᴀᴊᴏᴜᴛ ᴅᴇ ᴍᴇ́ᴛᴀᴅᴏɴɴᴇ́ᴇs...__**")

        try:
            os.rename(path, renamed_file_path)
            path = renamed_file_path

            metadata_added = False
            _bool_metadata = await hyoshcoder.get_metadata(user_id)
            if _bool_metadata:
                metadata = await hyoshcoder.get_metadata_code(user_id)
                if metadata:
                    cmd = f'ffmpeg -i "{renamed_file_path}"  -map 0 -c:s copy -c:a copy -c:v copy -metadata title="{metadata}" -metadata author="{metadata}" -metadata:s:s title="{metadata}" -metadata:s:a title="{metadata}" -metadata:s:v title="{metadata}"  "{metadata_file_path}"'
                    try:
                        process = await asyncio.create_subprocess_shell(
                            cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                        )
                        stdout, stderr = await process.communicate()
                        if process.returncode == 0:
                            metadata_added = True
                            path = metadata_file_path
                        else:
                            error_message = stderr.decode()
                            await download_msg.edit(f"**ᴇʀʀᴇᴜʀ ᴅᴇ ᴍᴇ́ᴛᴀᴅᴏɴɴᴇ́ᴇs:**\n{error_message}")
                    except asyncio.TimeoutError:
                        await download_msg.edit("**ᴄᴏᴍᴍᴀɴᴅᴇ ғғᴍᴘᴇɢ ᴇxᴘɪʀᴇ́ᴇ.**")
                        return
                    except Exception as e:
                        await download_msg.edit(f"**ᴜɴᴇ ᴇxᴄᴇᴘᴛɪᴏɴ s'ᴇsᴛ ᴘʀᴏᴅᴜɪᴛᴇ:**\n{str(e)}")
                        return
            else:
                metadata_added = True

            if not metadata_added:
                await download_msg.edit(
                    "L'ᴀᴊᴏᴜᴛ ᴅᴇs mᴇ́ᴛᴀᴅᴏɴɴᴇᴇs ᴀ ᴇ́ᴄʜᴏᴜᴇ́. ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ ᴅᴜ ғɪᴄʜɪᴇʀ ʀᴇɴᴏᴍᴍᴇ́."
                )
                path = renamed_file_path

            upload_msg = await download_msg.edit("**__ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ...__**")

            ph_path = None
            c_caption = await hyoshcoder.get_caption(message.chat.id)
            c_thumb = await hyoshcoder.get_thumbnail(message.chat.id)

            if message.document:
                file_size = humanbytes(message.document.file_size)
                duration = convert(0)
            elif message.video:
                file_size = humanbytes(message.video.file_size)
                duration = convert(message.video.duration or 0)
            else:
                await message.reply("Le message ne contient pas de document ou de vidéo pris en charge.")
                return

            caption = (
                c_caption.format(
                    filename=renamed_file_name,
                    filesize=file_size,
                    duration=duration,
                )
                if c_caption
                else f"**{renamed_file_name}**"
            )

            if c_thumb:
                ph_path = await client.download_media(c_thumb)
            elif media_type == "video" and message.video.thumbs:
                ph_path = await client.download_media(message.video.thumbs[0].file_id)

            if ph_path:
                img = Image.open(ph_path).convert("RGB")
                img = img.resize((320, 320))
                img.save(ph_path, "JPEG")

            try:
                if sequential_mode:
                    log_message = await client.send_document(
                        settings.LOG_CHANNEL,
                        document=path,
                        thumb=ph_path,
                        caption=caption,
                        progress=progress_for_pyrogram,
                        progress_args=("ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", upload_msg, time.time()),
                    )
                    secantial_operations[user_id]["files"].append({
                        "message_id": log_message.id,
                        "file_name": renamed_file_name,
                        "season": saison,
                        "episode": episode_number
                    })

                    if len(secantial_operations[user_id]["files"]) == secantial_operations[user_id]["expected_count"]:
                        sorted_files = sorted(
                            secantial_operations[user_id]["files"],
                            key=lambda x: (x["season"], x["episode"])
                        )

                        user_channel = await hyoshcoder.get_user_channel(user_id)
                        if not user_channel:
                            user_channel = user_id  
                        try:
                            await client.get_chat(user_channel)  
                            for file_info in sorted_files:
                                print(f"Copie du fichier {file_info['file_name']} vers le canal {user_channel}")
                                await client.copy_message(
                                    user_channel,
                                    settings.LOG_CHANNEL,
                                    file_info["message_id"]
                                )
                            await message.reply_text(f"Tous les fichiers ont été envoyés dans le canal {user_channel}.")
                        except Exception as e:
                            await message.reply_text(f"Erreur : Le canal {user_channel} n'est pas accessible. {e}")

                        del secantial_operations[user_id]
                else:
                    if media_type == "document":
                        await client.send_document(
                            message.chat.id,
                            document=path,
                            thumb=ph_path,
                            caption=caption,
                            progress=progress_for_pyrogram,
                            progress_args=("ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", upload_msg, time.time()),
                        )
                    elif media_type == "video":
                        await client.send_video(
                            message.chat.id,
                            video=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", upload_msg, time.time()),
                        )
                    elif media_type == "audio":
                        await client.send_audio(
                            message.chat.id,
                            audio=path,
                            caption=caption,
                            thumb=ph_path,
                            duration=0,
                            progress=progress_for_pyrogram,
                            progress_args=("ᴛᴇ́ʟᴇᴠᴇʀsᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", upload_msg, time.time()),
                        )
            except Exception as e:
                os.remove(renamed_file_path)
                if ph_path:
                    os.remove(ph_path)
                return await upload_msg.edit(f"Error: {e}")

            await download_msg.delete()
            os.remove(renamed_file_path)
            if ph_path:
                os.remove(ph_path)

        finally:
            await hyoshcoder.degrade_points(user_id, 1)
            if os.path.exists(renamed_file_path):
                os.remove(renamed_file_path)
            if os.path.exists(metadata_file_path):
                os.remove(metadata_file_path)
            if ph_path and os.path.exists(ph_path):
                os.remove(ph_path)
            del renaming_operations[file_id]
    finally:
        user_semaphore.release()