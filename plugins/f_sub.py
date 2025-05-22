import os
import asyncio
import logging
from typing import List, Union
from pyrogram import Client, filters, idle
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery, Message, User
from pyrogram.errors import (
    UserNotParticipant, 
    FloodWait, 
    ChannelInvalid, 
    ChatAdminRequired,
    PeerIdInvalid,
    MessageNotModified
)
from config import settings
from helpers.utils import get_random_photo, get_random_animation

logger = logging.getLogger(__name__)
FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS

async def not_subscribed(_: Client, client: Client, message: Message) -> bool:
    """
    Check if user is not subscribed to required channels.
    Returns True if user needs to subscribe, False if already subscribed.
    """
    if not FORCE_SUB_CHANNELS:
        return False

    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, message.from_user.id)
            if user.status in ["kicked", "left"]:
                logger.info(f"User {message.from_user.id} not subscribed to {channel}")
                return True
        except UserNotParticipant:
            logger.info(f"User {message.from_user.id} not participant in {channel}")
            return True
        except (ChannelInvalid, PeerIdInvalid) as e:
            logger.error(f"Invalid channel {channel}: {e}")
            continue
        except ChatAdminRequired:
            logger.error(f"Bot needs admin in {channel} to check subscriptions")
            continue
        except FloodWait as e:
            logger.warning(f"Flood wait {e.x}s for channel {channel}")
            await asyncio.sleep(e.x)
            return await not_subscribed(_, client, message)  # Retry
        except Exception as e:
            logger.error(f"Error checking subscription for {channel}: {e}")
            continue
    
    return False

async def build_subscription_buttons(client: Client, user_id: int) -> tuple[List[List[InlineKeyboardButton]], List[str]]:
    """
    Build subscription buttons for channels user hasn't joined.
    Returns (buttons, not_joined_channels)
    """
    buttons = []
    not_joined_channels = []

    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, user_id)
            if user.status in ["kicked", "left"]:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)
        except Exception as e:
            logger.error(f"Error checking channel {channel}: {e}")
            not_joined_channels.append(channel)

    for channel in not_joined_channels:
        try:
            chat = await client.get_chat(channel)
            channel_name = chat.title
            buttons.append([
                InlineKeyboardButton(
                    text=f"✨ Join {channel_name}",
                    url=f"https://t.me/{chat.username or channel}"
                )
            ])
        except Exception:
            buttons.append([
                InlineKeyboardButton(
                    text="✨ Join Channel", 
                    url=f"https://t.me/{channel}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            text="✅ I've Joined",
            callback_data="check_subscription"
        )
    ])
    
    return buttons, not_joined_channels

@Client.on_message(filters.private & filters.create(not_subscribed))
async def force_sub_handler(client: Client, message: Message):
    """
    Handle users who haven't subscribed to required channels.
    """
    try:
        media = await get_random_animation() or await get_random_photo()
        buttons, _ = await build_subscription_buttons(client, message.from_user.id)
        
        text = (
            "**🔒 Premium Content Access**\n\n"
            "To use this bot, please join our official channels first:\n"
            "• Join all channels below\n"
            "• Then click 'I've Joined' to verify\n\n"
            "Thank you for your support! 💖"
        )
        
        try:
            if media and media.endswith(('.mp4', '.gif')):
                await message.reply_animation(
                    animation=media,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="markdown"
                )
            elif media:
                await message.reply_photo(
                    photo=media,
                    caption=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    parse_mode="markdown"
                )
            else:
                await message.reply_text(
                    text=text,
                    reply_markup=InlineKeyboardMarkup(buttons),
                    disable_web_page_preview=True,
                    parse_mode="markdown"
                )
        except Exception as e:
            logger.error(f"Failed to send media message: {e}")
            await message.reply_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True,
                parse_mode="markdown"
            )
            
    except Exception as e:
        logger.error(f"Error in force_sub_handler: {e}")
        await message.reply_text(
            "⚠️ An error occurred. Please try again later.",
            parse_mode="markdown"
        )

@Client.on_callback_query(filters.regex("^check_subscription$"))
async def check_subscription_callback(client: Client, callback_query: CallbackQuery):
    """
    Handle subscription verification callback.
    """
    user = callback_query.from_user
    try:
        await callback_query.answer("Checking subscriptions...")
        
        # Check subscriptions with retries
        for attempt in range(3):
            buttons, not_joined = await build_subscription_buttons(client, user.id)
            
            if not not_joined:
                try:
                    await callback_query.message.delete()
                except:
                    pass
                
                welcome_msg = await send_effect_message(
                    client,
                    user.id,
                    f"**🎉 Access Granted!**\n\n"
                    f"Thanks for joining {user.mention()}!\n"
                    "You can now use all bot features.\n\n"
                    "Type /start to begin!",
                    effect_id=5  # Sparkles effect
                )
                asyncio.create_task(auto_delete_message(welcome_msg, delay=15))
                return
            
            await asyncio.sleep(2)  # Wait between checks

        # Still not subscribed to all channels
        text = (
            "**🚫 Subscription Required**\n\n"
            "You haven't joined all required channels yet:\n"
            "• Please join the channels below\n"
            "• Then click 'I've Joined' again\n\n"
            "If you've joined but still see this, try leaving and rejoining."
        )
        
        try:
            await callback_query.message.edit_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                parse_mode="markdown"
            )
        except MessageNotModified:
            pass
        except Exception:
            await callback_query.message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons),
                disable_web_page_preview=True,
                parse_mode="markdown"
            )
            
        await callback_query.answer(
            "Please join all channels first!",
            show_alert=True
        )
        
    except Exception as e:
        logger.error(f"Error in check_subscription_callback: {e}")
        await callback_query.answer(
            "An error occurred. Please try again.",
            show_alert=True
        )

async def auto_delete_message(message: Message, delay: int = 15):
    """Automatically delete message after delay"""
    try:
        await asyncio.sleep(delay)
        await message.delete()
    except Exception as e:
        logger.warning(f"Couldn't delete message: {e}")
