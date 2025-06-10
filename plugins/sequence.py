import asyncio
import logging
import re
from datetime import datetime
from typing import List, Dict

from pyrogram import Client, filters
from pyrogram.types import Message
from motor.motor_asyncio import AsyncIOMotorClient
from pyrogram import idle
from config import settings

# Initialize the client
app = Client(
    "sequence_bot",
    api_id=settings.API_ID,
    api_hash=settings.API_HASH,
    bot_token=settings.BOT_TOKEN
)
# Initialize logger
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Database setup with motor for async MongoDB
mongo_client = AsyncIOMotorClient(settings.DATA_URI)
db = mongo_client[settings.DATA_NAME]
users_collection = db["users_sequence"]
sequence_collection = db["active_sequences"]

# Patterns for extracting episode numbers
patterns = [
    re.compile(r'\b(?:EP|E)\s*-\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'\b(?:EP|E)\s*(\d{1,3})\b', re.IGNORECASE),
    re.compile(r'S(\d+)(?:E|EP)(\d+)', re.IGNORECASE),
    re.compile(r'S(\d+)\s*(?:E|EP|-\s*EP)\s*(\d+)', re.IGNORECASE),
    re.compile(r'(?:[([<{]?\s*(?:E|EP)\s*(\d+)\s*[)\]>}]?)', re.IGNORECASE),
    re.compile(r'(?:EP|E)?\s*[-]?\s*(\d{1,3})', re.IGNORECASE),
    re.compile(r'S(\d+)[^\d]*(\d+)', re.IGNORECASE),
    re.compile(r'(\d+)')
]

def extract_episode_number(filename: str) -> int:
    """Extract episode number from filename for sorting"""
    for pattern in patterns:
        match = pattern.search(filename)
        if match:
            return int(match.groups()[-1])
    return float('inf')

async def is_in_sequence_mode(user_id: int) -> bool:
    """Check if user is in sequence mode"""
    return await sequence_collection.find_one({"user_id": user_id}) is not None

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
    leaderboard = []
    async for user in users_collection.find().sort("files_sequenced", -1).limit(limit):
        leaderboard.append({
            "_id": user["user_id"],
            "username": user.get("username", f"User {user['user_id']}"),
            "files_sequenced": user.get("files_sequenced", 0)
        })
    return leaderboard

@Client.on_message(filters.private & filters.command("startsequence"))
async def start_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    if await is_in_sequence_mode(user_id):
        await message.reply("⚠️ You already have an active sequence. Use /endsequence first.")
        return
        
    await sequence_collection.insert_one({
        "user_id": user_id,
        "username": username,
        "files": [],
        "started_at": datetime.now(),
        "updated_at": datetime.now()
    })
    
    logger.info(f"User {user_id} started sequence")
    await message.reply(
        "📦 Sequence mode activated!\n\n"
        "Now send me the files you want to sequence.\n\n"
        "Commands:\n"
        "/showsequence - View current files\n"
        "/endsequence - Send all files in order\n"
        "/cancelsequence - Cancel the sequence"
    )

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_sequence_file(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not await is_in_sequence_mode(user_id):
        return
    
    # Get filename based on media type
    if message.document:
        filename = message.document.file_name
    elif message.video:
        filename = message.video.file_name or "video.mp4"
    elif message.audio:
        filename = message.audio.file_name or "audio.mp3"
    else:
        filename = "file"
    
    # Add to sequence
    await sequence_collection.update_one(
        {"user_id": user_id},
        {"$push": {"files": {
            "filename": filename,
            "msg_id": message.id,
            "chat_id": message.chat.id,
            "added_at": datetime.now()
        }},
         "$set": {"updated_at": datetime.now()}}
    )
    
    await message.reply(f"➕ Added to sequence: {filename}")

@Client.on_message(filters.private & filters.command("endsequence"))
async def end_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    sequence = await sequence_collection.find_one({"user_id": user_id})
    if not sequence or not sequence.get("files"):
        await message.reply("❌ No files in sequence!")
        return
    
    files = sequence["files"]
    sorted_files = sorted(files, key=lambda x: extract_episode_number(x["filename"]))
    
    progress = await message.reply(f"⏳ Sending {len(sorted_files)} files in order...")
    
    success = 0
    errors = []
    
    for file in sorted_files:
        try:
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=file["chat_id"],
                message_id=file["msg_id"]
            )
            success += 1
            await asyncio.sleep(1)  # Rate limiting
        except Exception as e:
            errors.append(f"{file['filename']}: {str(e)}")
    
    # Update stats
    if success > 0:
        await increment_user_sequence_count(user_id, username, success)
    
    # Clean up
    await sequence_collection.delete_one({"user_id": user_id})
    
    # Send result
    result = f"✅ Successfully sent {success}/{len(sorted_files)} files!"
    if errors:
        result += "\n\nErrors:\n" + "\n".join(errors[:3])
        if len(errors) > 3:
            result += f"\n...and {len(errors)-3} more"
    
    await progress.edit_text(result)

@Client.on_message(filters.private & filters.command("showsequence"))
async def show_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    sequence = await sequence_collection.find_one({"user_id": user_id})
    if not sequence or not sequence.get("files"):
        await message.reply("No files in sequence!")
        return
    
    files = sorted(sequence["files"], key=lambda x: extract_episode_number(x["filename"]))
    
    file_list = "\n".join(f"{i}. {f['filename']}" for i, f in enumerate(files, 1))
    if len(file_list) > 4000:
        file_list = file_list[:3900] + "\n... (truncated)"
    
    await message.reply(f"📋 Current sequence ({len(files)} files):\n\n{file_list}")

@Client.on_message(filters.private & filters.command("cancelsequence"))
async def cancel_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    result = await sequence_collection.delete_one({"user_id": user_id})
    if result.deleted_count > 0:
        await message.reply("🗑 Sequence cancelled and cleared!")
    else:
        await message.reply("No active sequence to cancel.")
