
import logging
from pyrogram import Client, filters
from pyrogram.types import Message
from datetime import datetime
from database.data import hyoshcoder
import asyncio

logger = logging.getLogger(__name__)

@Client.on_message(filters.private & filters.command("startsequence"))
async def start_sequence(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        username = message.from_user.first_name
        
        # Debug: Check if user exists
        if not await hyoshcoder.is_user_exist(user_id):
            await hyoshcoder.add_user(user_id)
            logger.info(f"Created new user {user_id} for sequence")

        # Check for existing sequence
        existing = await hyoshcoder.sequences.find_one({"user_id": user_id})
        if existing:
            await message.reply("⚠️ You already have an active sequence. Use /endsequence first.")
            return

        # Create new sequence
        sequence_data = {
            "user_id": user_id,
            "username": username,
            "files": [],
            "started_at": datetime.now(),
            "updated_at": datetime.now()
        }
        
        result = await hyoshcoder.sequences.insert_one(sequence_data)
        if result.inserted_id:
            logger.info(f"Started sequence for {user_id}")
            await message.reply(
                "📦 Sequence mode activated!\n\n"
                "Now send me files to add to your sequence.\n\n"
                "Commands:\n"
                "/showsequence - View current files\n"
                "/endsequence - Send all files\n"
                "/cancelsequence - Cancel sequence"
            )
        else:
            await message.reply("❌ Failed to start sequence. Please try again.")
            
    except Exception as e:
        logger.error(f"Error in start_sequence: {e}", exc_info=True)
        await message.reply("⚠️ An error occurred. Please try again.")

@Client.on_message(filters.private & (filters.document | filters.video | filters.audio))
async def handle_sequence_file(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        
        # Check if user has active sequence
        sequence = await hyoshcoder.sequences.find_one({"user_id": user_id})
        if not sequence:
            return

        # Get filename
        if message.document:
            filename = message.document.file_name
        elif message.video:
            filename = message.video.file_name or "video.mp4"
        elif message.audio:
            filename = message.audio.file_name or "audio.mp3"
        else:
            filename = "file"

        file_data = {
            "filename": filename,
            "msg_id": message.id,
            "chat_id": message.chat.id,
            "added_at": datetime.now()
        }

        # Add to sequence
        result = await hyoshcoder.sequences.update_one(
            {"user_id": user_id},
            {
                "$push": {"files": file_data},
                "$set": {"updated_at": datetime.now()}
            }
        )

        if result.modified_count > 0:
            await message.reply(f"➕ Added to sequence: {filename}")
        else:
            await message.reply("❌ Failed to add file to sequence")

    except Exception as e:
        logger.error(f"Error adding file to sequence: {e}", exc_info=True)

@Client.on_message(filters.private & filters.command("endsequence"))
async def end_sequence(client: Client, message: Message):
    user_id = message.from_user.id
    username = message.from_user.first_name
    
    # Get all files in sequence
    files = await hyoshcoder.get_sequence_files(user_id)
    if not files:
        await message.reply("❌ No files in sequence!")
        return
    
    progress = await message.reply(f"⏳ Sending {len(files)} files in order...")
    
    success = 0
    errors = []
    
    # Send files in order
    for file in sorted(files, key=lambda x: x['filename']):  # Sort by filename
        try:
            await client.copy_message(
                chat_id=message.chat.id,
                from_chat_id=file["chat_id"],
                message_id=file["msg_id"]
            )
            success += 1
            await asyncio.sleep(1)  # Rate limit
            
            # Reward points every 5 files
            if success % 5 == 0:
                await hyoshcoder.add_points(user_id, 5, "sequence")
                
        except Exception as e:
            errors.append(f"{file['filename']}: {str(e)}")
    
    # Update stats if successful
    if success > 0:
        await hyoshcoder.increment_sequence_count(user_id, username, success)
    
    # Clean up sequence
    await hyoshcoder.end_sequence(user_id)
    
    # Show results
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
