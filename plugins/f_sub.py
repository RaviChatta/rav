import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant, PeerIdInvalid, ChatAdminRequired
from pyrogram.enums import ChatMemberStatus
from config import settings
import logging

logger = logging.getLogger(__name__)

# Validate and filter empty channel usernames
FORCE_SUB_CHANNELS = [channel.strip() for channel in settings.FORCE_SUB_CHANNELS if channel.strip()]
IMAGE_URL = "https://i.ibb.co/gFQFknCN/d8a33273f73c.jpg"

async def not_subscribed(_, __, message):
    if not FORCE_SUB_CHANNELS:
        return False
        
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await message._client.get_chat_member(channel, message.from_user.id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                return True
        except UserNotParticipant:
            return True
        except PeerIdInvalid:
            logger.warning(f"Invalid channel username: {channel}")
            continue
        except ChatAdminRequired:
            logger.warning(f"Bot is not admin in channel: {channel}")
            continue
        except Exception as e:
            logger.error(f"Error checking subscription for {channel}: {e}")
            continue
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def force_subscribe(client, message):
    if not FORCE_SUB_CHANNELS:
        return
        
    not_joined_channels = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(channel, message.from_user.id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                not_joined_channels.append(channel)
        except (UserNotParticipant, PeerIdInvalid, ChatAdminRequired):
            not_joined_channels.append(channel)
        except Exception as e:
            logger.error(f"Error checking subscription for {channel}: {e}")
            continue

    if not not_joined_channels:
        return

    buttons = [
        [InlineKeyboardButton(f"• ᴊᴏɪɴ {channel.upper()} •", url=f"https://t.me/{channel}")]
        for channel in not_joined_channels
    ]
    buttons.append([InlineKeyboardButton("• ᴊᴏɪɴᴇᴅ •", callback_data="check_subscription")])

    await message.reply_photo(
        photo=IMAGE_URL,
        caption="**ʙᴀᴋᴋᴀ!!, ʏᴏᴜ'ʀᴇ ɴᴏᴛ ᴊᴏɪɴᴇᴅ ᴛᴏ ᴀʟʟ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs, ᴊᴏɪɴ ᴛʜᴇᴍ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.**",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("check_subscription"))
async def check_subscription(client, callback_query: CallbackQuery):
    if not FORCE_SUB_CHANNELS:
        await callback_query.answer("No subscription required", show_alert=True)
        return
        
    user_id = callback_query.from_user.id
    not_joined_channels = []

    for channel in FORCE_SUB_CHANNELS:
        try:
            member = await client.get_chat_member(channel, user_id)
            if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                not_joined_channels.append(channel)
        except (UserNotParticipant, PeerIdInvalid, ChatAdminRequired):
            not_joined_channels.append(channel)
        except Exception as e:
            logger.error(f"Error checking subscription for {channel}: {e}")
            continue

    if not not_joined_channels:
        new_text = "**ʏᴏᴜ ʜᴀᴠᴇ ᴊᴏɪɴᴇᴅ ᴀʟʟ ᴛʜᴇ ʀᴇǫᴜɪʀᴇᴅ ᴄʜᴀɴɴᴇʟs. ɢᴏᴏᴅ ʙᴏʏ! 🔥 /start ɴᴏᴡ**"
        try:
            await callback_query.message.edit_caption(
                caption=new_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ɴᴏᴡ ᴄʟɪᴄᴋ ʜᴇʀᴇ •", callback_data='help')]
                ])
            )
            await callback_query.answer("Thanks for joining!", show_alert=True)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
    else:
        buttons = [
            [InlineKeyboardButton(f"• ᴊᴏɪɴ {channel.upper()} •", url=f"https://t.me/{channel}")]
            for channel in not_joined_channels
        ]
        buttons.append([InlineKeyboardButton("• ᴊᴏɪɴᴇᴅ •", callback_data="check_subscription")])

        try:
            await callback_query.message.edit_caption(
                caption="**ᴘʟᴇᴀsᴇ ᴊᴏɪɴ ᴀʟʟ ᴜᴘᴅᴀᴛᴇ ᴄʜᴀɴɴᴇʟs ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ.**",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
            await callback_query.answer("Please join all required channels", show_alert=True)
        except Exception as e:
            logger.error(f"Error editing message: {e}")
