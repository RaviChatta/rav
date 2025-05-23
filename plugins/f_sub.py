import asyncio
import logging
from typing import List, Optional
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message, CallbackQuery
from pyrogram.errors import (
    UserNotParticipant,
    FloodWait,
    ChannelInvalid,
    ChatAdminRequired,
    PeerIdInvalid,
    UsernameNotOccupied,
    UsernameInvalid,
    MessageNotModified
)
from config import settings

logger = logging.getLogger(__name__)
FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS or []

async def validate_channel(client: Client, channel: str) -> bool:
    """Check if a channel exists and is accessible"""
    try:
        if isinstance(channel, int) or (isinstance(channel, str) and channel.lstrip('-').isdigit()):
            await client.get_chat(int(channel))
        else:
            await client.get_chat(channel)
        return True
    except (UsernameNotOccupied, UsernameInvalid, PeerIdInvalid, ChannelInvalid):
        logger.error(f"Channel {channel} doesn't exist or is inaccessible")
        return False
    except Exception as e:
        logger.error(f"Error validating channel {channel}: {e}")
        return False

async def get_channel_info(client: Client, channel: str) -> Optional[dict]:
    """Get channel info with error handling"""
    try:
        if isinstance(channel, int) or (isinstance(channel, str) and channel.lstrip('-').isdigit()):
            chat = await client.get_chat(int(channel))
        else:
            chat = await client.get_chat(channel)
        return {
            'id': chat.id,
            'username': getattr(chat, 'username', None),
            'title': getattr(chat, 'title', f"Channel {chat.id}"),
            'invite_link': getattr(chat, 'invite_link', None)
        }
    except Exception as e:
        logger.error(f"Couldn't get info for channel {channel}: {e}")
        return None

async def is_subscribed(client: Client, user_id: int, channel: str) -> bool:
    """Check if user is subscribed to a specific channel"""
    try:
        member = await client.get_chat_member(channel, user_id)
        return member.status not in ["left", "kicked", None]
    except UserNotParticipant:
        return False
    except (ChannelInvalid, PeerIdInvalid, ChatAdminRequired):
        logger.error(f"Can't check membership in {channel}")
        return True  # Assume subscribed to avoid blocking users
    except FloodWait as e:
        logger.warning(f"Flood wait {e.x}s for channel {channel}")
        await asyncio.sleep(e.x)
        return await is_subscribed(client, user_id, channel)
    except Exception as e:
        logger.error(f"Subscription check error for {channel}: {e}")
        return True  # Fail safe - allow access

async def check_subscriptions(client: Client, user_id: int) -> tuple[bool, list]:
    """
    Check all forced subscriptions
    Returns (all_joined, failed_checks)
    """
    valid_channels = []
    
    # First validate all channels
    for channel in FORCE_SUB_CHANNELS:
        if await validate_channel(client, channel):
            valid_channels.append(channel)
        else:
            logger.warning(f"Removing invalid channel: {channel}")

    if not valid_channels:
        return True, []

    results = await asyncio.gather(*[is_subscribed(client, user_id, channel) for channel in valid_channels)
    failed = [channel for channel, result in zip(valid_channels, results) if not result]
    
    return len(failed) == 0, failed

async def build_subscription_buttons(client: Client, channels: list) -> InlineKeyboardMarkup:
    """Build buttons for channels user needs to join"""
    buttons = []
    
    for channel in channels:
        info = await get_channel_info(client, channel)
        if not info:
            continue
            
        url = f"https://t.me/{info['username']}" if info['username'] else info['invite_link']
        if not url:
            continue
            
        buttons.append([
            InlineKeyboardButton(
                text=f"Join {info['title']}",
                url=url
            )
        ])
    
    if buttons:
        buttons.append([
            InlineKeyboardButton(
                text="✅ I've Subscribed",
                callback_data="check_subs"
            )
        ])
    
    return InlineKeyboardMarkup(buttons) if buttons else None

@Client.on_message(filters.private & ~filters.user(settings.ADMIN))
async def force_sub_check(client: Client, message: Message):
    """Check subscriptions on private messages"""
    if not FORCE_SUB_CHANNELS:
        return
        
    try:
        all_joined, missing = await check_subscriptions(client, message.from_user.id)
        if all_joined:
            return
            
        buttons = await build_subscription_buttons(client, missing)
        if not buttons:
            return
            
        text = (
            "**🔒 Premium Content Access**\n\n"
            "To use this bot, please join our official channels first:\n\n"
            "1. Join all channels below\n"
            "2. Then click 'I've Subscribed'\n\n"
            "Thank you! 💖"
        )
        
        await message.reply(
            text=text,
            reply_markup=buttons,
            disable_web_page_preview=True
        )
        
    except Exception as e:
        logger.error(f"Force sub check error: {e}")

@Client.on_callback_query(filters.regex("^check_subs$"))
async def verify_subscription(client: Client, callback: CallbackQuery):
    """Verify user subscriptions"""
    try:
        await callback.answer("Checking subscriptions...")
        all_joined, missing = await check_subscriptions(client, callback.from_user.id)
        
        if all_joined:
            try:
                await callback.message.delete()
            except:
                pass
                
            await callback.message.reply("🎉 Access granted! You can now use all bot features.")
            return
            
        buttons = await build_subscription_buttons(client, missing)
        if buttons:
            try:
                await callback.message.edit_reply_markup(buttons)
            except MessageNotModified:
                pass
                
        await callback.answer(
            "Please join all required channels first!",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Subscription verification error: {e}")
        await callback.answer(
            "An error occurred. Please try again.",
            show_alert=True
        )
