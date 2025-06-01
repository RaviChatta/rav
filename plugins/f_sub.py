import os
import asyncio
import logging
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message
from pyrogram.errors import UserNotParticipant, FloodWait, ChatAdminRequired, ChannelInvalid, ChannelPrivate
from config import settings
from helpers.utils import get_random_photo
from database.data import hyoshcoder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

class ForceSubManager:
    def __init__(self):
        self.channel_cache = {}
        
    async def ensure_bot_joined(self, client: Client, channel_id: int):
        """Make sure bot has joined the channel"""
        try:
            # Check if already joined
            if channel_id in self.channel_cache:
                return True
                
            # Try to get chat details
            chat = await client.get_chat(channel_id)
            self.channel_cache[channel_id] = chat
            return True
            
        except (ChannelInvalid, ChannelPrivate):
            try:
                # Try to join via invite link
                invite = f"https://t.me/c/{str(channel_id).replace('-100', '')}"
                await client.join_chat(invite)
                self.channel_cache[channel_id] = await client.get_chat(channel_id)
                return True
            except Exception as e:
                logger.error(f"Failed to join channel {channel_id}: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"Channel check error {channel_id}: {str(e)}")
            return False

force_sub_manager = ForceSubManager()

@Client.on_message(filters.private & filters.command("fs_debug"))
async def debug_force_sub(client: Client, message: Message):
    """Admin command to debug force sub channels"""
    if message.from_user.id != settings.ADMIN:
        return
        
    report = []
    for channel_id in settings.FORCE_SUB_CHANNELS:
        try:
            joined = await force_sub_manager.ensure_bot_joined(client, channel_id)
            status = "✅ Joined" if joined else "❌ Failed"
            report.append(f"{channel_id}: {status}")
        except Exception as e:
            report.append(f"{channel_id}: ❌ Error ({str(e)})")
    
    await message.reply_text("Force Sub Debug:\n\n" + "\n".join(report))

async def not_subscribed(_, client: Client, message: Message):
    """Improved subscription check with channel validation"""
    if not settings.FORCE_SUB_CHANNELS:
        return False
        
    user_id = message.from_user.id
    
    # Admin bypass
    if user_id == settings.ADMIN:
        return False
        
    for channel_id in settings.FORCE_SUB_CHANNELS:
        try:
            # Ensure bot has joined first
            if not await force_sub_manager.ensure_bot_joined(client, channel_id):
                continue
                
            user = await client.get_chat_member(channel_id, user_id)
            if user.status == "kicked":
                await message.reply("🚫 You're banned from our channels. Contact admins.")
                return False
            if user.status == "left":
                return True
        except UserNotParticipant:
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value)
            continue
        except Exception as e:
            logger.error(f"Subscription check failed for {channel_id}: {str(e)}")
            continue
            
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def force_sub_handler(client: Client, message: Message):
    """Fixed handler with channel validation"""
    if not settings.FORCE_SUB_CHANNELS:
        return
        
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    # Get media
    UNIVERSE_IMAGE = await get_random_photo() or "https://telegra.ph/file/3a4d5a6a6c3d4a7a9a8a9.jpg"
    
    not_joined = []
    valid_channels = []
    
    # Validate channels first
    for channel_id in settings.FORCE_SUB_CHANNELS:
        try:
            if await force_sub_manager.ensure_bot_joined(client, channel_id):
                chat = await client.get_chat(channel_id)
                try:
                    invite_link = await client.export_chat_invite_link(channel_id)
                except:
                    invite_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}"
                valid_channels.append((channel_id, chat.title or f"Channel {channel_id}", invite_link))
        except Exception as e:
            logger.error(f"Skipping invalid channel {channel_id}: {str(e)}")
            continue
    
    # Check user status
    for channel_id, title, invite_link in valid_channels:
        try:
            user = await client.get_chat_member(channel_id, user_id)
            if user.status in ["left", "kicked"]:
                not_joined.append((channel_id, title, invite_link))
        except UserNotParticipant:
            not_joined.append((channel_id, title, invite_link))
        except Exception as e:
            logger.error(f"Status check failed for {channel_id}: {str(e)}")
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
    """Improved verification with channel validation"""
    user = callback.from_user
    user_id = user.id
    
    await callback.answer("🔍 Checking your subscription...")
    
    not_joined = []
    
    for channel_id in settings.FORCE_SUB_CHANNELS:
        try:
            if not await force_sub_manager.ensure_bot_joined(client, channel_id):
                continue
                
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel_id)
        except UserNotParticipant:
            not_joined.append(channel_id)
        except Exception as e:
            logger.error(f"Verification error for {channel_id}: {str(e)}")
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
