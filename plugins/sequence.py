import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

@Client.on_message(filters.private & filters.command("startsequence"))
async def start_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    if await hyoshcoder.is_in_sequence_mode(user_id):
        await message.reply("⚠️ You already have an active sequence. Use /endsequence first.")
        return
        
    if await hyoshcoder.start_sequence(user_id, username):
        logger.info(f"User {user_id} started sequence")
        await message.reply(
            "📦 Sequence mode activated!\n\n"
            "Now send me the files you want to sequence.\n\n"
            "Commands:\n"
            "/showsequence - View current files\n"
            "/endsequence - Send all files in order\n"
            "/cancelsequence - Cancel the sequence"
        )
    else:
        await message.reply("❌ Failed to start sequence. Please try again.")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_sequence_file(client: Client, message: Message):
    user_id = message.from_user.id
    
    if not await hyoshcoder.is_in_sequence_mode(user_id):
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
    file_data = {
        "filename": filename,
        "msg_id": message.id,
        "chat_id": message.chat.id,
        "added_at": datetime.now()
    }
    
    if await hyoshcoder.add_file_to_sequence(user_id, file_data):
        await message.reply(f"➕ Added to sequence: {filename}")
    else:
        await message.reply("❌ Failed to add file to sequence")

@Client.on_message(filters.private & filters.command("endsequence"))
async def end_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    files = await hyoshcoder.get_sequence_files(user_id)
    if not files:
        await message.reply("❌ No files in sequence!")
        return
    
    progress = await message.reply(f"⏳ Sending {len(files)} files in order...")
    
    success = 0
    errors = []
    
    for file in files:
        try:
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=file["chat_id"],
                message_id=file["msg_id"]
            )
            success += 1
            await asyncio.sleep(1)  # Rate limiting
            
            # Add points for successful sequence
            if success % 5 == 0:  # Reward every 5 files
                points = 5
                await hyoshcoder.add_points(user_id, points, "sequence", f"Sequenced {success} files")
                
        except Exception as e:
            errors.append(f"{file['filename']}: {str(e)}")
    
    # Update stats
    if success > 0:
        await hyoshcoder.increment_sequence_count(user_id, username, success)
    
    # Clean up
    await hyoshcoder.end_sequence(user_id)
    
    # Send result
    result = f"✅ Successfully sent {success}/{len(files)} files!"
    if errors:
        result += "\n\nErrors:\n" + "\n".join(errors[:3])
        if len(errors) > 3:
            result += f"\n...and {len(errors)-3} more"
    
    await progress.edit_text(result)

@Client.on_message(filters.private & filters.command("showsequence"))
async def show_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    files = await hyoshcoder.get_sequence_files(user_id)
    if not files:
        await message.reply("No files in sequence!")
        return
    
    file_list = "\n".join(f"{i}. {f['filename']}" for i, f in enumerate(files, 1))
    if len(file_list) > 4000:
        file_list = file_list[:3900] + "\n... (truncated)"
    
    await message.reply(f"📋 Current sequence ({len(files)} files):\n\n{file_list}")

@Client.on_message(filters.private & filters.command("cancelsequence"))
async def cancel_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    
    if await hyoshcoder.end_sequence(user_id):
        await message.reply("🗑 Sequence cancelled and cleared!")
    else:
        await message.reply("No active sequence to cancel.")

@Client.on_message(filters.private & filters.command("sequenceleaderboard"))
async def sequence_leaderboard(client: Client, message: Message):
    """Show leaderboard of users with most sequenced files"""
    try:
        leaderboard = await hyoshcoder.get_sequence_leaderboard(10)
        
        if not leaderboard:
            await message.reply("No sequence data available yet!")
            return
        
        text = "🏆 **Sequence Leaderboard** �n\n"
        for i, user in enumerate(leaderboard, 1):
            text += f"{i}. {user['username']} - {user['files_sequenced']} files\n"
        
        text += "\nUse /startsequence to start your own sequence!"
        await message.reply(text)
    except Exception as e:
        logger.error(f"Error showing sequence leaderboard: {e}")
        await message.reply("⚠️ Failed to load sequence leaderboard. Please try again.")
