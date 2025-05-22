import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
from pyrogram.errors import UserNotParticipant, FloodWait
from config import settings
from helpers.utils import get_random_photo
import asyncio
import time

FORCE_SUB_CHANNELS = settings.FORCE_SUB_CHANNELS

async def not_subscribed(_, client, message):
    for channel in FORCE_SUB_CHANNELS:
        try:
            user = await client.get_chat_member(channel, message.from_user.id)
            if user.status in ["kicked", "left"]:
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
            if user.status in ["kicked", "left"]:
                not_joined_channels.append(channel)
        except UserNotParticipant:
            not_joined_channels.append(channel)

    buttons = []
    for channel in not_joined_channels:
        try:
            chat = await client.get_chat(channel)
            channel_name = chat.title
            buttons.append([
                InlineKeyboardButton(
                    text=f"• Join {channel_name} •",
                    url=f"https://t.me/{channel}"
                )
            ])
        except:
            buttons.append([
                InlineKeyboardButton(
                    text=f"• Join Channel •",
                    url=f"https://t.me/{channel}"
                )
            ])

    buttons.append([
        InlineKeyboardButton(
            text="• I've Joined •",
            callback_data="check_subscription"
        )
    ])

    text = "**Hey! You need to join our channels to use this bot.**\n\nPlease join all required channels below and then click 'I've Joined' to verify."
    
    try:
        await message.reply_photo(
            photo=IMAGE_URL,
            caption=text,
            reply_markup=InlineKeyboardMarkup(buttons)
        )
    except:
        await message.reply_text(
            text=text,
            reply_markup=InlineKeyboardMarkup(buttons),
            disable_web_page_preview=True
        )

@Client.on_callback_query(filters.regex("^check_subscription$"))
async def check_subscription(client, callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    not_joined_channels = []

    # Check subscription with retries
    for _ in range(5):  # Max 5 retries
        not_joined_channels = []
        for channel in FORCE_SUB_CHANNELS:
            try:
                user = await client.get_chat_member(channel, user_id)
                if user.status in ["kicked", "left"]:
                    not_joined_channels.append(channel)
            except UserNotParticipant:
                not_joined_channels.append(channel)
        
        if not not_joined_channels:
            break
        await asyncio.sleep(2)  # Wait 2 seconds between retries

    if not not_joined_channels:
        # Success - delete previous messages
        try:
            await callback_query.message.delete()
        except:
            pass
        
        # Send success message
        success_text = "**✅ Successfully verified! You can now use the bot.**\n\nType /start to begin."
        await client.send_message(
            chat_id=user_id,
            text=success_text,
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("• Click Here •", callback_data='help')]
            ])
        )
    else:
        # Still not subscribed to some channels
        buttons = []
        for channel in not_joined_channels:
            try:
                chat = await client.get_chat(channel)
                channel_name = chat.title
                buttons.append([
                    InlineKeyboardButton(
                        text=f"• Join {channel_name} •",
                        url=f"https://t.me/{channel}"
                    )
                ])
            except:
                buttons.append([
                    InlineKeyboardButton(
                        text=f"• Join Channel •",
                        url=f"https://t.me/{channel}"
                    )
                ])

        buttons.append([
            InlineKeyboardButton(
                text="• I've Joined •",
                callback_data="check_subscription"
            )
        ])

        text = "**You're still not subscribed to all required channels.**\n\nPlease join these channels and try again:"
        
        try:
            await callback_query.message.edit_caption(
                caption=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        except:
            await callback_query.message.edit_text(
                text=text,
                reply_markup=InlineKeyboardMarkup(buttons)
            )
        
        await callback_query.answer("Please join all channels first!", show_alert=True)
