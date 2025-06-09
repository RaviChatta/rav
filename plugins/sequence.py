import asyncio
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
import re
from collections import defaultdict
from pymongo import MongoClient
from datetime import datetime
from config import settings
from typing import List, Dict, Optional

# Database setup
db_client = MongoClient(settings.DATA_URI)
db = db_client[settings.DATA_NAME]
users_collection = db["users_sequence"]
sequence_collection = db["active_sequences"]  # Simplified collection name

# Patterns for extracting episode numbers
patterns = [
    re.compile(r'\b(?:EP|E)\s*-\s*(\d{1,3})\b', re.IGNORECASE),  # "Ep - 06" format fix
    re.compile(r'\b(?:EP|E)\s*(\d{1,3})\b', re.IGNORECASE),  # "EP06" or "E 06"
    re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),  # "S1E06" / "S01EP06"
    re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)\s*(\d+)', re.IGNORECASE),  # "S 1 Ep 06"
    re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),  # "E(06)"
    re.compile(r'(?:EP|E)?\s*[-]?\s*(\d{1,3})', re.IGNORECASE),  # "E - 06" / "- 06"
    re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),  # "S1 - 06"
    re.compile(r'(\d+)')  # Simple fallback (last resort)
]

def extract_episode_number(filename: str) -> int:
    """Extract episode number from filename for sorting"""
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            return int(match.groups()[-1])
    return float('inf')  # Default for files without episode numbers

def is_in_sequence_mode(user_id: int) -> bool:
    """Check if user is in sequence mode"""
    return sequence_collection.find_one({"user_id": user_id}) is not None

async def get_user_sequence_count(user_id: int) -> int:
    """Get user's total sequenced files count"""
    user = await users_collection.find_one({"user_id": user_id})
    return user.get("files_sequenced", 0) if user else 0

async def increment_user_sequence_count(user_id: int, username: str, count: int = 1) -> None:
    """Increment user's sequenced files count"""
    await users_collection.update_one(
        {"user_id": user_id},
        {"$inc": {"files_sequenced": count}, 
         "$set": {"username": username}},
        upsert=True
    )

async def get_files_sequenced_leaderboard(limit: int = 10) -> List[Dict]:
    """Get the files sequenced leaderboard"""
    cursor = users_collection.find().sort("files_sequenced", -1).limit(limit)
    return [
        {
            "_id": str(user["_id"]),
            "user_id": user["user_id"],
            "username": user.get("username", f"User {user['user_id']}"),
            "files_sequenced": user.get("files_sequenced", 0)
        }
        async for user in cursor
    ]

@Client.on_message(filters.private & filters.command("startsequence"))
async def start_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if already in sequence mode
    if is_in_sequence_mode(user_id):
        await message.reply_text("⚠️ Sequence mode is already active. Send your files or use /endsequence.")
        return
        
    # Create new sequence entry
    sequence_collection.insert_one({
        "user_id": user_id,
        "files": [],
        "started_at": datetime.now(),
        "username": message.from_user.first_name
    })
    
    await message.reply_text(
        "✅ Sequence mode started! Send your files now.\n\n"
        "ℹ️ You can use:\n"
        "/showsequence - View current files\n"
        "/cancelsequence - Cancel the sequence\n"
        "/endsequence - Send all files in order"
    )

@Client.on_message(filters.private & filters.command("endsequence"))
async def end_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    # Get sequence data
    sequence_data = sequence_collection.find_one({"user_id": user_id})
    
    if not sequence_data or not sequence_data.get("files"):
        await message.reply_text("❌ No files in sequence!")
        return
    
    # Get files and sort them
    files = sequence_data.get("files", [])
    sorted_files = sorted(files, key=lambda x: extract_episode_number(x["filename"]))
    total = len(sorted_files)
    
    # Send progress message
    progress = await message.reply_text(f"⏳ Processing and sorting {total} files...")
    
    sent_count = 0
    errors = []
    
    # Send files in sequence
    for i, file in enumerate(sorted_files, 1):
        try:
            await client.copy_message(
                chat_id=message.chat.id, 
                from_chat_id=file["chat_id"], 
                message_id=file["msg_id"]
            )
            sent_count += 1
            
            # Update progress every 5 files
            if i % 5 == 0:
                await progress.edit_text(f"📤 Sent {i}/{total} files...")
            
            await asyncio.sleep(0.5)  # Add delay to prevent flooding
        except Exception as e:
            errors.append(f"{file['filename']}: {str(e)}")
            continue
    
    # Update user stats
    if sent_count > 0:
        await increment_user_sequence_count(user_id, username, sent_count)
    
    # Remove sequence data
    sequence_collection.delete_one({"user_id": user_id})
    
    # Prepare result message
    result_msg = f"✅ Successfully sent {sent_count}/{total} files in sequence!"
    if errors:
        error_list = "\n".join(errors[:3])  # Show first 3 errors
        if len(errors) > 3:
            error_list += f"\n...and {len(errors) - 3} more errors"
        result_msg += f"\n\n❌ Errors:\n{error_list}"
    
    await progress.edit_text(result_msg)

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio), group=0)
async def sequence_file_handler(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Check if user is in sequence mode
    if not is_in_sequence_mode(user_id):
        return
    
    # Get file name based on media type
    if message.document:
        file_name = message.document.file_name
    elif message.video:
        file_name = message.video.file_name or "video"
    elif message.audio:
        file_name = message.audio.file_name or "audio"
    else:
        file_name = "Unknown"
    
    # Store file information
    file_info = {
        "filename": file_name,
        "msg_id": message.id,
        "chat_id": message.chat.id,
        "added_at": datetime.now()
    }
    
    # Add to sequence collection
    sequence_collection.update_one(
        {"user_id": user_id},
        {"$push": {"files": file_info}},
        upsert=True
    )
    
    # Set flag to indicate this is for sequence
    message.stop_propagation()
    
    await message.reply_text(f"📂 Added to sequence: {file_name}")

@Client.on_message(filters.private & filters.command("cancelsequence"))
async def cancel_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Remove sequence data
    result = sequence_collection.delete_one({"user_id": user_id})
    
    if result.deleted_count > 0:
        await message.reply_text("❌ Sequence mode cancelled. All queued files have been cleared.")
    else:
        await message.reply_text("❓ No active sequence found to cancel.")

@Client.on_message(filters.private & filters.command("showsequence"))
async def show_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    # Get sequence data
    sequence_data = sequence_collection.find_one({"user_id": user_id})
    
    if not sequence_data or not sequence_data.get("files"):
        await message.reply_text("No files in current sequence.")
        return
    
    files = sequence_data.get("files", [])
    sorted_files = sorted(files, key=lambda x: extract_episode_number(x["filename"]))
    
    file_list = "\n".join([
        f"{i}. {file['filename']}" 
        for i, file in enumerate(sorted_files, 1)
    ])
    
    if len(file_list) > 4000:
        file_list = file_list[:3900] + "\n\n... (list truncated)"
    
    await message.reply_text(
        f"**Current Sequence Files ({len(files)}):**\n\n{file_list}"
    )

@Client.on_message(filters.private & filters.command("sequencestats"))
async def sequence_stats(client: Client, message: Message):
    user_id = message.from_user.id
    count = await get_user_sequence_count(user_id)
    
    await message.reply_text(
        f"📊 Your sequencing stats:\n\n"
        f"• Total files sequenced: {count}\n"
        f"• Current sequence: {len(sequence_collection.find_one({'user_id': user_id}).get('files', [])) if is_in_sequence_mode(user_id) else 0}"
    )
