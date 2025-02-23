from datetime import datetime, timezone
import os
import shutil
import asyncio
import time
import logging
from typing import List, Optional, Dict, Union
from pathlib import Path
from uuid import uuid4
from mimetypes import guess_type
from aiohttp import ClientSession
from pyrogram import Client, enums
from pyrogram.types import Message, CallbackQuery
from pyrogram.errors import FloodWait, MessageNotModified
from database.userdb import read_user, update_user, clear_user_queue
from model.user import QueueItem
from .extract_data import extract_season_episode, extract_quality
from config import settings
from helper.enti_nfsw import check_anti_nsfw
from helper.utils import get_video_duration, progress_for_pyrogram


MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 Go

def cleanup_temp_files(*file_paths: Path):
    for file_path in file_paths:
        try:
            if file_path.exists():
                file_path.unlink()
        except Exception as e:
            pass
async def download_file(client, file_source, file_name, message=None):
    try:
        if isinstance(file_source, Message):
            if file_source.media:
                file_id = file_source.media.file_id
            else:
                return None
        elif isinstance(file_source, CallbackQuery):
            if file_source.message and file_source.message.media:
                file_id = file_source.message.media.file_id
            else:
                return None
        elif isinstance(file_source, str):
            file_id = file_source
        else:
            return None

        download_msg = await message.reply_text("**__ᴛᴇʟᴇ́ᴄʜᴀʀɢᴇᴍᴇɴᴛ...__**")
        file_path = await client.download_media(
            file_id,
            file_name=file_name,
            progress=progress_for_pyrogram,
            progress_args=("ᴛᴇʟᴇ́ᴄʜᴀʀɢᴇᴍᴇɴᴛ ᴇɴ ᴄᴏᴜʀs...", download_msg, time.time())
        )
        await download_msg.delete()
        if os.path.exists(file_path):
            return file_path
        else:
            return None

    except Exception as e:
        return None

async def upload_file(client, file_path, dest, message=None, thumb=None, is_video=False):

    ud_type = "Téléversement..."
    download_file = None  

    try:
        if not os.path.exists(file_path):
            return None

        file_size = os.path.getsize(file_path)
        start_time = time.time()

        if isinstance(dest, (Message, CallbackQuery)):
            chat_id = dest.chat.id
        elif isinstance(dest, (int, str)): 
            chat_id = dest
        else:
            return None

        upload_message = await message.reply_text("**__ᴛᴇʟᴇ́versement...__**")
        upload_args = {
            "chat_id": chat_id,
            "file_name": os.path.basename(file_path),
            "progress": progress_for_pyrogram,
            "progress_args": (ud_type, upload_message, time.time())
        }

        if thumb:
            download_file = await client.download_media(thumb)
            if download_file and os.path.exists(download_file):
                upload_args["thumb"] = download_file


        if is_video:
            sent_message = await client.send_video(video=file_path, **upload_args)
        else:
            sent_message = await client.send_document(document=file_path, **upload_args, force_document=True)
        return sent_message

    except FloodWait as e:
        await asyncio.sleep(e.value)
        return await upload_file(client, file_path, dest, message, thumb, is_video)
    except Exception as e:
        return None
    finally:
        await upload_message.delete()
        if download_file and os.path.exists(download_file):
            cleanup_temp_files(Path(download_file))  
            

async def copy_files_an_channel_log_to_other_channel(client: Client, channel_id: int, log_channel_id: int, message_ids=[]):

    if not message_ids:
        return []

    copied_messages = []

    for msg_id in message_ids:
        try:
            copied_msg = await client.copy_message(
                chat_id=channel_id,
                from_chat_id=log_channel_id,
                message_id=msg_id
            )
            copied_messages.append(copied_msg)
            await asyncio.sleep(1)

        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await copy_files_an_channel_log_to_other_channel(client, channel_id, log_channel_id, message_ids)

        except MessageNotModified:
            pass
        except Exception as e:
            pass
    return copied_messages

