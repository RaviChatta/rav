from database.data import hyoshcoder
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from scripts import Txt

# Define your exact button layouts from command.py
ON = [
    [InlineKeyboardButton('Metadata Enabled', callback_data='metadata_1'),
     InlineKeyboardButton('✅', callback_data='metadata_1')],
    [InlineKeyboardButton('Set Custom Metadata', callback_data='custom_metadata')]
]

OFF = [
    [InlineKeyboardButton('Metadata Disabled', callback_data='metadata_0'),
     InlineKeyboardButton('❌', callback_data='metadata_0')],
    [InlineKeyboardButton('Set Custom Metadata', callback_data='custom_metadata')]
]

@Client.on_message(filters.command("metadata"))
async def metadata(client, message: Message):
    user_id = message.from_user.id
    bool_meta = await hyoshcoder.get_metadata(user_id)
    meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
    
    text = f"<b>Your current metadata:</b>\n\n➜ {meta_code}"
    
    await message.reply_text(
        text,
        reply_markup=InlineKeyboardMarkup(ON if bool_meta else OFF)
    )

@Client.on_callback_query(filters.regex(r'^metadata_[01]$'))
async def toggle_metadata_callback(client, query: CallbackQuery):
    user_id = query.from_user.id
    enable = query.data.endswith('_1')
    await hyoshcoder.set_metadata(user_id, enable)
    
    meta_code = await hyoshcoder.get_metadata_code(user_id) or "Not set"
    text = f"<b>Your current metadata:</b>\n\n➜ {meta_code}"
    
    await query.message.edit_text(
        text,
        reply_markup=InlineKeyboardMarkup(ON if enable else OFF)
    )
    await query.answer(f"Metadata {'enabled' if enable else 'disabled'}")

@Client.on_callback_query(filters.regex(r'^custom_metadata$'))
async def set_metadata_callback(client, query: CallbackQuery):
    try:
        # Delete the original button message
        await query.message.delete()
    except:
        pass

    # Send prompt for new metadata
    prompt = await client.send_message(
        chat_id=query.from_user.id,
        text=(
            "✏️ <b>Please send your new metadata text</b>\n\n"
            "Example: <code>Lakshmi Ganapathi Films</code>\n"
            f"Current: {await hyoshcoder.get_metadata_code(query.from_user.id) or 'None'}\n\n"
            "You have 2 minutes to respond.\n"
            "Type /cancel to abort."
        ),
        reply_markup=InlineKeyboardMarkup(
            [[InlineKeyboardButton("❌ Cancel", callback_data="cancel_meta")]]
        )
    )

    # Wait for user response
    try:
        response = await client.listen.Message(
            filters.text & filters.user(query.from_user.id),
            timeout=120  # 2 minute timeout
        )
        
        if response.text.startswith('/cancel'):
            await response.reply("🚫 Metadata update cancelled")
            return
            
        # Save the new metadata
        await hyoshcoder.set_metadata_code(query.from_user.id, response.text)
        
        # Show confirmation
        bool_meta = await hyoshcoder.get_metadata(query.from_user.id)
        await response.reply(
            f"✅ <b>Metadata updated successfully!</b>\n\n"
            f"New metadata: <code>{response.text}</code>",
            reply_markup=InlineKeyboardMarkup(ON if bool_meta else OFF)
        )

    except asyncio.TimeoutError:
        await prompt.edit("⏳ Timeout - metadata not changed")
    except Exception as e:
        await prompt.edit(f"❌ Error: {str(e)}")
        
@Client.on_message(filters.private & filters.text & ~filters.command(['start', 'cancel']))
async def handle_metadata_text(client, message: Message):
    # Check if this is a reply to metadata request
    if (message.reply_to_message and 
        "Send your custom metadata text" in message.reply_to_message.text):
        
        await hyoshcoder.set_metadata_code(message.from_user.id, message.text)
        
        # Show confirmation with fresh interface
        bool_meta = await hyoshcoder.get_metadata(message.from_user.id)
        markup = InlineKeyboardMarkup(ON if bool_meta else OFF)
        
        await message.reply_text(
            f"✅ Metadata updated to:\n<code>{message.text}</code>",
            reply_markup=markup
        )
        
        # Delete the intermediate messages
        await asyncio.sleep(2)
        try:
            await message.reply_to_message.delete()
            await message.delete()
        except:
            pass

@Client.on_callback_query(filters.regex(r'^cancel_meta$'))
async def cancel_metadata(client, query: CallbackQuery):
    bool_meta = await hyoshcoder.get_metadata(query.from_user.id)
    meta_code = await hyoshcoder.get_metadata_code(query.from_user.id) or "Not set"
    
    await query.message.edit_text(
        f"<b>Your current metadata:</b>\n\n➜ {meta_code}",
        reply_markup=InlineKeyboardMarkup(ON if bool_meta else OFF)
    )
    await query.answer("Metadata update cancelled")
