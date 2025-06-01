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

FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS  # Now accepts channel IDs (-100...)
CHECK_DELAY = 1  # Ultra-fast checks

async def not_subscribed(_, __, message: Message):
    """Check if user is not subscribed (ADMIN BYPASS + BAN DETECTION)"""
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
                await message.reply("🚫 **BANNED!** You are banned from our channels. Contact admins.")
                return False
            if user.status == "left":
                return True
        except UserNotParticipant:
            return True
        except FloodWait as e:
            await asyncio.sleep(e.value)
            return await not_subscribed(_, __, message)
        except Exception as e:
            logger.error(f"ForceSub Error (Channel ID: {channel_id}): {e}")
            continue
            
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def universe_force_sub(client: Client, message: Message):
    """ULTIMATE FORCE-SUB HANDLER FOR CHANNEL IDs"""
    if not FORCE_SUB_CHANNELS:
        return
        
    user_id = message.from_user.id
    user_mention = message.from_user.mention
    
    # Get a stunning random image
    UNIVERSE_IMAGE = await get_random_photo() # or "https://telegra.ph/file/3a4d5a6a6c3d4a7a9a8a9.jpg"
    
    not_joined = []
    channel_info = []
    
    # Fetch channel details
    for channel_id in FORCE_SUB_CHANNELS:
        try:
            chat = await client.get_chat(channel_id)
            invite_link = await client.export_chat_invite_link(channel_id)
            channel_info.append((channel_id, chat.title or f"Channel {channel_id}", invite_link))
        except Exception as e:
            logger.error(f"Failed to get channel {channel_id} info: {e}")
            try:
                # Fallback to basic invite link generation
                invite_link = f"https://t.me/c/{str(channel_id).replace('-100', '')}"
                channel_info.append((channel_id, f"Channel {channel_id}", invite_link))
            except:
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
            logger.error(f"ForceSub Check Error: {e}")
            continue
    
    if not not_joined:
        return await message.command_handler(client, message)  # Proceed if already joined
    
    # ===== UNIVERSE-LEVEL BUTTONS ===== #
    buttons = []
    
    # **1-TAP JOIN ALL BUTTON** (MAGIC LINK)
    if len(not_joined) > 1:
        buttons.append([
            InlineKeyboardButton(
                text="🌟 JOIN ALL CHANNELS (1-TAP) 🌟",
                url=not_joined[0][2]  # First channel's invite link
            )
        ])
    
    # Individual channel buttons (fallback)
    for _, title, invite_link in not_joined:
        buttons.append([
            InlineKeyboardButton(
                text=f"🔔 {title}",
                url=invite_link
            )
        ])
    
    # **AUTO-VERIFY BUTTON** (NO SPAMMING "I'VE JOINED")
    buttons.append([
        InlineKeyboardButton(
            text="✅ AUTOMATIC VERIFY",
            callback_data="force_sub_verify"
        )
    ])
    
    # **UNIVERSE-LEVEL MESSAGE**
    text = f"""
    🚀 **ACCESS DENIED** 🚀

**Hey {user_mention},**  
You must join **{len(not_joined)} channel(s)** to use this bot!

**🔗 Required Channels:**  
{'\n'.join(f'• **{title}**' for _, title, _ in not_joined)}

**👉 Click "JOIN ALL" to unlock instantly!**
    """
    
    try:
        await message.reply_photo(
            photo=UNIVERSE_IMAGE,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )
    except Exception as e:
        logger.error(f"ForceSub Send Error: {e}")
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

@Client.on_callback_query(filters.regex("force_sub_verify"))
async def auto_verify_force_sub(client: Client, callback: CallbackQuery):
    """AUTO-VERIFY SYSTEM FOR CHANNEL IDs"""
    user = callback.from_user
    user_id = user.id
    
    await callback.answer("⚡ Checking subscriptions...")
    
    not_joined = []
    
    for channel_id in FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(channel_id, user_id)
            if member.status in ["left", "kicked"]:
                not_joined.append(channel_id)
        except UserNotParticipant:
            not_joined.append(channel_id)
        except Exception as e:
            logger.error(f"Auto-Verify Error: {e}")
            continue
    
    if not not_joined:
        # **SUCCESS - UNLOCK BOT**
        try:
            await callback.message.delete()
        except:
            pass
        
        # **TRIGGER /start AUTOMATICALLY**
        fake_msg = callback.message
        fake_msg.text = "/start"
        fake_msg.from_user = user
        await fake_msg.command_handler(client, fake_msg)
    else:
        # **FAILED - SHOW REMAINING CHANNELS**
        remaining = []
        for channel_id in not_joined:
            try:
                chat = await client.get_chat(channel_id)
                remaining.append(f"• **{chat.title}**")
            except:
                remaining.append(f"• Channel {channel_id}")
        
        text = f"""
        ❗ **INCOMPLETE SUBSCRIPTION** ❗

You still need to join:  
{'\n'.join(remaining)}

**👉 Join and press VERIFY again!**
        """
        
        # Get new invite links for remaining channels
        new_buttons = []
        for channel_id in not_joined:
            try:
                invite_link = await client.export_chat_invite_link(channel_id)
                new_buttons.append([
                    InlineKeyboardButton(
                        f"Join Channel {channel_id}",
                        url=invite_link
                    )
                ])
            except:
                pass
        
        new_buttons.append([
            InlineKeyboardButton("🔄 TRY AGAIN", callback_data="force_sub_verify")
        ])
        
        await callback.message.edit_caption(
            caption=text,
            reply_markup=InlineKeyboardMarkup(new_buttons)
        )
        await callback.answer("Join all channels first!", show_alert=True)
