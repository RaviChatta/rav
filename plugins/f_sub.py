import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant
from config import settings
from helpers.utils import get_random_photo

FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS


async def not_subscribed(_, __, message):
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await message._client.get_chat_member(channel, message.from_user.id)
            if user.status in {"kicked", "left"}:
                return True
        except UserNotParticipant:
            return True
    return False

@Client.on_message(filters.private & filters.create(not_subscribed))
async def forces_sub(client, message):
    IMAGE_URL = await get_random_photo()
    not_joined_channels = []
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, message.from_user.id)
            if user.status in {"kicked", "left"}:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)

    buttons = [
        [
            InlineKeyboardButton(
                text=f"• ʀᴇᴊᴏɪɴᴅʀᴇ {channel.capitalize()} •", url=f"https://t.me/{channel}"
            )
        ]
        for channel in not_joined_channels
    ]
    buttons.append(
        [
            InlineKeyboardButton(
                text="• ᴊ'ᴀɪ ʀᴇᴊᴏɪɴᴛ •", callback_data="check_subscription"
            )
        ]
    )

    text = "**ʙᴀᴋᴀᴋᴀ !!, ᴠᴏᴜs ɴ'ᴇ̂ᴛᴇs ᴘᴀs ᴀʙᴏɴɴᴇ́ ᴀ̀ ᴛᴏᴜs ʟᴇs ᴄᴀɴᴀᴜx ʀᴇǫᴜɪs, ʀᴇᴊᴏɪɢɴᴇᴢ ʟᴇs ᴄᴀɴᴀᴜx ᴅᴇ ᴍɪsᴇ ᴀ̀ ᴊᴏᴜʀ ᴘᴏᴜʀ ᴄᴏɴᴛɪɴᴜᴇʀ.**"
    await message.reply_photo(
        photo=IMAGE_URL,
        caption=text,
        reply_markup=InlineKeyboardMarkup(buttons)
    )

@Client.on_callback_query(filters.regex("check_subscription"))
async def check_subscription(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    not_joined_channels = []

    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, user_id)
            if user.status in {"kicked", "left"}:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)

    if not not_joined_channels:
        new_text = "**ᴠᴏᴜs ᴇ̂ᴛᴇs ᴀʙᴏɴɴᴇ́ ᴀ̀ ᴛᴏᴜs ʟᴇs ᴄᴀɴᴀᴜx ʀᴇǫᴜɪs. ᴍᴇʀᴄɪ ! 😊 /start ᴍᴀɪɴᴛᴇɴᴀɴᴛ.**"
        if callback_query.message.caption != new_text:
            await callback_query.message.edit_caption(
                caption=new_text,
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("• ᴄʟɪǫᴜᴇᴢ ɪᴄɪ ᴍᴀɪɴᴛᴇɴᴀɴᴛ •", callback_data='help')]
                ])
            )
    else:
        buttons = [
            [
                InlineKeyboardButton(
                    text=f"• ʀᴇᴊᴏɪɴᴅʀᴇ {channel.capitalize()} •",
                    url=f"https://t.me/{channel}",
                )
            ]
            for channel in not_joined_channels
        ]
        buttons.append(
            [
                InlineKeyboardButton(
                    text="• ᴊ'ᴀɪ ʀᴇᴊᴏɪɴᴛ •", callback_data="check_subscription"
                )
            ]
        )

        text = "**ᴠᴏᴜs ᴇ̂ᴛᴇs ᴀʙᴏɴɴᴇ́ ᴀ̀ ᴛᴏᴜs ʟᴇs ᴄᴀɴᴀᴜx ʀᴇǫᴜɪs. ᴠᴇᴜɪʟʟᴇᴢ ʀᴇᴊᴏɪɴᴅʀᴇ ʟᴇs ᴄᴀɴᴀᴜx ᴅᴇ ᴍɪsᴇ ᴀ̀ ᴊᴏᴜʀ ᴘᴏᴜʀ ᴄᴏɴᴛɪɴᴜᴇʀ.**"
        if callback_query.message.caption != text:
            await callback_query.message.edit_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
