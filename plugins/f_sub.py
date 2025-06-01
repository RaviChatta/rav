import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired
from config import settings
from helpers.utils import get_random_photo
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS  # List of channel IDs (-100...)
CHECK_DELAY = 1  # Fast checks

async def not_subscribed(_, __, message: Message):
    """Check if user is not subscribed (with proper channel ID handling)"""
    if not FORCE_SUB_CHANNELS:
        return False
        
    user_id = message.from_user.id
    
    # Admin bypass
    if user_id == settings.ADMIN:
        return False
        
    for channel_id in FORCE_SUB_CHANNELS:
        try:
            user = await message._client.get_chat_member(channel_id, user_id)
            if user.status == "kicked":
                await message.reply("🚫 You're banned from our channels. Contact admins.")
                return False
            if user.status == "left":
                return True
        except UserNotParticipant:
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await not_subscribed(_, __, message)
        except Exception as e:
            logger.error(f"ForceSub Check Error (Channel ID: {channel_id}): {str(e)}")
            continue
            
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def force_sub_handler(client: Client, message: Message):
    """Fixed handler for channel IDs"""
    if not FORCE_SUB_CHANNELS:
        return
        
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    # Get media
    UNIVERSE_IMAGE = await get_random_photo() or "https://telegra.ph/file/3a4d5a6a6c3d4a7a9a8a9.jpg"
    
    not_joined = []
    channel_info = []
    
    # Get channel info with proper error handling
    for channel_id in FORCE_SUB_CHANNELS:
        try:
            chat = await client.get_chat(channel_id)
            try:
                invite_link = await client.export_chat_invite_link(channel_id)
            except:
                invite_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}"
            channel_info.append((channel_id, chat.title or f"Channel {channel_id}", invite_link))
        except Exception as e:
            logger.error(f"Failed to get channel {channel_id} info: {str(e)}")
            continue
    
    # Check subscription status
    for channel_id, title, invite_link in channel_info:
        try:
            user = await client.get_chat_member(channel_id, user_id)
            if user.status in ["left", "kicked"]:
                not_joined.append((channel_id, title, invite_link))
        except UserNotParticipant:
            not_joined.append((channel_id, title, invite_link))
        except Exception as e:
            logger.error(f"Subscription check failed: {str(e)}")
            continue
    
    if not not_joined:
        return await message.command_handler(client, message)
    
    # Create buttons
    buttons = []
    for _, title, invite_link in not_joined:
        buttons.append([InlineKeyboardButton(f"🔔 Join {title}", url=invite_link)])
    
    buttons.append([InlineKeyboardButton("✅ Verify Subscription", callback_data="force_sub_verify")])
    
    # Message text
    text = f"""
    🚀 **ACCESS REQUIRED** 🚀

**Hey {user_mention},**  
Join our channels to continue:

{'\n'.join(f'• **{title}**' for _, title, _ in not_joined)}
    """
    
    try:
        await message.reply_photo(
            photo=UNIVERSE_IMAGE,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"Failed to send force sub message: {str(e)}")
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("force_sub_verify"))
async def verify_subscription(client: Client, callback: CallbackQuery):
    """Verification handler for channel IDs"""
    user = callback.from_user
    user_id = user.id
    
    await callback.answer("🔍 Checking your subscription...")
    
    not_joined = []
    
    for channel_id in FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel_id)
        except UserNotParticipant:
            not_joined.append(channel_id)
        except Exception as e:
            logger.error(f"Verification error: {str(e)}")
            continue
    
    if not not_joined:
        try:
            await callback.message.delete()
        except:
            pass
        
        # Trigger start command
        fake_msg = callback.message
        fake_msg.text = "/start"
        fake_msg.from_user = user
        await fake_msg.command_handler(client, fake_msg)
    else:
        remaining = []
        for channel_id in not_joined:
            try:
                chat = await client.get_chat(channel_id)
                remaining.append(f"• {chat.title}")
            except:
                remaining.append(f"• Channel {channel_id}")
        
        text = f"""
        ❗ **INCOMPLETE SUBSCRIPTION** ❗

You still need to join:
{'\n'.join(remaining)}
        """
        
        await callback.message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔄 Try Again", callback_data="force_sub_verify")]
            ])
        )
        await callback.answer("Please join all channels first!", show_alert=True)
