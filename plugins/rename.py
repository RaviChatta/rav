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
from scripts import Txt

logger = logging.getLogger(__name__)

class RenameHandler:
    def __init__(self):
        self.renaming_operations: Dict[str, datetime] = {}
        self.sequential_operations: Dict[int, Dict] = {}
        self.user_semaphores: Dict[int, asyncio.Semaphore] = {}
        self.user_queue_messages: Dict[int, List[Message]] = {}
        self.pending_manual_renames: Dict[int, Dict] = {}

    async def get_user_semaphore(self, user_id: int) -> asyncio.Semaphore:
        """Get or create a semaphore for user to control concurrent operations"""
        if user_id not in self.user_semaphores:
            self.user_semaphores[user_id] = asyncio.Semaphore(3)  # Limit to 3 concurrent operations per user
        return self.user_semaphores[user_id]

    async def apply_metadata(self, file_path: str, metadata_code: str, output_path: str) -> bool:
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

    async def process_file_rename(self, client: Client, message: Message, file_name: str, file_id: str, queue_message: Message, user_id: int):
        """Process file renaming with proper error handling"""
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
                progress_args=(Txt.PROGRESS_BAR, queue_message, time.time())
            )

            if not file_path or not os.path.exists(file_path):
                await queue_message.edit_text("❌ Download failed")
                return None

            # Generate new filename
            new_name = self.generate_new_filename(file_name, format_template)
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

    def generate_new_filename(self, original_name: str, template: str) -> str:
        """Generate new filename based on template with smart extraction"""
        try:
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
        except Exception as e:
            logger.error(f"Filename generation error: {e}")
            return original_name  # Fallback to original name

    async def send_renamed_file(
        self,
        client: Client,
        user_id: int,
        file_path: str,
        file_name: str,
        original_message: Message,
        queue_message: Message,
        media_type: str = "document"
    ) -> bool:
        """Send the renamed file back to the user with all metadata"""
        try:
            if not os.path.exists(file_path):
                await queue_message.edit_text("❌ File not found for upload")
                return False

            # Get user settings
            custom_caption = await hyoshcoder.get_caption(user_id)
            custom_thumb = await hyoshcoder.get_thumbnail(user_id)

            # Prepare caption
            file_size = os.path.getsize(file_path)
            duration = "N/A"
            
            # Try to extract duration for media files
            if media_type in ["video", "audio"]:
                try:
                    metadata = extractMetadata(createParser(file_path))
                    if metadata and metadata.has("duration"):
                        duration = convert(metadata.get("duration").seconds)
                except Exception as e:
                    logger.error(f"Duration extraction error: {e}")

            caption = (
                custom_caption.format(
                    filename=file_name,
                    filesize=humanbytes(file_size),
                    duration=duration
                ) if custom_caption else f"**{file_name}**"
            )

            # Handle thumbnail
            thumb_path = None
            if custom_thumb:
                try:
                    thumb_path = await client.download_media(custom_thumb)
                    # Resize thumbnail if needed
                    with Image.open(thumb_path) as img:
                        img.thumbnail((320, 320))
                        img.save(thumb_path, "JPEG")
                except Exception as e:
                    logger.error(f"Thumbnail processing error: {e}")
                    thumb_path = None

            # Send file based on type
            if media_type == "document":
                await client.send_document(
                    original_message.chat.id,
                    document=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    file_name=file_name,
                    progress=progress_for_pyrogram,
                    progress_args=("Uploading...", queue_message, time.time())
                )
            elif media_type == "video":
                await client.send_video(
                    original_message.chat.id,
                    video=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    file_name=file_name,
                    duration=int(duration.split(":")[0])*60 + int(duration.split(":")[1]) if ":" in duration else 0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uploading...", queue_message, time.time())
                )
            elif media_type == "audio":
                await client.send_audio(
                    original_message.chat.id,
                    audio=file_path,
                    thumb=thumb_path,
                    caption=caption,
                    file_name=file_name,
                    duration=int(duration.split(":")[0])*60 + int(duration.split(":")[1]) if ":" in duration else 0,
                    progress=progress_for_pyrogram,
                    progress_args=("Uploading...", queue_message, time.time())
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
            if file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except:
                    pass

    async def handle_manual_rename(self, client: Client, message: Message, user_id: int):
        """Handle manual rename when auto-rename is off"""
        if user_id not in self.pending_manual_renames:
            return

        rename_data = self.pending_manual_renames[user_id]
        file_id = rename_data["file_id"]
        callback_msg = rename_data["callback_message"]
        
        try:
            new_name = message.text.strip()
            if len(new_name) > 100:
                raise ValueError("Filename too long (max 100 chars)")
            if not new_name:
                raise ValueError("Filename cannot be empty")
            
            # Get the original message with the file
            original_msg = await client.get_messages(user_id, message_ids=int(file_id))
            if not original_msg or not (original_msg.document or original_msg.video or original_msg.audio):
                raise ValueError("Original file message not found")
            
            # Process points deduction
            points_config = await hyoshcoder.get_config("points_config") or {}
            points_per_rename = points_config.get("per_rename", 2)
            current_points = await hyoshcoder.get_points(user_id)
            
            premium_status = await hyoshcoder.check_premium_status(user_id)
            if not premium_status.get("is_premium", False):
                if current_points < points_per_rename:
                    await callback_msg.edit_text(
                        f"❌ Insufficient points! Each rename costs {points_per_rename} points\n"
                        f"Your balance: {current_points} points"
                    )
                    return
                
                await hyoshcoder.deduct_points(user_id, points_per_rename, "manual_rename")
            
            # Create queue message
            queue_message = await callback_msg.reply_text(
                "🔄 Processing your manual rename request...",
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{file_id}")]
                ])
            )
            
            # Get file info
            if original_msg.document:
                file = original_msg.document
                file_name = file.file_name or "document"
                media_type = "document"
            elif original_msg.video:
                file = original_msg.video
                file_name = getattr(file, "file_name", None) or "video.mp4"
                media_type = "video"
            elif original_msg.audio:
                file = original_msg.audio
                file_name = getattr(file, "file_name", None) or "audio.mp3"
                media_type = "audio"
            else:
                raise ValueError("Unsupported file type")

            # Process the rename
            result = await self.process_file_rename(
                client, original_msg, file_name, file_id, queue_message, user_id
            )
            
            if not result:
                return

            final_path, renamed_file_name = result

            # Send the renamed file
            success = await self.send_renamed_file(
                client,
                user_id,
                final_path,
                new_name,  # Use the manually provided name
                original_msg,
                queue_message,
                media_type
            )

            if success:
                # Track the rename in database
                await hyoshcoder.track_file_rename(
                    user_id=user_id,
                    original_name=file_name,
                    new_name=new_name,
                    file_type=media_type,
                    file_size=file.file_size
                )
                
                await callback_msg.edit_text(f"✅ File renamed to: {new_name}")
            
        except Exception as e:
            logger.error(f"Manual rename error: {e}")
            await callback_msg.edit_text(f"❌ Rename failed: {str(e)}")
            
            # Refund points if deduction was made but rename failed
            if not premium_status.get("is_premium", False) and rename_data.get("points_deducted", False):
                try:
                    await hyoshcoder.add_points(user_id, points_per_rename, "rename_failed_refund")
                except Exception as refund_error:
                    logger.error(f"Failed to refund points: {refund_error}")
        finally:
            if user_id in self.pending_manual_renames:
                del self.pending_manual_renames[user_id]
            try:
                await message.delete()
            except:
                pass

    async def auto_rename_files(self, client: Client, message: Message):
        """Main auto-rename handler for incoming files"""
        user_id = message.from_user.id
        
        # Check user registration
        user_data = await hyoshcoder.read_user(user_id)
        if not user_data:
            return await message.reply_text("❌ Please start the bot first with /start")

        # Check auto-rename status
        auto_rename_status = await hyoshcoder.get_auto_rename_status(user_id)
        if not auto_rename_status:
            # If auto-rename is off, offer manual rename option
            buttons = InlineKeyboardMarkup([
                [InlineKeyboardButton("📝 Rename Manually", callback_data=f"rename_{message.id}")],
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{message.id}")]
            ])
            return await message.reply_text(
                "Auto-rename is disabled. Would you like to rename this file manually?",
                reply_markup=buttons
            )

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
        if file_id in self.renaming_operations:
            elapsed = (datetime.now() - self.renaming_operations[file_id]).seconds
            if elapsed < 10:  # 10 second cooldown for same file
                return
        self.renaming_operations[file_id] = datetime.now()

        # Create queue message
        queue_message = await message.reply_text(
            "🔄 Your file has been added to processing queue...",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{file_id}")]
            ])
        )

        # Track queue messages
        if user_id not in self.user_queue_messages:
            self.user_queue_messages[user_id] = []
        self.user_queue_messages[user_id].append(queue_message)

        # Acquire semaphore for this user
        user_semaphore = await self.get_user_semaphore(user_id)
        await user_semaphore.acquire()

        try:
            # Process the file
            result = await self.process_file_rename(client, message, file_name, file_id, queue_message, user_id)
            if not result:
                return

            final_path, renamed_file_name = result

            # Deduct points if not premium
            if not premium_status.get("is_premium", False):
                await hyoshcoder.deduct_points(user_id, points_per_rename, "file_rename")

            # Send the renamed file with proper media type handling
            success = await self.send_renamed_file(
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
                await hyoshcoder.track_file_rename(
                    user_id=user_id,
                    original_name=file_name,
                    new_name=renamed_file_name,
                    file_type=media_type,
                    file_size=file.file_size
                )

        except Exception as e:
            logger.error(f"Error in auto_rename_files: {e}")
            await queue_message.edit_text(f"❌ Error processing file: {e}")
        finally:
            # Cleanup
            if user_id in self.user_queue_messages and queue_message in self.user_queue_messages[user_id]:
                self.user_queue_messages[user_id].remove(queue_message)
            
            if file_id in self.renaming_operations:
                del self.renaming_operations[file_id]
            
            user_semaphore.release()

    async def cancel_operation(self, client: Client, query: CallbackQuery, user_id: int, file_id: str):
        """Cancel any pending rename operation"""
        try:
            if file_id in self.renaming_operations:
                del self.renaming_operations[file_id]
            
            if user_id in self.user_queue_messages:
                for msg in self.user_queue_messages[user_id]:
                    try:
                        if str(msg.reply_to_message.message_id) == file_id:
                            await msg.edit_text("❌ Processing cancelled by user")
                            self.user_queue_messages[user_id].remove(msg)
                            break
                    except:
                        continue

            if user_id in self.pending_manual_renames and self.pending_manual_renames[user_id].get("file_id") == file_id:
                del self.pending_manual_renames[user_id]
                await query.message.edit_text("❌ Manual rename cancelled")

            await query.answer("Processing cancelled")
        except Exception as e:
            logger.error(f"Cancel operation error: {e}")
            await query.answer("❌ Failed to cancel operation", show_alert=True)

# Initialize handler
rename_handler = RenameHandler()

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_file(client: Client, message: Message):
    await rename_handler.auto_rename_files(client, message)

@Client.on_message(filters.private & filters.text & ~filters.command)
async def handle_manual_rename_text(client: Client, message: Message):
    await rename_handler.handle_manual_rename(client, message, message.from_user.id)

@Client.on_callback_query(filters.regex(r"^cancel_"))
async def handle_cancel_rename(client: Client, query: CallbackQuery):
    file_id = query.data.split("_", 1)[1]
    await rename_handler.cancel_operation(client, query, query.from_user.id, file_id)