async def apply_metadata(file_path: Path, metadata: Dict[str, str], output_path: Path):
    ffmpeg_cmd = shutil.which('ffmpeg')
    if not ffmpeg_cmd:
        raise Exception("FFmpeg n'est pas installé ou n'est pas dans le PATH.")

    metadata_command = [
        ffmpeg_cmd,
        '-i', str(file_path),
        '-metadata', f'title={metadata["title"]}',
        '-metadata', f'artist={metadata["artist"]}',
        '-metadata', f'album={metadata["album"]}',
        '-metadata', f'genre={metadata["genre"]}',
        '-c', 'copy', 
        '-loglevel', 'error',  
        str(output_path)
    ]

    process = await asyncio.create_subprocess_exec(
        *metadata_command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()

    if process.returncode != 0:
        raise Exception(f"Erreur FFmpeg: {stderr.decode()}")

async def process_file(queue_item: QueueItem, session, client, message, user, metadata_dict, temp_queue):
    file_path = None
    metadata_file_path = None  

    try:
        file_id = queue_item.file_id
        file_name = queue_item.file_name
        unique_file_name = f"{uuid4()}_{file_name}" 
        file_path = Path(settings.TEMP_DIR) / unique_file_name  

        downloaded_path = await download_file(client, file_id, str(file_path), message)
        if not downloaded_path:
            await safe_reply(client, message, f"⚠️ Échec du téléchargement du fichier {file_name}.")
            return

        metadata_file_path = Path(settings.TEMP_DIR) / f"metadata_{unique_file_name}"
        await apply_metadata(file_path, metadata_dict, metadata_file_path)

        season_episode = await extract_season_episode(file_name)
        quality = await extract_quality(file_name)
        file_extension = Path(file_name).suffix  
        new_file_name = user.auto.format(
            episode=season_episode[1] if season_episode else "",
            saison=season_episode[0] if season_episode else "",
            quality=quality
        ) + file_extension  
        new_file_path = Path(settings.TEMP_DIR) / new_file_name
        metadata_file_path.rename(new_file_path)
        uploaded_message = await upload_file(client, str(new_file_path), settings.CHANNEL_LOG, message, user.thumb)
        if not uploaded_message:
            await safe_reply(client, message, f"⚠️ Échec de l'upload du fichier {new_file_name}.")
            return

        temp_queue[file_id] = {
            'id': file_id,  
            'season': season_episode[0] if season_episode else None,
            'episode': season_episode[1] if season_episode else None,
            'message_id': uploaded_message.id  
        }

    except Exception as e:
        pass
    finally:
        if file_path and file_path.exists():
            cleanup_temp_files(file_path)
        if metadata_file_path and metadata_file_path.exists():
            cleanup_temp_files(metadata_file_path)
        if new_file_path and new_file_path.exists():
            cleanup_temp_files(new_file_path)

async def process_user_queue(user_id: int, client: Client, update: Union[Message, CallbackQuery]):

    try:
        if isinstance(update, CallbackQuery):
            message = update.message
        else:
            message = update

        user = await read_user(user_id)
        if not user:
            return await safe_reply(client, message, f"Utilisateur {user_id} non trouvé.")

        queue = user.queue
        if not queue.files:
            return await safe_reply(client, message, f"Aucun fichier dans la file d'attente pour l'utilisateur {user_id}.")

        metadata_dict = {
            "title": user.metadata.titre or f"Encodé par @{client.me.username}",
            "artist": user.metadata.artiste or f"Encodé par @{client.me.username}",
            "album": user.metadata.album or f"Encodé par @{client.me.username}",
            "genre": user.metadata.genre or "Inconnu",
        }

        temp_queue = {}
        async with ClientSession() as session:
            semaphore = asyncio.Semaphore(3)

            async def process_file_with_semaphore(file):
                async with semaphore:
                    await process_file(file, session, client, message, user, metadata_dict, temp_queue)

            tasks = [process_file_with_semaphore(file) for file in queue.files]
            await asyncio.gather(*tasks)

        sorted_files = sorted(temp_queue.values(), key=lambda x: (x['season'] or 0, x['episode'] or 0))

        message_ids = [file['message_id'] for file in sorted_files]
        print(message_ids)
        dest = user.channel_dump['channel_id'] if user.channel_dump else user.id
        if message_ids:  
            await copy_files_an_channel_log_to_other_channel(client, dest, settings.CHANNEL_LOG, message_ids)


        await clear_user_queue(user_id)
        await safe_reply(client, message, "Traitement terminé.")

    except FloodWait as e:
        await asyncio.sleep(e.value)
    except Exception as e:
        await safe_reply(client, message, f"Une erreur s'est produite : {e}")
    
        
async def safe_reply(client: Client, message: Message, text: str):
    try:
        await message.reply(text)
    except FloodWait as e:
        await asyncio.sleep(e.value)
        await message.reply(text)
    except Exception as e:
        pass
